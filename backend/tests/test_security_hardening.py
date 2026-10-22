"""Regression tests for the pre-deployment security hardening.

Covers: admin registration and first-admin bootstrap, refresh-cookie handling
behind a same-origin proxy, demo-account blocking in production, facility
isolation for doctors and admins, sync ownership, sensitive endpoints, and
production configuration checks.
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import app.api.auth as auth_module
import app.main as main_module
from app.api.auth import COOKIE_NAME, _rate_limiter
from app.bootstrap_admin import BootstrapError, bootstrap_first_admin
from app.bootstrap_admin import main as bootstrap_main
from app.config import Settings, get_settings
from app.db.base import Base
from app.db.models import AuditLog, Facility, FacilityType, Patient, RiskFlag, User, UserRole, Visit
from app.db.seed import DEMO_USERS, seed_demo_data
from app.db.session import get_session_local
from app.main import app, check_no_demo_accounts, create_app
from app.services.auth_service import hash_password, hash_pin
from app.services.demo_accounts import DEMO_PHONES, is_demo_identity

client = TestClient(app)

PROXY_ORIGIN = "https://herdoc-web.onrender.com"
STRONG_PASSWORD = "Str0ng!Passw0rd-2026"


def _prod_settings(**overrides) -> Settings:
    values = dict(
        _env_file=None,
        ENVIRONMENT="production",
        DATABASE_URL="mysql+pymysql://user:pass@db.example.org:3306/herdoc",
        JWT_SECRET="p" * 48,
        WEB_ORIGIN=PROXY_ORIGIN,
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_CHAT_ID="",
        METRICS_TOKEN="",
    )
    values.update(overrides)
    return Settings(**values)


def _db():
    return get_session_local()()


def _login_admin(c: TestClient = client) -> str:
    resp = c.post("/api/auth/login/admin", json={"email": "admin@herdoc.local", "password": "AdminPass!2024"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _login_doctor(c: TestClient = client) -> str:
    resp = c.post("/api/auth/login/doctor", json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_user(*, role: str, facility_id, active: bool = True, password: str = STRONG_PASSWORD) -> User:
    db = _db()
    try:
        user = User(
            id=uuid.uuid4(),
            role=role,
            name=f"{role} {uuid.uuid4().hex[:6]}",
            email=f"{role}-{uuid.uuid4().hex[:8]}@example.org" if role != UserRole.WORKER.value else None,
            phone=f"8{uuid.uuid4().int % 900000000:09d}" if role == UserRole.WORKER.value else None,
            password_hash=hash_password(password) if role != UserRole.WORKER.value else None,
            pin_hash=hash_pin("2468") if role == UserRole.WORKER.value else None,
            facility_id=facility_id,
            is_active=active,
            failed_login_attempts=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


@pytest.fixture(scope="module")
def two_facilities():
    """Seeded Facility 1 (demo admin/doctor/worker) plus an isolated Facility 2 with one patient."""
    db = _db()
    try:
        seed_demo_data(db, commit=True)
        f1 = db.query(Facility).filter(Facility.name == "Demo PHC").first()
        f2 = Facility(id=uuid.uuid4(), name=f"Isolated PHC {uuid.uuid4().hex[:6]}", region="East", type=FacilityType.PHC.value)
        db.add(f2)
        db.flush()
        w2 = User(
            id=uuid.uuid4(), role=UserRole.WORKER.value, name="F2 Worker",
            phone=f"7{uuid.uuid4().int % 900000000:09d}", pin_hash=hash_pin("2468"),
            facility_id=f2.id, is_active=True, failed_login_attempts=0,
        )
        db.add(w2)
        db.flush()
        p2 = Patient(id=uuid.uuid4(), worker_id=w2.id, name="F2 Patient", age=27, village="East Village", edd=date(2026, 12, 1))
        db.add(p2)
        db.flush()
        v2 = Visit(
            id=uuid.uuid4(), patient_id=p2.id, worker_id=w2.id, visit_date=date.today(),
            systolic_bp=150, diastolic_bp=95, created_locally_at=datetime.now(timezone.utc),
        )
        db.add(v2)
        db.flush()
        db.add(RiskFlag(id=uuid.uuid4(), visit_id=v2.id, model_risk_level="red", trend_adjusted_level="red"))
        db.commit()
        return {"f1_id": str(f1.id), "f2_id": str(f2.id), "w2_id": str(w2.id), "p2_id": str(p2.id)}
    finally:
        db.close()


# ---------------------------------------------------------------- admin registration

def test_unauthenticated_admin_registration_is_rejected(two_facilities):
    email = f"intruder-{uuid.uuid4().hex[:8]}@example.org"
    resp = client.post("/api/auth/register/admin", json={"name": "Intruder", "email": email, "password": STRONG_PASSWORD})
    assert resp.status_code == 401

    db = _db()
    try:
        assert db.query(User).filter(User.email == email).first() is None
    finally:
        db.close()


def test_doctor_cannot_register_admin(two_facilities):
    resp = client.post(
        "/api/auth/register/admin",
        headers=_auth(_login_doctor()),
        json={"name": "Sneaky", "email": f"sneaky-{uuid.uuid4().hex[:8]}@example.org", "password": STRONG_PASSWORD},
    )
    assert resp.status_code == 403


def test_admin_registers_admin_in_own_facility(two_facilities):
    email = f"second-admin-{uuid.uuid4().hex[:8]}@example.org"
    resp = client.post(
        "/api/auth/register/admin",
        headers=_auth(_login_admin()),
        json={"name": "Second Admin", "email": email, "password": STRONG_PASSWORD},
    )
    assert resp.status_code == 200, resp.text

    db = _db()
    try:
        created = db.query(User).filter(User.email == email).one()
        assert created.role == UserRole.ADMIN.value
        assert str(created.facility_id) == two_facilities["f1_id"]
    finally:
        db.close()

    login = client.post("/api/auth/login/admin", json={"email": email, "password": STRONG_PASSWORD})
    assert login.status_code == 200, login.text


def test_admin_without_facility_cannot_register_users(two_facilities):
    orphan_admin = _create_user(role=UserRole.ADMIN.value, facility_id=None)
    token = client.post("/api/auth/login/admin", json={"email": orphan_admin.email, "password": STRONG_PASSWORD}).json()["access_token"]
    for path, body in [
        ("/api/auth/register/worker", {"name": "W", "phone": f"6{uuid.uuid4().int % 900000000:09d}", "temporary_pin": "2468"}),
        ("/api/auth/register/doctor", {"name": "D", "email": f"d-{uuid.uuid4().hex[:8]}@example.org", "password": STRONG_PASSWORD}),
        ("/api/auth/register/admin", {"name": "A", "email": f"a-{uuid.uuid4().hex[:8]}@example.org", "password": STRONG_PASSWORD}),
    ]:
        assert client.post(path, headers=_auth(token), json=body).status_code == 403, path


# ---------------------------------------------------------------- first-admin bootstrap

@pytest.fixture()
def empty_db():
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def _bootstrap(db, **overrides):
    values = dict(
        name="First Admin", email="first.admin@example.org", password=STRONG_PASSWORD,
        facility_name="PHC Rampur", facility_region="North",
    )
    values.update(overrides)
    return bootstrap_first_admin(db, **values)


def test_bootstrap_creates_first_admin_with_facility(empty_db):
    admin = _bootstrap(empty_db)
    assert admin.role == UserRole.ADMIN.value
    assert admin.facility_id is not None
    facility = empty_db.get(Facility, admin.facility_id)
    assert facility.name == "PHC Rampur"
    assert admin.password_hash and admin.password_hash != STRONG_PASSWORD
    assert empty_db.query(AuditLog).filter(AuditLog.event_type == "admin.bootstrap").count() == 1


def test_bootstrap_refuses_when_an_admin_exists(empty_db):
    _bootstrap(empty_db)
    with pytest.raises(BootstrapError, match="already exists"):
        _bootstrap(empty_db, email="another@example.org")
    assert empty_db.query(User).filter(User.role == UserRole.ADMIN.value).count() == 1


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"email": "admin@herdoc.local"}, "Demo"),
        ({"password": "short"}, ""),
        ({"facility_type": "hospital"}, "Facility type"),
        ({"facility_name": "  "}, "Facility name"),
    ],
)
def test_bootstrap_rejects_unsafe_input(empty_db, overrides, message):
    with pytest.raises(BootstrapError, match=message):
        _bootstrap(empty_db, **overrides)
    assert empty_db.query(User).count() == 0
    assert empty_db.query(Facility).count() == 0


def test_bootstrap_cli_refuses_existing_admin_and_honours_abort(two_facilities, monkeypatch):
    monkeypatch.setenv("HERDOC_BOOTSTRAP_ADMIN_PASSWORD", STRONG_PASSWORD)
    args = ["--name", "X", "--email", f"x-{uuid.uuid4().hex[:6]}@example.org", "--facility-name", "F", "--facility-region", "R"]

    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    assert bootstrap_main(args) == 1

    # The seeded test database already has an admin, so a real run must refuse.
    assert bootstrap_main(args + ["--yes"]) == 2


# ---------------------------------------------------------------- cookies and same-origin proxy

@pytest.fixture()
def production_auth(monkeypatch):
    """Run the auth router with production settings (Secure cookies, demo logins blocked)."""
    settings = _prod_settings()
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    return settings


def _cookie_header(resp, name=COOKIE_NAME) -> str:
    headers = [h for h in resp.headers.get_list("set-cookie") if h.startswith(f"{name}=")]
    assert headers, "refresh cookie not set"
    return headers[-1]


def _expired_token(sub: str, token_type: str) -> str:
    past = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    payload = {"sub": sub, "type": token_type, "iat": past - 60, "exp": past}
    if token_type == "refresh":
        payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, get_settings().JWT_SECRET, algorithm="HS256")


def test_web_session_through_same_origin_proxy(two_facilities, production_auth):
    doctor = _create_user(role=UserRole.DOCTOR.value, facility_id=uuid.UUID(two_facilities["f1_id"]))
    web = TestClient(app, base_url=PROXY_ORIGIN)

    # Login: access token in JSON, refresh token only in a Secure httpOnly SameSite=Strict cookie.
    login = web.post("/api/auth/login/web", json={"email": doctor.email, "password": STRONG_PASSWORD})
    assert login.status_code == 200, login.text
    assert "refresh_token" not in login.json()
    cookie = _cookie_header(login).lower()
    for attribute in ("httponly", "secure", "samesite=strict", "path=/api/auth"):
        assert attribute in cookie, attribute
    assert login.headers["cache-control"] == "no-store"
    first_cookie = web.cookies.get(COOKIE_NAME)

    # Session expiry: an expired access token is rejected...
    expired_access = _expired_token(str(doctor.id), "access")
    assert web.get("/api/auth/me", headers=_auth(expired_access)).status_code == 401

    # ...and silent refresh via the cookie (empty body, as web/src/api/client.js sends) recovers it.
    refreshed = web.post("/api/auth/refresh", json={})
    assert refreshed.status_code == 200, refreshed.text
    assert "refresh_token" not in refreshed.json()
    assert "secure" in _cookie_header(refreshed).lower()
    rotated_cookie = web.cookies.get(COOKIE_NAME)
    assert rotated_cookie and rotated_cookie != first_cookie
    assert web.get("/api/auth/me", headers=_auth(refreshed.json()["access_token"])).status_code == 200

    # The pre-rotation cookie can no longer be used.
    replay = TestClient(app, base_url=PROXY_ORIGIN).post(
        "/api/auth/refresh", json={}, headers={"Cookie": f"{COOKIE_NAME}={first_cookie}"}
    )
    assert replay.status_code == 401

    # Logout revokes the session and clears the cookie with matching attributes.
    logout = web.post("/api/auth/logout", json={})
    assert logout.status_code == 200
    cleared = _cookie_header(logout).lower()
    assert "max-age=0" in cleared and "secure" in cleared and "path=/api/auth" in cleared
    after = TestClient(app, base_url=PROXY_ORIGIN).post(
        "/api/auth/refresh", json={}, headers={"Cookie": f"{COOKIE_NAME}={rotated_cookie}"}
    )
    assert after.status_code == 401


def test_expired_refresh_cookie_is_rejected(two_facilities):
    doctor = _create_user(role=UserRole.DOCTOR.value, facility_id=uuid.UUID(two_facilities["f1_id"]))
    resp = TestClient(app).post(
        "/api/auth/refresh", json={}, headers={"Cookie": f"{COOKIE_NAME}={_expired_token(str(doctor.id), 'refresh')}"}
    )
    assert resp.status_code == 401


def test_development_cookie_is_not_secure_but_strict(two_facilities):
    doctor = _create_user(role=UserRole.DOCTOR.value, facility_id=uuid.UUID(two_facilities["f1_id"]))
    login = TestClient(app).post("/api/auth/login/web", json={"email": doctor.email, "password": STRONG_PASSWORD})
    assert login.status_code == 200
    cookie = _cookie_header(login).lower()
    assert "secure" not in cookie
    assert "samesite=strict" in cookie and "httponly" in cookie


def test_mobile_body_refresh_still_returns_rotated_token(two_facilities):
    worker = _create_user(role=UserRole.WORKER.value, facility_id=uuid.UUID(two_facilities["f1_id"]))
    mobile = TestClient(app)
    login = mobile.post("/api/auth/login/worker", json={"phone": worker.phone, "pin": "2468"})
    assert login.status_code == 200
    refresh = mobile.post("/api/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["refresh_token"] != login.json()["refresh_token"]
    assert not [h for h in refresh.headers.get_list("set-cookie") if h.startswith(f"{COOKIE_NAME}=")]


def test_refresh_rejected_for_deactivated_user(two_facilities):
    worker = _create_user(role=UserRole.WORKER.value, facility_id=uuid.UUID(two_facilities["f1_id"]))
    login = client.post("/api/auth/login/worker", json={"phone": worker.phone, "pin": "2468"})
    refresh_token = login.json()["refresh_token"]

    # Deactivate directly (without the admin endpoint's token revocation) to test the refresh check itself.
    db = _db()
    try:
        db.get(User, worker.id).is_active = False
        db.commit()
    finally:
        db.close()
    assert client.post("/api/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401


def test_deactivated_doctor_cannot_log_in(two_facilities):
    doctor = _create_user(role=UserRole.DOCTOR.value, facility_id=uuid.UUID(two_facilities["f1_id"]), active=False)
    for path in ("/api/auth/login/doctor", "/api/auth/login/web"):
        resp = client.post(path, json={"email": doctor.email, "password": STRONG_PASSWORD})
        assert resp.status_code == 401, path
        assert "access_token" not in resp.json()


def test_deactivated_worker_status_not_revealed_without_pin(two_facilities):
    worker = _create_user(role=UserRole.WORKER.value, facility_id=uuid.UUID(two_facilities["f1_id"]), active=False)
    wrong = client.post("/api/auth/login/worker", json={"phone": worker.phone, "pin": "9999"})
    assert wrong.status_code == 401
    assert "deactivated" not in wrong.json()["detail"].lower()


# ---------------------------------------------------------------- demo credentials

def test_demo_identities_cover_every_seeded_account():
    for config in DEMO_USERS:
        assert is_demo_identity(email=config["email"])
        assert config["phone"] in DEMO_PHONES
    assert not is_demo_identity(email="doctor@example.org", phone="9876543210")


def test_demo_accounts_cannot_log_in_in_production(two_facilities, production_auth):
    for path, body in [
        ("/api/auth/login/web", {"email": "doctor@herdoc.local", "password": "DoctorPass!2024"}),
        ("/api/auth/login/admin", {"email": "admin@herdoc.local", "password": "AdminPass!2024"}),
        ("/api/auth/login/doctor", {"email": "doctor@herdoc.local", "password": "DoctorPass!2024"}),
        ("/api/auth/login/worker", {"phone": "9000000003", "pin": "2468"}),
    ]:
        resp = client.post(path, json=body)
        assert resp.status_code == 401, path
        assert "access_token" not in resp.json()


def test_production_refuses_to_start_with_demo_accounts(two_facilities, monkeypatch):
    with pytest.raises(RuntimeError, match="demo account"):
        check_no_demo_accounts()

    monkeypatch.setattr(main_module, "check_database_connection", lambda: None)
    with pytest.raises(RuntimeError, match="demo account"):
        with TestClient(create_app(_prod_settings())):
            pass


# ---------------------------------------------------------------- facility isolation

@pytest.mark.parametrize("login", [_login_admin, _login_doctor], ids=["admin", "doctor"])
def test_patient_endpoints_enforce_facility(two_facilities, login):
    headers = _auth(login())
    p2 = two_facilities["p2_id"]
    assert client.get(f"/api/patients/{p2}", headers=headers).status_code == 403
    assert client.get(f"/api/patients/{p2}/visits", headers=headers).status_code == 403
    listed = client.get("/api/patients", headers=headers)
    assert listed.status_code == 200
    assert p2 not in {p["id"] for p in listed.json()}
    review = client.post("/api/reviews", headers=headers, json={"patient_id": p2, "status": "reviewed", "notes": "x"})
    assert review.status_code == 403


@pytest.mark.parametrize("login", [_login_admin, _login_doctor], ids=["admin", "doctor"])
def test_dashboard_enforces_facility(two_facilities, login):
    headers = _auth(login())
    f2 = two_facilities["f2_id"]
    assert client.get(f"/api/dashboard/flagged?facility_id={f2}", headers=headers).status_code == 403
    assert client.get(f"/api/dashboard/facility-overview?facility_id={f2}", headers=headers).status_code == 403

    flagged = client.get("/api/dashboard/flagged", headers=headers)
    assert flagged.status_code == 200
    assert two_facilities["p2_id"] not in {p["id"] for p in flagged.json()}

    filters = client.get("/api/dashboard/filters", headers=headers).json()
    assert {f["id"] for f in filters["facilities"]} == {two_facilities["f1_id"]}
    assert two_facilities["w2_id"] not in {w["id"] for w in filters["workers"]}


def test_admin_cannot_manage_other_facility_workers(two_facilities):
    headers = _auth(_login_admin())
    assert client.get(f"/api/workers?facility_id={two_facilities['f2_id']}", headers=headers).status_code == 403
    workers = client.get("/api/workers", headers=headers)
    assert workers.status_code == 200
    assert two_facilities["w2_id"] not in {w["id"] for w in workers.json()}

    resp = client.patch(f"/api/workers/{two_facilities['w2_id']}/status", headers=headers, json={"is_active": False})
    assert resp.status_code == 403
    db = _db()
    try:
        assert db.get(User, uuid.UUID(two_facilities["w2_id"])).is_active is True
    finally:
        db.close()


@pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.DOCTOR.value])
def test_staff_without_facility_see_nothing(two_facilities, role):
    user = _create_user(role=role, facility_id=None)
    token = client.post(f"/api/auth/login/{role}", json={"email": user.email, "password": STRONG_PASSWORD}).json()["access_token"]
    headers = _auth(token)
    for path in ("/api/patients", "/api/dashboard/flagged", "/api/dashboard/facility-overview", "/api/dashboard/filters",
                 f"/api/patients/{two_facilities['p2_id']}"):
        assert client.get(path, headers=headers).status_code == 403, path


# ---------------------------------------------------------------- sync ownership

def _sync(token: str, *, patients=(), visits=(), risk_flags=()):
    resp = client.post(
        "/api/sync",
        headers=_auth(token),
        json={"patients": list(patients), "visits": list(visits), "risk_flags": list(risk_flags), "last_synced_at": None},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _worker_session(facility_id: str):
    worker = _create_user(role=UserRole.WORKER.value, facility_id=uuid.UUID(facility_id))
    token = client.post("/api/auth/login/worker", json={"phone": worker.phone, "pin": "2468"}).json()["access_token"]
    return token, str(worker.id)


def _patient(pid, worker_id, name="Owner Patient"):
    return {"id": pid, "worker_id": worker_id, "name": name, "age": 25, "village": "V", "edd": "2026-12-01", "phone": None}


def _visit(vid, pid, worker_id):
    now = datetime.now(timezone.utc).isoformat()
    return {"id": vid, "patient_id": pid, "worker_id": worker_id, "visit_date": now, "systolic_bp": 120,
            "diastolic_bp": 80, "blood_sugar": 90, "body_temp_c": 37.0, "heart_rate": 80, "created_locally_at": now}


def test_sync_cannot_take_over_another_workers_patient(two_facilities):
    owner_token, owner_id = _worker_session(two_facilities["f1_id"])
    attacker_token, attacker_id = _worker_session(two_facilities["f2_id"])
    pid = str(uuid.uuid4())
    assert _sync(owner_token, patients=[_patient(pid, owner_id)])["patients"]["success"] == 1

    result = _sync(attacker_token, patients=[_patient(pid, attacker_id, name="Hijacked")])
    assert result["patients"]["failed"] == 1
    db = _db()
    try:
        patient = db.get(Patient, uuid.UUID(pid))
        assert str(patient.worker_id) == owner_id
        assert patient.name == "Owner Patient"
    finally:
        db.close()


def test_sync_cannot_move_another_workers_risk_flag(two_facilities):
    owner_token, owner_id = _worker_session(two_facilities["f1_id"])
    attacker_token, attacker_id = _worker_session(two_facilities["f1_id"])
    owner_pid, owner_vid, flag_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    flag = {"id": flag_id, "visit_id": owner_vid, "model_risk_level": "red", "trend_adjusted_level": "red", "trend_reason": None}
    _sync(owner_token, patients=[_patient(owner_pid, owner_id)], visits=[_visit(owner_vid, owner_pid, owner_id)], risk_flags=[flag])

    attacker_pid, attacker_vid = str(uuid.uuid4()), str(uuid.uuid4())
    stolen = dict(flag, visit_id=attacker_vid, model_risk_level="green", trend_adjusted_level="green")
    result = _sync(
        attacker_token,
        patients=[_patient(attacker_pid, attacker_id)],
        visits=[_visit(attacker_vid, attacker_pid, attacker_id)],
        risk_flags=[stolen],
    )
    assert result["risk_flags"]["failed"] == 1
    db = _db()
    try:
        stored = db.get(RiskFlag, uuid.UUID(flag_id))
        assert str(stored.visit_id) == owner_vid
        assert stored.trend_adjusted_level == "red"
    finally:
        db.close()


# ---------------------------------------------------------------- sensitive endpoints

def test_production_hides_docs_and_metrics():
    prod = TestClient(create_app(_prod_settings()))
    for path in ("/docs", "/redoc", "/openapi.json", "/metrics"):
        assert prod.get(path).status_code == 404, path
    assert prod.get("/health").status_code == 200


def test_metrics_token_protects_metrics():
    token = "m" * 40
    prod = TestClient(create_app(_prod_settings(METRICS_TOKEN=token)))
    assert prod.get("/metrics").status_code == 401
    assert prod.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = prod.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert "herdoc" in ok.text or "http_requests" in ok.text


def test_development_keeps_docs_and_metrics_open():
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_cors_allows_only_configured_origin():
    origin = get_settings().WEB_ORIGIN
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    allowed = client.options("/api/auth/login/web", headers={"Origin": origin, **preflight})
    assert allowed.headers.get("access-control-allow-origin") == origin
    assert allowed.headers.get("access-control-allow-credentials") == "true"
    denied = client.options("/api/auth/login/web", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in denied.headers


def test_api_responses_are_not_cacheable():
    assert client.get("/api/auth/me").headers["cache-control"] == "no-store"


def test_unknown_accounts_do_not_grow_rate_limiter():
    _rate_limiter.clear()
    for _ in range(3):
        email = f"ghost-{uuid.uuid4().hex}@example.org"
        assert client.post("/api/auth/login/web", json={"email": email, "password": STRONG_PASSWORD}).status_code == 401
    assert _rate_limiter == {}


def test_telegram_requests_are_not_logged_with_token():
    import app.services.telegram_service  # noqa: F401  (module import configures the loggers)

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


# ---------------------------------------------------------------- production configuration

def test_valid_production_settings_are_accepted():
    settings = _prod_settings(WEB_ORIGIN=PROXY_ORIGIN + "/")
    assert settings.is_production and settings.cookie_secure and not settings.api_docs_enabled
    assert settings.WEB_ORIGIN == PROXY_ORIGIN


@pytest.mark.parametrize(
    "overrides",
    [
        {"JWT_SECRET": "short-but-secret"},
        {"JWT_SECRET": "REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS"},
        {"WEB_ORIGIN": "http://herdoc-web.onrender.com"},
        {"WEB_ORIGIN": "*"},
        {"DATABASE_URL": "sqlite:///./prod.db"},
        {"COOKIE_SECURE": False},
        {"TELEGRAM_BOT_TOKEN": "123:abc-secret-bot-token"},
    ],
)
def test_unsafe_production_settings_fail_without_leaking_secrets(overrides):
    with pytest.raises(ValidationError) as exc_info:
        _prod_settings(**overrides)
    message = str(exc_info.value)
    assert "Unsafe production configuration" in message
    for secret in ("p" * 48, "user:pass", "short-but-secret", "123:abc-secret-bot-token"):
        assert secret not in message


def test_render_defaults_to_production(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValidationError):
        _prod_settings(ENVIRONMENT=None, JWT_SECRET="weak")
    assert _prod_settings(ENVIRONMENT=None).is_production
