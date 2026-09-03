import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import Facility, User, UserRole
from app.db.seed import seed_demo_data
from app.db.session import get_session_local

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_test_context():
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)
        admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR.value).first()
        worker = db.query(User).filter(User.role == UserRole.WORKER.value).first()

        return {
            "admin_email": "admin@herdoc.local",
            "admin_password": "AdminPass!2024",
            "doctor_email": "doctor@herdoc.local",
            "doctor_password": "DoctorPass!2024",
            "existing_worker_phone": worker.phone,
        }
    finally:
        db.close()


def test_admin_worker_lifecycle_create_login_deactivate_block(admin_test_context):
    ctx = admin_test_context

    # 1. Admin Login
    admin_login = client.post(
        "/api/auth/login/admin",
        json={"email": ctx["admin_email"], "password": ctx["admin_password"]},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin creates a new field worker with temporary PIN
    temp_pin = "3579"
    new_phone = f"98{uuid.uuid4().int % 100000000:08d}"
    worker_name = "ASHA Meera"

    create_resp = client.post(
        "/api/auth/register/worker",
        headers=admin_headers,
        json={
            "name": worker_name,
            "phone": new_phone,
            "temporary_pin": temp_pin,
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    worker_data = create_resp.json()["user"]
    worker_id = worker_data["id"]

    # 3. Worker logs in on mobile using phone + temporary PIN
    worker_login = client.post(
        "/api/auth/login/worker",
        json={"phone": new_phone, "pin": temp_pin},
    )
    assert worker_login.status_code == 200
    worker_token = worker_login.json()["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    # Verify worker can access mobile me endpoint
    me_resp = client.get("/api/auth/me", headers=worker_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["name"] == worker_name

    # 4. Admin lists workers and verifies new worker is present and active
    list_resp = client.get("/api/workers", headers=admin_headers)
    assert list_resp.status_code == 200
    worker_entries = list_resp.json()
    created_entry = next((w for w in worker_entries if w["id"] == worker_id), None)
    assert created_entry is not None
    assert created_entry["is_active"] is True
    assert "pin" not in created_entry  # PIN is never exposed in listing

    # 5. Admin deactivates worker
    deactivate_resp = client.patch(
        f"/api/workers/{worker_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    # 6. Deactivated worker attempts mobile login -> Rejected (401)
    failed_login = client.post(
        "/api/auth/login/worker",
        json={"phone": new_phone, "pin": temp_pin},
    )
    assert failed_login.status_code == 401
    assert "deactivated" in failed_login.json()["detail"].lower()

    # 7. Old access token for deactivated worker is rejected on protected endpoints (403)
    blocked_me = client.get("/api/auth/me", headers=worker_headers)
    assert blocked_me.status_code == 403

    # 8. Admin reactivates worker
    reactivate_resp = client.patch(
        f"/api/workers/{worker_id}/status",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_active"] is True

    # 9. Reactivated worker can log in again
    relogin_resp = client.post(
        "/api/auth/login/worker",
        json={"phone": new_phone, "pin": temp_pin},
    )
    assert relogin_resp.status_code == 200


def test_doctor_cannot_access_worker_management(admin_test_context):
    ctx = admin_test_context

    # Login as Doctor
    doc_login = client.post(
        "/api/auth/login/doctor",
        json={"email": ctx["doctor_email"], "password": ctx["doctor_password"]},
    )
    assert doc_login.status_code == 200
    doc_token = doc_login.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Doctor trying to list workers -> 403 Forbidden
    list_resp = client.get("/api/workers", headers=doc_headers)
    assert list_resp.status_code == 403

    # Doctor trying to register worker -> 403 Forbidden
    reg_resp = client.post(
        "/api/auth/register/worker",
        headers=doc_headers,
        json={"name": "Forbidden Worker", "phone": "9998887776", "temporary_pin": "1234"},
    )
    assert reg_resp.status_code == 403

    # Doctor trying to update worker status -> 403 Forbidden
    patch_resp = client.patch(
        f"/api/workers/{uuid.uuid4()}/status",
        headers=doc_headers,
        json={"is_active": False},
    )
    assert patch_resp.status_code == 403


def test_worker_cannot_access_worker_management(admin_test_context):
    ctx = admin_test_context

    # Login as Worker
    worker_login = client.post(
        "/api/auth/login/worker",
        json={"phone": ctx["existing_worker_phone"], "pin": "2468"},
    )
    assert worker_login.status_code == 200
    worker_token = worker_login.json()["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    # Worker trying to list workers -> 403 Forbidden
    list_resp = client.get("/api/workers", headers=worker_headers)
    assert list_resp.status_code == 403

    # Worker trying to register worker -> 403 Forbidden
    reg_resp = client.post(
        "/api/auth/register/worker",
        headers=worker_headers,
        json={"name": "Forbidden Worker", "phone": "9998887775", "temporary_pin": "1234"},
    )
    assert reg_resp.status_code == 403

    # Worker trying to update worker status -> 403 Forbidden
    patch_resp = client.patch(
        f"/api/workers/{uuid.uuid4()}/status",
        headers=worker_headers,
        json={"is_active": False},
    )
    assert patch_resp.status_code == 403
