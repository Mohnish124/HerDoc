"""JWT creation and verification for HerDoc access/refresh tokens.

Access tokens: short-lived (15 minutes) for authenticating API calls.
Refresh tokens: long-lived (30 days) for minting new access tokens.

Token claims:
    - ``sub``: Subject identifier (user UUID string)
    - ``type``: "access" | "refresh"
    - ``iat``: Issued-at timestamp (seconds since Epoch, int)
    - ``exp``: Expiry timestamp (seconds since Epoch, int)
    - ``jti``: Unique token id (UUID string) for refresh tokens
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Mapping

import jwt
from jwt import DecodeError, ExpiredSignatureError, InvalidTokenError

from app.config import get_settings

LOGGER = logging.getLogger(__name__)

JWT_ALGORITHM: Final[str] = "HS256"

ACCESS_TOKEN_TTL: Final[timedelta] = timedelta(minutes=15)
REFRESH_TOKEN_TTL: Final[timedelta] = timedelta(days=30)

TOKEN_TYPE_ACCESS: Final[str] = "access"
TOKEN_TYPE_REFRESH: Final[str] = "refresh"

REQUIRED_CLAIMS: Final[frozenset[str]] = frozenset({"sub", "type", "iat", "exp"})


class JWTError(ValueError):
    """Base error for all JWT-related failures.

    Messages are intentionally generic to avoid leaking token structure
    in logs or error responses.
    """


class TokenExpiredError(JWTError):
    """Raised when a JWT's ``exp`` claim has passed."""


class TokenInvalidError(JWTError):
    """Raised when a JWT's signature or claims fail validation."""


def _secret_key() -> str:
    secret = get_settings().JWT_SECRET
    if not secret or len(secret) < 16:
        raise JWTError("JWT secret is too short or not configured.")
    return secret


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: Mapping[str, Any]) -> str:
    return jwt.encode(dict(payload), _secret_key(), algorithm=JWT_ALGORITHM)


def _decode(token: str, *, verify_exp: bool) -> dict[str, Any]:
    options = {"verify_exp": verify_exp}
    try:
        return jwt.decode(
            token,
            _secret_key(),
            algorithms=[JWT_ALGORITHM],
            options=options,
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired.") from exc
    except (DecodeError, InvalidTokenError) as exc:
        raise TokenInvalidError("Token is invalid.") from exc


def _validate_common_claims(payload: Mapping[str, Any], expected_type: str) -> None:
    for claim in REQUIRED_CLAIMS:
        if claim not in payload:
            raise TokenInvalidError(f"Token missing required claim: {claim}.")

    if payload.get("type") != expected_type:
        raise TokenInvalidError("Token type is invalid.")

    if not isinstance(payload["sub"], str) or not payload["sub"]:
        raise TokenInvalidError("Token subject is invalid.")

    if not isinstance(payload["iat"], int) or payload["iat"] < 0:
        raise TokenInvalidError("Token issued-at claim is invalid.")

    if not isinstance(payload["exp"], int) or payload["exp"] <= 0:
        raise TokenInvalidError("Token expiration claim is invalid.")

    now = int(_now_utc().timestamp())
    if now >= payload["exp"]:
        raise TokenExpiredError("Token has expired.")


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create an access token.

    :param subject: The user identifier (UUID string recommended).
    :param expires_delta: Override the default 15-minute TTL (for tests only).
    """
    if not subject:
        raise JWTError("Access token subject must not be empty.")
    ttl = expires_delta if expires_delta is not None else ACCESS_TOKEN_TTL
    if ttl.total_seconds() <= 0:
        raise JWTError("Access token TTL must be positive.")
    now = _now_utc()
    payload = {
        "sub": subject,
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return _encode(payload)


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify an access token and return its claims.

    Raises :class:`TokenExpiredError` or :class:`TokenInvalidError`.
    """
    if not token:
        raise TokenInvalidError("Token is empty.")
    payload = _decode(token, verify_exp=True)
    _validate_common_claims(payload, expected_type=TOKEN_TYPE_ACCESS)
    return payload


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a refresh token.

    Refresh tokens include a ``jti`` so they can be individually revoked via
    the ``refresh_tokens`` database table (``token_hash`` stores a HASH of
    the JWT string — NEVER store the JWT refresh token itself in plaintext).
    """
    if not subject:
        raise JWTError("Refresh token subject must not be empty.")
    ttl = expires_delta if expires_delta is not None else REFRESH_TOKEN_TTL
    if ttl.total_seconds() <= 0:
        raise JWTError("Refresh token TTL must be positive.")
    now = _now_utc()
    payload = {
        "sub": subject,
        "type": TOKEN_TYPE_REFRESH,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Verify a refresh token JWT and return its claims.

    IMPORTANT: Callers MUST additionally verify the ``jti`` hash against the
    ``refresh_tokens`` table to confirm the token has not been revoked.
    """
    if not token:
        raise TokenInvalidError("Token is empty.")
    payload = _decode(token, verify_exp=True)
    _validate_common_claims(payload, expected_type=TOKEN_TYPE_REFRESH)
    if "jti" not in payload or not isinstance(payload["jti"], str):
        raise TokenInvalidError("Refresh token missing jti.")
    return payload
