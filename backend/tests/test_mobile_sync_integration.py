import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import Patient, Visit, RiskFlag, Review, User
from app.db.seed import seed_demo_data
from app.db.session import get_session_local

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


def _register_worker(admin_token: str):
    phone = f"9{uuid.uuid4().int % 900000000:09d}"
    register = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"ASHA Worker {uuid.uuid4().hex[:6]}", "phone": phone, "temporary_pin": "2468"},
    )
    assert register.status_code == 200, register.text

    login = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"], login.json()["user"]["id"]


def test_offline_sync_lifecycle():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    headers = {"Authorization": f"Bearer {worker_token}"}
    db = get_session_local()()

    try:
        # 1. Simulate mobile offline creation: 1 patient + 3 visits with trend escalation
        patient_id = str(uuid.uuid4())
        visit1_id = str(uuid.uuid4())
        visit2_id = str(uuid.uuid4())
        visit3_id = str(uuid.uuid4())
        flag1_id = str(uuid.uuid4())
        flag2_id = str(uuid.uuid4())
        flag3_id = str(uuid.uuid4())

        patient_payload = {
            "id": patient_id,
            "worker_id": str(worker_id),
            "name": "Kavita Devi",
            "age": 26,
            "village": "Rampur",
            "edd": "2026-12-01",
            "phone": "9876500001",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        visit1 = {
            "id": visit1_id,
            "patient_id": patient_id,
            "worker_id": str(worker_id),
            "visit_date": "2026-08-01",
            "systolic_bp": 110,
            "diastolic_bp": 70,
            "blood_sugar": 90,
            "body_temp_c": 37.0,
            "heart_rate": 72,
            "created_locally_at": datetime.now(timezone.utc).isoformat(),
        }
        flag1 = {
            "id": flag1_id,
            "visit_id": visit1_id,
            "model_risk_level": "green",
            "trend_adjusted_level": "green",
            "trend_reason": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        visit2 = {
            "id": visit2_id,
            "patient_id": patient_id,
            "worker_id": str(worker_id),
            "visit_date": "2026-08-08",
            "systolic_bp": 120,
            "diastolic_bp": 78,
            "blood_sugar": 92,
            "body_temp_c": 37.0,
            "heart_rate": 76,
            "created_locally_at": datetime.now(timezone.utc).isoformat(),
        }
        flag2 = {
            "id": flag2_id,
            "visit_id": visit2_id,
            "model_risk_level": "green",
            "trend_adjusted_level": "green",
            "trend_reason": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        visit3 = {
            "id": visit3_id,
            "patient_id": patient_id,
            "worker_id": str(worker_id),
            "visit_date": "2026-08-15",
            "systolic_bp": 130,
            "diastolic_bp": 86,
            "blood_sugar": 95,
            "body_temp_c": 37.1,
            "heart_rate": 80,
            "created_locally_at": datetime.now(timezone.utc).isoformat(),
        }
        flag3 = {
            "id": flag3_id,
            "visit_id": visit3_id,
            "model_risk_level": "green",
            "trend_adjusted_level": "yellow",
            "trend_reason": "Blood pressure has risen steadily over your last 3 visits.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        sync_batch = {
            "patients": [patient_payload],
            "visits": [visit1, visit2, visit3],
            "risk_flags": [flag1, flag2, flag3],
            "last_synced_at": None,
        }

        # 2. Synchronize batch with backend
        resp = client.post("/api/sync", json=sync_batch, headers=headers)
        assert resp.status_code == 200, f"Sync failed: {resp.text}"
        data = resp.json()

        assert data["patients"]["success"] == 1
        assert data["visits"]["success"] == 3
        assert data["risk_flags"]["success"] == 3
        assert "sync_timestamp" in data

        # 3. Verify in MySQL database
        db_patient = db.get(Patient, uuid.UUID(patient_id))
        assert db_patient is not None
        assert db_patient.name == "Kavita Devi"

        db_visits = db.query(Visit).filter(Visit.patient_id == uuid.UUID(patient_id)).all()
        assert len(db_visits) == 3

        db_flags = db.query(RiskFlag).filter(RiskFlag.visit_id.in_([uuid.UUID(v) for v in [visit1_id, visit2_id, visit3_id]])).all()
        assert len(db_flags) == 3
        escalated_flag = [f for f in db_flags if str(f.id) == flag3_id][0]
        assert escalated_flag.trend_adjusted_level == "yellow"
        assert "Blood pressure has risen" in escalated_flag.trend_reason

        # 4. Test Idempotency: Send the exact same batch again
        resp_repeat = client.post("/api/sync", json=sync_batch, headers=headers)
        assert resp_repeat.status_code == 200
        repeat_data = resp_repeat.json()
        assert repeat_data["patients"]["already_synced"] == 1
        assert repeat_data["visits"]["already_synced"] == 3
        assert repeat_data["risk_flags"]["already_synced"] == 3

        # Confirm total count in MySQL did not duplicate
        total_visits_count = db.query(Visit).filter(Visit.patient_id == uuid.UUID(patient_id)).count()
        assert total_visits_count == 3

        # 5. Test Doctor Review Pull back to mobile
        doctor_resp = client.post(
            "/api/auth/login/doctor",
            json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
        )
        assert doctor_resp.status_code == 200
        doctor_user = doctor_resp.json()["user"]

        review = Review(
            id=uuid.uuid4(),
            patient_id=uuid.UUID(patient_id),
            doctor_id=uuid.UUID(doctor_user["id"]),
            status="referred",
            notes="Referred to District Hospital for antenatal BP management",
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)
        db.commit()

        # Mobile syncs to fetch server updates
        sync_pull = {
            "patients": [],
            "visits": [],
            "risk_flags": [],
            "last_synced_at": data["sync_timestamp"],
        }
        resp_pull = client.post("/api/sync", json=sync_pull, headers=headers)
        assert resp_pull.status_code == 200
        pull_data = resp_pull.json()
        reviews = pull_data.get("reviews", [])
        assert len(reviews) >= 1
        patient_review = [r for r in reviews if r["patient_id"] == patient_id][0]
        assert patient_review["status"] == "referred"
        assert "District Hospital" in patient_review["notes"]

    finally:
        db.close()
