import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.models import User, UserRole
from app.db.seed import seed_demo_data
from app.db.session import get_session_local
from app.main import app
from app.services.auth_service import hash_password, hash_pin

client = TestClient(app)


def _unique_phone() -> str:
    return str(9000000000 + (uuid.uuid4().int % 9000000))


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@herdoc.local"


@pytest.fixture
def demo_admin_token() -> str:
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)
    finally:
        db.close()

    response = client.post(
        "/api/auth/login/admin",
        json={"email": "admin@herdoc.local", "password": "AdminPass!2024"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_worker_register_login_refresh_logout_flow(demo_admin_token):
    phone = _unique_phone()
    pin = "2468"

    register = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {demo_admin_token}"},
        json={"name": "Worker One", "phone": phone, "temporary_pin": pin},
    )
    assert register.status_code == 200, register.text
    data = register.json()
    assert data["user"]["role"] == "worker"
    assert data["user"]["phone"] == phone

    login = client.post(
        "/api/auth/login/worker",
        json={"phone": phone, "pin": pin},
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    refreshed_payload = refreshed.json()
    assert refreshed_payload["refresh_token"] != tokens["refresh_token"]

    logout = client.post(
        "/api/auth/logout",
        json={"refresh_token": refreshed_payload["refresh_token"]},
    )
    assert logout.status_code == 200, logout.text


def test_admin_register_login_refresh_logout_flow():
    email = _unique_email("admin")
    password = "StrongAdmin!2024"

    register = client.post(
        "/api/auth/register/admin",
        json={"name": "New Admin", "email": email, "password": password},
    )
    assert register.status_code == 200, register.text

    login = client.post(
        "/api/auth/login/admin",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200, refreshed.text

    log_out = client.post("/api/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]})
    assert log_out.status_code == 200, log_out.text

    protected = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert protected.status_code == 200, protected.text


def test_doctor_register_login_refresh_logout_flow(demo_admin_token):
    email = _unique_email("doctor")
    password = "StrongDoctor!2024"

    register = client.post(
        "/api/auth/register/doctor",
        headers={"Authorization": f"Bearer {demo_admin_token}"},
        json={"name": "Dr. Kim", "email": email, "password": password},
    )
    assert register.status_code == 200, register.text

    login = client.post(
        "/api/auth/login/doctor",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["role"] == "doctor"

    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert refreshed.status_code == 200, refreshed.text

    logout = client.post(
        "/api/auth/logout",
        json={"refresh_token": refreshed.json()["refresh_token"]},
    )
    assert logout.status_code == 200, logout.text


def test_invalid_credentials_and_weak_password_and_pin(demo_admin_token):
    weak_pw = client.post(
        "/api/auth/register/doctor",
        headers={"Authorization": f"Bearer {demo_admin_token}"},
        json={"name": "Weak Doc", "email": _unique_email("weak_pw"), "password": "Password123"},
    )
    assert weak_pw.status_code == 400

    weak_pin = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {demo_admin_token}"},
        json={"name": "Weak Worker", "phone": _unique_phone(), "temporary_pin": "1234"},
    )
    assert weak_pin.status_code == 400

    wrong_worker = client.post(
        "/api/auth/login/worker",
        json={"phone": _unique_phone(), "pin": "9999"},
    )
    assert wrong_worker.status_code in {401, 403}

    wrong_doctor = client.post(
        "/api/auth/login/doctor",
        json={"email": _unique_email("bad_doctor"), "password": "NopeWrong!2024"},
    )
    assert wrong_doctor.status_code in {401, 403}


def test_account_lock_after_5_failed_attempts():
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)
        phone = _unique_phone()
        facility = db.query(User).filter_by(email="admin@herdoc.local").first().facility
        user = User(
            id=uuid.uuid4(),
            role=UserRole.WORKER.value,
            name="Lockout Worker",
            phone=phone,
            email=None,
            facility_id=facility.id,
            password_hash=None,
            pin_hash=hash_pin("2468"),
            failed_login_attempts=0,
            is_active=True,
            locked_until=None,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    for _ in range(4):
        resp = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "9999"})
        assert resp.status_code in {401, 403}

    locked = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "9999"})
    assert locked.status_code == 403
    assert "locked" in locked.json()["detail"].lower()

    unlocked = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    assert unlocked.status_code == 403


def test_refresh_token_rotation_and_revoked_token(demo_admin_token):
    phone = _unique_phone()
    client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {demo_admin_token}"},
        json={"name": "Rotation Worker", "phone": phone, "temporary_pin": "2468"},
    )

    login = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    first_refresh = login.json()["refresh_token"]

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
    assert refreshed.status_code == 200, refreshed.text
    second_refresh = refreshed.json()["refresh_token"]
    assert second_refresh != first_refresh

    replay = client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
    assert replay.status_code in {401, 403}

    logout = client.post("/api/auth/logout", json={"refresh_token": second_refresh})
    assert logout.status_code == 200, logout.text

    replay_after_logout = client.post("/api/auth/refresh", json={"refresh_token": second_refresh})
    assert replay_after_logout.status_code in {401, 403}
