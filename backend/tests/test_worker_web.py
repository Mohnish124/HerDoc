"""Worker web portal: browser phone + PIN login, cookie sessions, and worker-scoped data access."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.api.auth as auth_module
from app.api.auth import COOKIE_NAME, _rate_limiter
from app.config import Settings
from app.db.models import Facility, User, UserRole
from app.db.seed import seed_demo_data
from app.db.session import get_session_local
from app.main import app
from app.services.auth_service import hash_password, hash_pin

PIN = "2580"
WEB_ORIGIN = "https://herdoc-web.onrender.com"


def _db():
    return get_session_local()()


@pytest.fixture(scope="module")
def facility_id():
    db = _db()
    try:
        seed_demo_data(db, commit=True)
        return db.query(Facility).filter(Facility.name == "Demo PHC").one().id
    finally:
        db.close()


def _worker(facility_id, *, active=True) -> User:
    db = _db()
    try:
        user = User(
            id=uuid.uuid4(), role=UserRole.WORKER.value, name=f"Web Worker {uuid.uuid4().hex[:4]}",
            phone=f"8{uuid.uuid4().int % 900000000:09d}", pin_hash=hash_pin(PIN),
            facility_id=facility_id, is_active=active, failed_login_attempts=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _set_cookie_headers(resp):
    return [h for h in resp.headers.get_list("set-cookie") if h.startswith(f"{COOKIE_NAME}=")]


def _web_login(client, worker, pin=PIN):
    return client.post("/api/auth/login/worker/web", json={"phone": worker.phone, "pin": pin})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def production_cookies(monkeypatch):
    settings = Settings(
        _env_file=None, ENVIRONMENT="production", DATABASE_URL="mysql+pymysql://u:p@db.example.org/h",
        JWT_SECRET="w" * 48, WEB_ORIGIN=WEB_ORIGIN, TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="",
    )
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)


# ---------------------------------------------------------------- browser login

def test_worker_web_login_sets_secure_cookie_and_hides_refresh_token(facility_id, production_cookies):
    worker = _worker(facility_id)
    web = TestClient(app, base_url=WEB_ORIGIN)
    resp = _web_login(web, worker)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["role"] == "worker" and body["access_token"]
    assert "refresh_token" not in body
    cookie = _set_cookie_headers(resp)[-1].lower()
    for attribute in ("httponly", "secure", "samesite=strict", "path=/api/auth"):
        assert attribute in cookie, attribute
    assert resp.headers["cache-control"] == "no-store"


def test_mobile_worker_login_is_unchanged(facility_id):
    worker = _worker(facility_id)
    resp = TestClient(app).post("/api/auth/login/worker", json={"phone": worker.phone, "pin": PIN})
    assert resp.status_code == 200
    assert resp.json()["refresh_token"]
    assert not _set_cookie_headers(resp)


def test_worker_web_login_rejects_wrong_pin_without_cookie(facility_id):
    worker = _worker(facility_id)
    resp = _web_login(TestClient(app), worker, pin="9731")
    assert resp.status_code == 401
    assert "access_token" not in resp.json()
    assert not _set_cookie_headers(resp)


def test_worker_web_login_locks_out_after_repeated_failures(facility_id):
    _rate_limiter.clear()
    worker = _worker(facility_id)
    web = TestClient(app)
    for _ in range(4):
        assert _web_login(web, worker, pin="9731").status_code == 401
    locked = _web_login(web, worker, pin="9731")
    assert locked.status_code == 403 and "locked" in locked.json()["detail"].lower()
    # Correct PIN is refused while locked, on both the web and the mobile endpoint.
    assert _web_login(web, worker).status_code == 403
    assert web.post("/api/auth/login/worker", json={"phone": worker.phone, "pin": PIN}).status_code == 403


def test_worker_web_and_mobile_share_one_rate_limit(facility_id):
    _rate_limiter.clear()
    worker = _worker(facility_id)
    key = f"worker:{worker.phone}"
    _rate_limiter[key] = [datetime.now(timezone.utc).timestamp()] * auth_module.LOGIN_RATE_LIMIT_MAX
    assert _web_login(TestClient(app), worker).status_code == 429
    _rate_limiter.clear()


def test_deactivated_worker_cannot_log_in_on_web(facility_id):
    worker = _worker(facility_id, active=False)
    resp = _web_login(TestClient(app), worker)
    assert resp.status_code == 401 and "deactivated" in resp.json()["detail"].lower()
    assert not _set_cookie_headers(resp)


def test_weak_pin_is_rejected_at_registration():
    db = _db()
    try:
        seed_demo_data(db, commit=True)
    finally:
        db.close()
    client = TestClient(app)
    admin = client.post("/api/auth/login/admin", json={"email": "admin@herdoc.local", "password": "AdminPass!2024"}).json()
    for weak in ("1234", "1111", "4321", "1123"):
        resp = client.post(
            "/api/auth/register/worker", headers=_auth(admin["access_token"]),
            json={"name": "Weak", "phone": f"8{uuid.uuid4().int % 900000000:09d}", "temporary_pin": weak},
        )
        assert resp.status_code == 400, weak


def test_demo_worker_phone_blocked_on_web_in_production(facility_id, production_cookies):
    resp = TestClient(app).post("/api/auth/login/worker/web", json={"phone": "9000000003", "pin": "2468"})
    assert resp.status_code == 401
    assert not _set_cookie_headers(resp)


# ---------------------------------------------------------------- sessions

def test_worker_cookie_refresh_rotates_and_keeps_role(facility_id):
    worker = _worker(facility_id)
    web = TestClient(app)
    assert _web_login(web, worker).status_code == 200
    first = web.cookies.get(COOKIE_NAME)
    refreshed = web.post("/api/auth/refresh", json={})
    assert refreshed.status_code == 200
    assert refreshed.json()["user"]["role"] == "worker"
    assert "refresh_token" not in refreshed.json()
    assert web.cookies.get(COOKIE_NAME) != first
    replay = TestClient(app).post("/api/auth/refresh", json={}, headers={"Cookie": f"{COOKIE_NAME}={first}"})
    assert replay.status_code == 401


def test_worker_web_logout_ends_only_the_browser_session(facility_id):
    worker = _worker(facility_id)
    mobile = TestClient(app).post("/api/auth/login/worker", json={"phone": worker.phone, "pin": PIN}).json()
    web = TestClient(app)
    assert _web_login(web, worker).status_code == 200
    web_cookie = web.cookies.get(COOKIE_NAME)

    logout = web.post("/api/auth/logout", json={})
    assert logout.status_code == 200
    assert "max-age=0" in _set_cookie_headers(logout)[-1].lower()

    # The browser session is revoked...
    stale = TestClient(app).post("/api/auth/refresh", json={}, headers={"Cookie": f"{COOKIE_NAME}={web_cookie}"})
    assert stale.status_code == 401
    # ...but the mobile app's session keeps working (offline-first sync).
    still_mobile = TestClient(app).post("/api/auth/refresh", json={"refresh_token": mobile["refresh_token"]})
    assert still_mobile.status_code == 200


def test_doctor_web_logout_still_revokes_all_sessions(facility_id):
    db = _db()
    try:
        email = f"doc-{uuid.uuid4().hex[:6]}@example.org"
        db.add(User(id=uuid.uuid4(), role=UserRole.DOCTOR.value, name="Doc", email=email,
                    password_hash=hash_password("Doctor-Pass-2026"), facility_id=facility_id,
                    is_active=True, failed_login_attempts=0))
        db.commit()
    finally:
        db.close()
    other = TestClient(app).post("/api/auth/login/doctor", json={"email": email, "password": "Doctor-Pass-2026"}).json()
    web = TestClient(app)
    assert web.post("/api/auth/login/web", json={"email": email, "password": "Doctor-Pass-2026"}).status_code == 200
    assert web.post("/api/auth/logout", json={}).status_code == 200
    assert TestClient(app).post("/api/auth/refresh", json={"refresh_token": other["refresh_token"]}).status_code == 401


# ---------------------------------------------------------------- role and data scope

def test_worker_web_token_is_rejected_by_staff_endpoints(facility_id):
    worker = _worker(facility_id)
    token = _web_login(TestClient(app), worker).json()["access_token"]
    client = TestClient(app)
    for method, path, body in [
        ("get", "/api/dashboard/flagged", None),
        ("get", "/api/dashboard/facility-overview", None),
        ("get", "/api/dashboard/filters", None),
        ("get", "/api/workers", None),
        ("post", "/api/reviews", {"patient_id": str(uuid.uuid4()), "status": "reviewed"}),
        ("post", "/api/auth/register/worker", {"name": "x", "phone": "8123456789", "temporary_pin": "2580"}),
        ("post", "/api/auth/register/doctor", {"name": "x", "email": "x@example.org", "password": "Doctor-Pass-2026"}),
        ("post", "/api/auth/register/admin", {"name": "x", "email": "y@example.org", "password": "Doctor-Pass-2026"}),
    ]:
        resp = getattr(client, method)(path, headers=_auth(token), **({"json": body} if body else {}))
        assert resp.status_code == 403, (path, resp.status_code)


def _patient_payload(name="Web Patient"):
    return {"id": str(uuid.uuid4()), "name": name, "age": 26, "village": "Rampur", "edd": "2026-12-15", "phone": None}


def _visit_payload(patient_id, worker_id, level="yellow"):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()), "patient_id": patient_id, "worker_id": worker_id, "visit_date": now,
        "systolic_bp": 132, "diastolic_bp": 86, "blood_sugar": 95, "body_temp_c": 37.0, "heart_rate": 82,
        "created_locally_at": now,
        "risk_flags": [{"id": str(uuid.uuid4()), "model_risk_level": "green", "trend_adjusted_level": level,
                        "trend_reason": "Blood pressure has risen steadily."}],
    }


def test_worker_registers_patient_and_records_visit_through_web_session(facility_id):
    worker = _worker(facility_id)
    login = _web_login(TestClient(app), worker).json()
    headers = _auth(login["access_token"])
    client = TestClient(app)

    patient = client.post("/api/patients", headers=headers, json=_patient_payload())
    assert patient.status_code == 200, patient.text
    pid = patient.json()["id"]
    assert patient.json()["worker_id"] == login["user"]["id"]

    visit = client.post(f"/api/patients/{pid}/visits", headers=headers, json=_visit_payload(pid, login["user"]["id"]))
    assert visit.status_code == 200, visit.text
    assert visit.json()["risk_flags"][0]["trend_adjusted_level"] == "yellow"

    listed = client.get("/api/patients", headers=headers).json()
    assert [p["id"] for p in listed] == [pid]
    history = client.get(f"/api/patients/{pid}/visits", headers=headers).json()
    assert len(history) == 1 and history[0]["systolic_bp"] == 132

    # Reviews for the worker's own patients come from the existing sync endpoint (empty batch writes nothing).
    sync = client.post("/api/sync", headers=headers, json={"patients": [], "visits": [], "risk_flags": [], "last_synced_at": None})
    assert sync.status_code == 200 and sync.json()["patients"] == {"success": 0, "updated": 0, "already_synced": 0, "failed": 0}


def test_worker_cannot_reach_another_workers_patient(facility_id):
    owner = _worker(facility_id)
    other = _worker(facility_id)  # same facility: workers are scoped to their own patients
    owner_login = _web_login(TestClient(app), owner).json()
    other_login = _web_login(TestClient(app), other).json()
    client = TestClient(app)
    pid = client.post("/api/patients", headers=_auth(owner_login["access_token"]), json=_patient_payload()).json()["id"]

    h = _auth(other_login["access_token"])
    assert client.get(f"/api/patients/{pid}", headers=h).status_code == 403
    assert client.get(f"/api/patients/{pid}/visits", headers=h).status_code == 403
    assert pid not in {p["id"] for p in client.get("/api/patients", headers=h).json()}
    assert client.post(f"/api/patients/{pid}/visits", headers=h, json=_visit_payload(pid, other_login["user"]["id"])).status_code == 403
    # Re-registering the same patient id under another worker is refused.
    taken = dict(_patient_payload(), id=pid)
    assert client.post("/api/patients", headers=h, json=taken).status_code == 403
    # A visit claiming to be by another worker is refused.
    assert client.post(f"/api/patients/{pid}/visits", headers=_auth(owner_login["access_token"]),
                       json=_visit_payload(pid, other_login["user"]["id"])).status_code == 400
