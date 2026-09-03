import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.seed import seed_demo_data
from app.db.session import get_session_local

client = TestClient(app)


def _seed_db():
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)
    finally:
        db.close()


def test_doctor_web_login_sets_cookie_and_returns_memory_token():
    _seed_db()

    response = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert "access_token" in data
    assert data["user"]["role"] == "doctor"
    assert "herdoc_refresh_token" in response.cookies

    # Test silent refresh via cookie (no body)
    refresh_resp = client.post("/api/auth/refresh", json={})
    assert refresh_resp.status_code == 200, refresh_resp.text
    refresh_data = refresh_resp.json()
    assert "access_token" in refresh_data
    assert refresh_data["user"]["role"] == "doctor"
    assert "herdoc_refresh_token" in refresh_resp.cookies

    # Test authenticated request with access token
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh_data['access_token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "doctor@herdoc.local"

    # Test logout via cookie
    logout_resp = client.post("/api/auth/logout", json={})
    assert logout_resp.status_code == 200

    # Old token / cookie is now revoked
    failed_refresh = client.post("/api/auth/refresh", json={})
    assert failed_refresh.status_code == 401


def test_admin_web_login_and_role_access():
    _seed_db()

    response = client.post(
        "/api/auth/login/admin",
        json={"email": "admin@herdoc.local", "password": "AdminPass!2024"},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["user"]["role"] == "admin"
    assert "herdoc_refresh_token" in response.cookies
    token = data["access_token"]

    # Verify admin can call worker registration with unique phone
    unique_phone = f"95{uuid.uuid4().int % 100000000:08d}"
    reg_resp = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "New Worker", "phone": unique_phone, "temporary_pin": "2468"},
    )
    assert reg_resp.status_code == 200


def test_doctor_cannot_access_admin_worker_registration():
    _seed_db()

    doc_resp = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert doc_resp.status_code == 200
    doc_token = doc_resp.json()["access_token"]

    # Doctor attempting admin endpoint must get 403 Forbidden
    unique_phone = f"96{uuid.uuid4().int % 100000000:08d}"
    reg_resp = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"name": "Forbidden Worker", "phone": unique_phone, "temporary_pin": "2468"},
    )
    assert reg_resp.status_code == 403
