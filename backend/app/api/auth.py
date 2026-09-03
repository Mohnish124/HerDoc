from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.models import AuditLog, RefreshToken, User, UserRole
from app.db.session import get_session_local
from app.services.auth_service import (
    hash_password,
    hash_pin,
    hash_refresh_token,
    verify_access_token,
    verify_password,
    verify_pin,
    verify_refresh_token,
    verify_refresh_token_hash,
)
from app.services.tokens import create_access_token, create_refresh_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

LOGIN_RATE_LIMIT_SECONDS = 60
LOGIN_RATE_LIMIT_MAX = 5
LOCKOUT_MINUTES = 15
FAILED_LOGIN_LIMIT = 5
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)

_rate_limiter: dict[str, list[float]] = {}


class WorkerRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=5, max_length=32)
    temporary_pin: str = Field(..., min_length=4, max_length=6)


class WorkerLoginRequest(BaseModel):
    phone: str = Field(..., min_length=5, max_length=32)
    pin: str = Field(..., min_length=4, max_length=6)


class EmailAddressMixin(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized or normalized.count("@") != 1:
            raise ValueError("Invalid email address")
        local_part, domain = normalized.split("@", 1)
        if not local_part or not domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Invalid email address")
        if any(ch.isspace() for ch in normalized):
            raise ValueError("Invalid email address")
        return normalized


class DoctorRegisterRequest(EmailAddressMixin):
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=10, max_length=255)


class DoctorLoginRequest(EmailAddressMixin):
    password: str = Field(..., min_length=10, max_length=255)


class AdminRegisterRequest(EmailAddressMixin):
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=10, max_length=255)


class AdminLoginRequest(EmailAddressMixin):
    password: str = Field(..., min_length=10, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None)


COOKIE_NAME = "herdoc_refresh_token"


def _set_refresh_cookie(response: Response | None, refresh_token_str: str) -> None:
    if response is not None:
        response.set_cookie(
            key=COOKIE_NAME,
            value=refresh_token_str,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
            path="/api/auth",
        )


def _clear_refresh_cookie(response: Response | None) -> None:
    if response is not None:
        response.delete_cookie(
            key=COOKIE_NAME,
            path="/api/auth",
            httponly=True,
            samesite="lax",
        )


def _get_db() -> Session:
    return get_session_local()()


def _log_audit(db: Session, user_id: uuid.UUID | None, event_type: str, metadata: dict[str, Any] | None = None) -> None:
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            event_type=event_type,
            event_metadata=metadata or {},
        )
    )


def _user_response(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "name": user.name,
        "role": user.role,
        "phone": user.phone,
        "email": user.email,
    }


def _remember_attempt(key: str) -> None:
    now = time.time()
    bucket = _rate_limiter.setdefault(key, [])
    bucket[:] = [ts for ts in bucket if now - ts < LOGIN_RATE_LIMIT_SECONDS]
    bucket.append(now)


def _is_rate_limited(key: str) -> bool:
    now = time.time()
    bucket = _rate_limiter.setdefault(key, [])
    bucket[:] = [ts for ts in bucket if now - ts < LOGIN_RATE_LIMIT_SECONDS]
    return len(bucket) >= LOGIN_RATE_LIMIT_MAX


def _check_lockout(user: User) -> None:
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            remaining_minutes = max(1, int((locked_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account is locked. Try again in {remaining_minutes} minutes.")


def _handle_failed_login(db: Session, user: User, *, key: str, event: str) -> None:
    _remember_attempt(key)
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= FAILED_LOGIN_LIMIT:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        _log_audit(db, user.id, "lockout", {"failed_attempts": user.failed_login_attempts, "event": event})
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account locked for 15 minutes due to repeated failed login attempts.")
    _log_audit(db, user.id, "failed_login", {"failed_attempts": user.failed_login_attempts, "event": event})
    db.commit()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


def _reset_successful_login(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)


def require_role(*allowed_roles: str):
    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> User:
        if credentials is None or not credentials.credentials:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        try:
            claims = verify_access_token(credentials.credentials)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc

        db = _get_db()
        try:
            user = db.query(User).filter(User.id == uuid.UUID(claims["sub"])).first()
        finally:
            db.close()

        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found or inactive")
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return dependency


def require_admin() -> Any:
    return require_role("admin")


def require_doctor_or_admin() -> Any:
    return require_role("doctor", "admin")


def require_worker() -> Any:
    return require_role("worker")


@router.post("/register/worker")
def register_worker(payload: WorkerRegisterRequest, admin_user: User = Depends(require_admin())):
    db = _get_db()
    try:
        normalized_phone = payload.phone.strip()
        if db.query(User).filter(User.phone == normalized_phone).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already registered")

        try:
            pin_hash = hash_pin(payload.temporary_pin)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        user = User(
            id=uuid.uuid4(),
            role=UserRole.WORKER.value,
            name=payload.name.strip(),
            phone=normalized_phone,
            email=None,
            password_hash=None,
            pin_hash=pin_hash,
            facility_id=admin_user.facility_id,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
        db.add(user)
        db.flush()
        _log_audit(db, admin_user.id, "role.account_change", {"target_role": "worker", "target_user_id": str(user.id)})
        db.commit()
        return {"message": "Worker registered", "user": _user_response(user)}
    finally:
        db.close()


@router.post("/login/worker")
def login_worker(payload: WorkerLoginRequest):
    db = _get_db()
    try:
        key = f"worker:{payload.phone.strip()}"
        user = db.query(User).filter(User.phone == payload.phone.strip()).first()
        if user is None:
            _remember_attempt(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not user.is_active:
            _remember_attempt(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Worker account is deactivated. Contact administrator.")

        _check_lockout(user)
        if _is_rate_limited(key):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

        if not user.pin_hash or not verify_pin(payload.pin, user.pin_hash):
            _handle_failed_login(db, user, key=key, event="worker_login")

        _reset_successful_login(db, user)
        _rate_limiter.pop(key, None)
        db.commit()
        _log_audit(db, user.id, "successful_authentication", {"role": user.role, "event": "worker_login"})

        access = create_access_token(str(user.id), expires_delta=ACCESS_TOKEN_TTL)
        refresh = create_refresh_token(str(user.id), expires_delta=REFRESH_TOKEN_TTL)
        refresh_hash = hash_refresh_token(refresh)
        db.add(RefreshToken(id=uuid.uuid4(), user_id=user.id, token_hash=refresh_hash, expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL))
        db.commit()
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()), "user": _user_response(user)}
    finally:
        db.close()


@router.post("/register/doctor")
def register_doctor(payload: DoctorRegisterRequest, admin_user: User = Depends(require_admin())):
    db = _get_db()
    try:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        try:
            password_hash = hash_password(payload.password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        user = User(
            id=uuid.uuid4(),
            name=payload.name.strip(),
            role=UserRole.DOCTOR.value,
            email=str(payload.email),
            password_hash=password_hash,
            pin_hash=None,
            facility_id=admin_user.facility_id,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
        db.add(user)
        db.flush()
        _log_audit(db, admin_user.id, "role.account_change", {"target_role": "doctor", "target_user_id": str(user.id)})
        db.commit()
        return {"message": "Doctor registered", "user": _user_response(user)}
    finally:
        db.close()


@router.post("/login/doctor")
def login_doctor(payload: DoctorLoginRequest, response: Response = None):
    db = _get_db()
    try:
        key = f"doctor:{payload.email}"
        user = db.query(User).filter(User.email == str(payload.email)).first()
        if user is None:
            _remember_attempt(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        _check_lockout(user)
        if _is_rate_limited(key):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

        if not user.password_hash or not verify_password(payload.password, user.password_hash):
            _handle_failed_login(db, user, key=key, event="doctor_login")

        _reset_successful_login(db, user)
        _rate_limiter.pop(key, None)
        db.commit()
        _log_audit(db, user.id, "successful_authentication", {"role": user.role, "event": "doctor_login"})

        access = create_access_token(str(user.id), expires_delta=ACCESS_TOKEN_TTL)
        refresh = create_refresh_token(str(user.id), expires_delta=REFRESH_TOKEN_TTL)
        refresh_hash = hash_refresh_token(refresh)
        db.add(RefreshToken(id=uuid.uuid4(), user_id=user.id, token_hash=refresh_hash, expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL))
        db.commit()
        _set_refresh_cookie(response, refresh)
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()), "user": _user_response(user)}
    finally:
        db.close()


@router.post("/register/admin")
def register_admin(payload: AdminRegisterRequest):
    db = _get_db()
    try:
        if db.query(User).filter(User.email == str(payload.email)).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        try:
            password_hash = hash_password(payload.password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        user = User(
            id=uuid.uuid4(),
            name=payload.name.strip(),
            role=UserRole.ADMIN.value,
            email=str(payload.email),
            password_hash=password_hash,
            pin_hash=None,
            facility_id=None,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
        db.add(user)
        db.flush()
        _log_audit(db, user.id, "role.account_change", {"target_role": "admin", "target_user_id": str(user.id)})
        db.commit()
        return {"message": "Admin registered", "user": _user_response(user)}
    finally:
        db.close()


@router.post("/login/admin")
def login_admin(payload: AdminLoginRequest, response: Response = None):
    db = _get_db()
    try:
        key = f"admin:{payload.email}"
        user = db.query(User).filter(User.email == str(payload.email)).first()
        if user is None:
            _remember_attempt(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        _check_lockout(user)
        if _is_rate_limited(key):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

        if not user.password_hash or not verify_password(payload.password, user.password_hash):
            _handle_failed_login(db, user, key=key, event="admin_login")

        _reset_successful_login(db, user)
        _rate_limiter.pop(key, None)
        db.commit()
        _log_audit(db, user.id, "successful_authentication", {"role": user.role, "event": "admin_login"})

        access = create_access_token(str(user.id), expires_delta=ACCESS_TOKEN_TTL)
        refresh = create_refresh_token(str(user.id), expires_delta=REFRESH_TOKEN_TTL)
        refresh_hash = hash_refresh_token(refresh)
        db.add(RefreshToken(id=uuid.uuid4(), user_id=user.id, token_hash=refresh_hash, expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL))
        db.commit()
        _set_refresh_cookie(response, refresh)
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()), "user": _user_response(user)}
    finally:
        db.close()


@router.post("/login/web")
def login_web(payload: DoctorLoginRequest, response: Response = None):
    db = _get_db()
    try:
        key = f"web:{payload.email}"
        user = db.query(User).filter(User.email == str(payload.email)).first()
        if user is None or user.role not in {UserRole.DOCTOR.value, UserRole.ADMIN.value}:
            _remember_attempt(key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        _check_lockout(user)
        if _is_rate_limited(key):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

        if not user.password_hash or not verify_password(payload.password, user.password_hash):
            _handle_failed_login(db, user, key=key, event="web_login")

        _reset_successful_login(db, user)
        _rate_limiter.pop(key, None)
        db.commit()
        _log_audit(db, user.id, "successful_authentication", {"role": user.role, "event": "web_login"})

        access = create_access_token(str(user.id), expires_delta=ACCESS_TOKEN_TTL)
        refresh = create_refresh_token(str(user.id), expires_delta=REFRESH_TOKEN_TTL)
        refresh_hash = hash_refresh_token(refresh)
        db.add(RefreshToken(id=uuid.uuid4(), user_id=user.id, token_hash=refresh_hash, expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL))
        db.commit()
        _set_refresh_cookie(response, refresh)
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()), "user": _user_response(user)}
    finally:
        db.close()


@router.post("/refresh")
def refresh_token(payload: RefreshRequest | None = None, request: Request = None, response: Response = None):
    raw_token = payload.refresh_token if payload and payload.refresh_token else None
    if not raw_token and request is not None:
        raw_token = request.cookies.get(COOKIE_NAME)

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")

    db = _get_db()
    try:
        try:
            claims = verify_refresh_token(raw_token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

        user = db.query(User).filter(User.id == uuid.UUID(claims["sub"])).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        incoming_hash = hash_refresh_token(raw_token)
        records = db.query(RefreshToken).filter(RefreshToken.user_id == user.id).all()
        active_record = next((record for record in records if verify_refresh_token_hash(raw_token, record.token_hash) and record.revoked_at is None), None)
        if active_record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

        active_record.revoked_at = datetime.now(timezone.utc)
        new_refresh = create_refresh_token(str(user.id), expires_delta=REFRESH_TOKEN_TTL)
        new_hash = hash_refresh_token(new_refresh)
        db.add(RefreshToken(id=uuid.uuid4(), user_id=user.id, token_hash=new_hash, expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL))
        db.commit()
        _log_audit(db, user.id, "successful_authentication", {"role": user.role, "event": "refresh"})
        db.commit()
        access = create_access_token(str(user.id), expires_delta=ACCESS_TOKEN_TTL)
        _set_refresh_cookie(response, new_refresh)
        return {
            "access_token": access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
            "user": _user_response(user),
        }
    finally:
        db.close()


@router.post("/logout")
def logout(payload: LogoutRequest | None = None, request: Request = None, response: Response = None):
    raw_token = payload.refresh_token if payload and payload.refresh_token else None
    if not raw_token and request is not None:
        raw_token = request.cookies.get(COOKIE_NAME)

    db = _get_db()
    try:
        if raw_token:
            try:
                claims = verify_refresh_token(raw_token)
                user = db.query(User).filter(User.id == uuid.UUID(claims["sub"])).first()
                if user is not None:
                    incoming_hash = hash_refresh_token(raw_token)
                    records = db.query(RefreshToken).filter(RefreshToken.user_id == user.id).all()
                    for record in records:
                        if record.token_hash == incoming_hash or record.revoked_at is None:
                            record.revoked_at = datetime.now(timezone.utc)
                    db.commit()
                    _log_audit(db, user.id, "successful_authentication", {"role": user.role, "event": "logout"})
                    db.commit()
            except Exception:
                pass

        _clear_refresh_cookie(response)
        return {"message": "Logged out"}
    finally:
        db.close()


@router.get("/me")
def me(user: User = Depends(require_role("admin", "doctor", "worker"))):
    return {"user": _user_response(user)}
