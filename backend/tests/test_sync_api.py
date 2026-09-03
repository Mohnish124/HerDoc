import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db.models import Patient, Review, ReviewStatus, RiskFlag, RiskLevel, Visit
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
    phone = phone or f"9{uuid.uuid4().int % 900000000:09d}"
    register = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"Worker {uuid.uuid4().hex[:6]}", "phone": phone, "temporary_pin": "2468"},
    )
    assert register.status_code == 200, register.text

    login = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"], login.json()["user"]["id"]


def _login_doctor():
    response = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_sync_new_patient():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = str(uuid.uuid4())

    response = client.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patients": [{
                "id": patient_id,
                "worker_id": worker_id,
                "name": "Sync Patient",
                "age": 31,
                "village": "Village A",
                "edd": "2026-12-01",
                "phone": "2223334444",
            }],
            "visits": [],
            "risk_flags": [],
            "last_synced_at": "2026-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patients"]["success"] == 1
    assert payload["patients"]["failed"] == 0
    assert payload["sync_timestamp"]
    db = get_session_local()()
    try:
        patient = db.query(Patient).filter(Patient.id == uuid.UUID(patient_id)).first()
        assert patient is not None
        assert patient.worker_id == uuid.UUID(worker_id)
    finally:
        db.close()


def test_sync_new_patient_visit_and_risk_flag():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = str(uuid.uuid4())
    visit_id = str(uuid.uuid4())
    risk_id = str(uuid.uuid4())

    response = client.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patients": [{
                "id": patient_id,
                "worker_id": worker_id,
                "name": "Patient With Visit",
                "age": 32,
                "village": "Village B",
                "edd": "2026-11-15",
                "phone": "1234567890",
            }],
            "visits": [{
                "id": visit_id,
                "patient_id": patient_id,
                "worker_id": worker_id,
                "visit_date": "2026-08-17",
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "blood_sugar": 94,
                "body_temp_c": 36.7,
                "heart_rate": 72,
                "created_locally_at": "2026-08-17T09:00:00+00:00",
            }],
            "risk_flags": [{
                "id": risk_id,
                "visit_id": visit_id,
                "model_risk_level": "yellow",
                "trend_adjusted_level": "red",
                "trend_reason": "trending upward",
            }],
            "last_synced_at": "2026-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patients"]["success"] == 1
    assert payload["visits"]["success"] == 1
    assert payload["risk_flags"]["success"] == 1

    db = get_session_local()()
    try:
        patient = db.query(Patient).filter(Patient.id == uuid.UUID(patient_id)).first()
        visit = db.query(Visit).filter(Visit.id == uuid.UUID(visit_id)).first()
        risk = db.query(RiskFlag).filter(RiskFlag.id == uuid.UUID(risk_id)).first()
        assert patient is not None
        assert visit is not None and visit.patient_id == uuid.UUID(patient_id)
        assert risk is not None and risk.visit_id == uuid.UUID(visit_id)
    finally:
        db.close()


def test_sync_same_batch_twice_is_idempotent():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = str(uuid.uuid4())
    visit_id = str(uuid.uuid4())
    risk_id = str(uuid.uuid4())
    payload = {
        "patients": [{
            "id": patient_id,
            "worker_id": worker_id,
            "name": "Idempotent Patient",
            "age": 28,
            "village": "Village C",
            "edd": "2026-10-04",
            "phone": "3334445555",
        }],
        "visits": [{
            "id": visit_id,
            "patient_id": patient_id,
            "worker_id": worker_id,
            "visit_date": "2026-08-19",
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "created_locally_at": "2026-08-19T10:00:00+00:00",
        }],
        "risk_flags": [{
            "id": risk_id,
            "visit_id": visit_id,
            "model_risk_level": "green",
            "trend_adjusted_level": "green",
        }],
        "last_synced_at": "2026-01-01T00:00:00Z",
    }

    first = client.post("/api/sync", headers={"Authorization": f"Bearer {worker_token}"}, json=payload)
    second = client.post("/api/sync", headers={"Authorization": f"Bearer {worker_token}"}, json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["patients"]["already_synced"] == 1
    assert second.json()["visits"]["already_synced"] == 1
    assert second.json()["risk_flags"]["already_synced"] == 1

    db = get_session_local()()
    try:
        patient_count = db.query(Patient).filter(Patient.id == uuid.UUID(patient_id)).count()
        visit_count = db.query(Visit).filter(Visit.id == uuid.UUID(visit_id)).count()
        risk_count = db.query(RiskFlag).filter(RiskFlag.id == uuid.UUID(risk_id)).count()
        assert patient_count == 1
        assert visit_count == 1
        assert risk_count == 1
    finally:
        db.close()


def test_sync_patient_and_visit_in_same_request():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = str(uuid.uuid4())
    visit_id = str(uuid.uuid4())

    response = client.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patients": [{
                "id": patient_id,
                "worker_id": worker_id,
                "name": "Same Request Patient",
                "age": 40,
                "village": "Village D",
                "edd": "2026-09-09",
                "phone": "7778889999",
            }],
            "visits": [{
                "id": visit_id,
                "patient_id": patient_id,
                "worker_id": worker_id,
                "visit_date": "2026-08-18",
                "systolic_bp": 132,
                "created_locally_at": "2026-08-18T11:00:00+00:00",
            }],
            "risk_flags": [],
            "last_synced_at": "2026-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patients"]["success"] == 1
    assert payload["visits"]["success"] == 1

    db = get_session_local()()
    try:
        patient = db.query(Patient).filter(Patient.id == uuid.UUID(patient_id)).first()
        visit = db.query(Visit).filter(Visit.id == uuid.UUID(visit_id)).first()
        assert patient is not None
        assert visit is not None and visit.patient_id == patient.id
    finally:
        db.close()


def test_sync_risk_flag_references_visit_in_same_request():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = str(uuid.uuid4())
    visit_id = str(uuid.uuid4())
    risk_id = str(uuid.uuid4())

    response = client.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patients": [{
                "id": patient_id,
                "worker_id": worker_id,
                "name": "Risk Permission Patient",
                "age": 33,
                "village": "Village E",
                "edd": "2026-09-02",
                "phone": "5556667777",
            }],
            "visits": [{
                "id": visit_id,
                "patient_id": patient_id,
                "worker_id": worker_id,
                "visit_date": "2026-08-20",
                "created_locally_at": "2026-08-20T12:00:00+00:00",
            }],
            "risk_flags": [{
                "id": risk_id,
                "visit_id": visit_id,
                "model_risk_level": "red",
                "trend_adjusted_level": "red",
            }],
            "last_synced_at": "2026-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["risk_flags"]["success"] == 1


def test_sync_partial_invalid_batch_records_failed_without_losing_data():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    valid_patient_id = str(uuid.uuid4())
    invalid_patient_id = str(uuid.uuid4())

    response = client.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patients": [
                {
                    "id": valid_patient_id,
                    "worker_id": worker_id,
                    "name": "Good Patient",
                    "age": 25,
                    "village": "Village F",
                    "edd": "2026-09-18",
                    "phone": "1112223333",
                },
                {
                    "id": invalid_patient_id,
                    "worker_id": worker_id,
                    "name": "",
                    "age": 0,
                    "village": "",
                    "edd": "not-a-date",
                    "phone": "bad",
                },
            ],
            "visits": [],
            "risk_flags": [],
            "last_synced_at": "2026-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patients"]["success"] == 1
    assert payload["patients"]["failed"] >= 1

    db = get_session_local()()
    try:
        patient = db.query(Patient).filter(Patient.id == uuid.UUID(valid_patient_id)).first()
        assert patient is not None
    finally:
        db.close()


def test_sync_returns_doctor_review_updates_for_worker_patients():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    doctor_token = _login_doctor()
    patient_id = str(uuid.uuid4())

    patient_payload = {
        "patients": [{
            "id": patient_id,
            "worker_id": worker_id,
            "name": "Reviewed Patient",
            "age": 29,
            "village": "Village G",
            "edd": "2026-11-20",
            "phone": "9990001111",
        }],
        "visits": [],
        "risk_flags": [],
        "last_synced_at": "2026-01-01T00:00:00Z",
    }
    sync_ok = client.post("/api/sync", headers={"Authorization": f"Bearer {worker_token}"}, json=patient_payload)
    assert sync_ok.status_code == 200, sync_ok.text

    db = get_session_local()()
    try:
        doctor = db.query(type('User', (), {})).filter().first() if False else None
        from app.db.models import User

        doctor_user = db.query(User).filter(User.email == "doctor@herdoc.local").first()
        patient = db.query(Patient).filter(Patient.id == uuid.UUID(patient_id)).first()
        review = Review(
            id=uuid.uuid4(),
            patient_id=patient.id,
            doctor_id=doctor_user.id,
            status=ReviewStatus.APPROVED.value,
            notes="Approved after review",
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)
        db.commit()
    finally:
        db.close()

    last_synced_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    response = client.post(
        "/api/sync",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patients": [],
            "visits": [],
            "risk_flags": [],
            "last_synced_at": last_synced_at,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    review_updates = payload.get("server_updates", {}).get("reviews", payload.get("reviews", []))
    assert review_updates
    assert any(item["patient_id"] == patient_id and item["status"] == ReviewStatus.APPROVED.value for item in review_updates)
