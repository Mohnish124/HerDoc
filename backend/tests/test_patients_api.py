import uuid

from fastapi.testclient import TestClient

from app.db.models import User
from app.db.seed import seed_demo_data
from app.db.session import get_session_local
from app.main import app

client = TestClient(app)


def _seed_and_login_admin():
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


def _register_worker(admin_token: str, phone: str | None = None):
    phone = phone or f"900{uuid.uuid4().int % 1000000000:09d}"
    register = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"Worker {uuid.uuid4().hex[:6]}", "phone": phone, "temporary_pin": "2468"},
    )
    assert register.status_code == 200, register.text

    login = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"], phone


def test_worker_can_create_patient():
    admin_token = _seed_and_login_admin()
    worker_token, _ = _register_worker(admin_token)

    patient_id = str(uuid.uuid4())
    response = client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "id": patient_id,
            "name": "Patient Alpha",
            "age": 32,
            "village": "Rangoon",
            "edd": "2026-10-12",
            "phone": "9876543210",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == patient_id
    assert data["name"] == "Patient Alpha"
    assert data["worker_id"]


def test_worker_can_only_see_own_patients():
    admin_token = _seed_and_login_admin()
    worker1_token, phone1 = _register_worker(admin_token)
    worker2_token, phone2 = _register_worker(admin_token)

    patient_a = {
        "id": str(uuid.uuid4()),
        "name": "Owning Patient",
        "age": 28,
        "village": "A",
        "edd": "2026-09-01",
        "phone": "1111111111",
    }
    patient_b = {
        "id": str(uuid.uuid4()),
        "name": "Other Patient",
        "age": 35,
        "village": "B",
        "edd": "2026-11-01",
        "phone": "2222222222",
    }

    r1 = client.post("/api/patients", headers={"Authorization": f"Bearer {worker1_token}"}, json=patient_a)
    r2 = client.post("/api/patients", headers={"Authorization": f"Bearer {worker2_token}"}, json=patient_b)
    assert r1.status_code == 200
    assert r2.status_code == 200

    listing = client.get("/api/patients", headers={"Authorization": f"Bearer {worker1_token}"})
    assert listing.status_code == 200, listing.text
    ids = {item["id"] for item in listing.json()}
    assert patient_a["id"] in ids
    assert patient_b["id"] not in ids


def test_doctor_can_see_facility_patients():
    admin_token = _seed_and_login_admin()
    worker_token, _ = _register_worker(admin_token)
    doctor_login = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert doctor_login.status_code == 200, doctor_login.text
    doctor_token = doctor_login.json()["access_token"]

    patient = {
        "id": str(uuid.uuid4()),
        "name": "Facility Patient",
        "age": 41,
        "village": "Center",
        "edd": "2026-12-10",
        "phone": "3333333333",
    }
    create = client.post("/api/patients", headers={"Authorization": f"Bearer {worker_token}"}, json=patient)
    assert create.status_code == 200, create.text

    listing = client.get("/api/patients", headers={"Authorization": f"Bearer {doctor_token}"})
    assert listing.status_code == 200, listing.text
    ids = {item["id"] for item in listing.json()}
    assert patient["id"] in ids


def test_unauthorized_users_rejected():
    admin_token = _seed_and_login_admin()
    doctor_login = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert doctor_login.status_code == 200
    doctor_token = doctor_login.json()["access_token"]

    missing = client.post(
        "/api/patients",
        json={
            "id": str(uuid.uuid4()),
            "name": "Nope",
            "age": 20,
            "village": "X",
            "edd": "2026-05-01",
            "phone": "4444444444",
        },
    )
    assert missing.status_code in {401, 403}

    doctor_create = client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "id": str(uuid.uuid4()),
            "name": "Doctor Not Allowed",
            "age": 20,
            "village": "X",
            "edd": "2026-05-01",
            "phone": "5555555555",
        },
    )
    assert doctor_create.status_code in {401, 403}


def test_duplicate_uuid_is_idempotent():
    admin_token = _seed_and_login_admin()
    worker_token, _ = _register_worker(admin_token)
    payload = {
        "id": str(uuid.uuid4()),
        "name": "Duplicate Patient",
        "age": 46,
        "village": "Dupville",
        "edd": "2026-06-20",
        "phone": "6666666666",
    }

    first = client.post("/api/patients", headers={"Authorization": f"Bearer {worker_token}"}, json=payload)
    second = client.post("/api/patients", headers={"Authorization": f"Bearer {worker_token}"}, json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == payload["id"]
    assert second.json()["id"] == payload["id"]

    listing = client.get("/api/patients", headers={"Authorization": f"Bearer {worker_token}"})
    assert listing.status_code == 200, listing.text
    created = [item for item in listing.json() if item["id"] == payload["id"]]
    assert len(created) == 1


def test_invalid_input_rejected():
    admin_token = _seed_and_login_admin()
    worker_token, _ = _register_worker(admin_token)

    bad_age = client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "id": str(uuid.uuid4()),
            "name": "Bad Age",
            "age": 0,
            "village": "X",
            "edd": "2026-05-01",
            "phone": "7777777777",
        },
    )
    assert bad_age.status_code == 422

    missing_name = client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "id": str(uuid.uuid4()),
            "name": "",
            "age": 21,
            "village": "X",
            "edd": "2026-05-01",
            "phone": "8888888888",
        },
    )
    assert missing_name.status_code == 422

    bad_edd = client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "id": str(uuid.uuid4()),
            "name": "Bad EDD",
            "age": 21,
            "village": "X",
            "edd": "not-a-date",
            "phone": "9999999999",
        },
    )
    assert bad_edd.status_code == 422
