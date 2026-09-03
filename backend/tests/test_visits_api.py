import uuid
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.db.models import Patient, RiskFlag, RiskLevel, User, UserRole, Visit
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


def _unique_phone():
    return f"9{uuid.uuid4().int % 900000000:09d}"


def _register_worker(admin_token: str, phone: str | None = None):
    phone = phone or _unique_phone()
    register = client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": f"Worker {uuid.uuid4().hex[:6]}", "phone": phone, "temporary_pin": "2468"},
    )
    assert register.status_code == 200, register.text

    login = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"], login.json()["user"]["id"]


def _create_patient(worker_token: str):
    patient_id = str(uuid.uuid4())
    create = client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "id": patient_id,
            "name": f"Patient {uuid.uuid4().hex[:6]}",
            "age": 29,
            "village": "Village X",
            "edd": "2026-10-01",
            "phone": _unique_phone(),
        },
    )
    assert create.status_code == 200, create.text
    return patient_id


def _login_doctor():
    login = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _visit_payload(patient_id: str, worker_id: str):
    visit_id = str(uuid.uuid4())
    risk_id = str(uuid.uuid4())
    payload = {
        "id": visit_id,
        "patient_id": patient_id,
        "worker_id": worker_id,
        "visit_date": "2026-08-15T09:30:00+00:00",
        "systolic_bp": 125,
        "diastolic_bp": 82,
        "blood_sugar": 98,
        "body_temp_c": 36.9,
        "heart_rate": 74,
        "created_locally_at": "2026-08-15T09:35:00+00:00",
        "risk_flags": [
            {
                "id": risk_id,
                "model_risk_level": "green",
                "trend_adjusted_level": "yellow",
                "trend_reason": "  trending stable  ",
            }
        ],
    }
    return payload, visit_id, risk_id


def test_worker_can_create_visit_with_risk_flags_preserving_uuid():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)

    payload, visit_id, risk_id = _visit_payload(patient_id, worker_id)

    response = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == visit_id
    assert data["patient_id"] == patient_id
    assert data["worker_id"] == worker_id
    assert data["systolic_bp"] == 125
    assert data["body_temp_c"] == 36.9
    assert data["created_locally_at"]
    assert data["synced_at"] is not None
    assert len(data["risk_flags"]) == 1
    assert data["risk_flags"][0]["id"] == risk_id
    assert data["risk_flags"][0]["visit_id"] == visit_id
    assert data["risk_flags"][0]["model_risk_level"] == "green"
    assert data["risk_flags"][0]["trend_adjusted_level"] == "yellow"
    assert data["risk_flags"][0]["trend_reason"] == "trending stable"


def test_worker_can_fetch_patient_visits_with_risk_flags():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)

    db = get_session_local()()
    try:
        worker_user = db.query(User).filter(User.id == uuid.UUID(worker_id)).first()
        assert worker_user is not None

        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            worker_id=worker_user.id,
            name="Visit Patient",
            age=29,
            village="North Arc",
            edd=date(2026, 8, 12),
            phone=_unique_phone(),
        )
        visit = Visit(
            id=uuid.uuid4(),
            patient_id=patient.id,
            worker_id=worker_user.id,
            visit_date=date(2026, 7, 21),
            systolic_bp=120,
            diastolic_bp=80,
            blood_sugar=95,
            body_temp_c=36.8,
            heart_rate=72,
            created_locally_at=datetime(2026, 7, 21, 9, 30, tzinfo=timezone.utc),
        )
        risk = RiskFlag(
            id=uuid.uuid4(),
            visit_id=visit.id,
            model_risk_level=RiskLevel.YELLOW.value,
            trend_adjusted_level=RiskLevel.RED.value,
            trend_reason="trending upward",
        )
        db.add_all([patient, visit, risk])
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/patients/{patient_id}/visits", headers={"Authorization": f"Bearer {worker_token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["patient_id"] == str(patient_id)
    assert payload[0]["systolic_bp"] == 120
    assert payload[0]["risk_flags"][0]["model_risk_level"] == "yellow"
    assert payload[0]["risk_flags"][0]["trend_adjusted_level"] == "red"
    assert payload[0]["risk_flags"][0]["trend_reason"] == "trending upward"


def test_worker_cannot_fetch_other_workers_patient_visits():
    admin_token = _seed_and_login_admin()
    worker1, _ = _register_worker(admin_token, phone=_unique_phone())
    worker2_token, worker2_id = _register_worker(admin_token, phone=_unique_phone())

    db = get_session_local()()
    try:
        w2 = db.query(User).filter(User.id == uuid.UUID(worker2_id)).first()
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            worker_id=w2.id,
            name="Other Worker Patient",
            age=38,
            village="West Hill",
            edd=date(2026, 9, 1),
            phone=_unique_phone(),
        )
        visit = Visit(
            id=uuid.uuid4(),
            patient_id=patient.id,
            worker_id=w2.id,
            visit_date=date(2026, 8, 14),
            created_locally_at=datetime(2026, 8, 14, 7, 15, tzinfo=timezone.utc),
        )
        db.add_all([patient, visit])
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/patients/{patient_id}/visits", headers={"Authorization": f"Bearer {worker1}"})
    assert response.status_code in {403, 404}


def test_doctor_can_see_facility_patient_visits():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)
    doctor_token = _login_doctor()

    payload, visit_id, _ = _visit_payload(patient_id, worker_id)
    create = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )
    assert create.status_code == 200, create.text

    listing = client.get(f"/api/patients/{patient_id}/visits", headers={"Authorization": f"Bearer {doctor_token}"})
    assert listing.status_code == 200, listing.text
    ids = [v["id"] for v in listing.json()]
    assert visit_id in ids


def test_unauthorized_and_non_worker_create_rejected():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)
    doctor_token = _login_doctor()

    payload, _, _ = _visit_payload(patient_id, worker_id)

    missing_auth = client.post(f"/api/patients/{patient_id}/visits", json=payload)
    assert missing_auth.status_code in {401, 403}, missing_auth.status_code

    doctor_create = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json=payload,
    )
    assert doctor_create.status_code in {401, 403}, doctor_create.status_code

    admin_create = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert admin_create.status_code in {401, 403}, admin_create.status_code


def test_duplicate_visit_uuid_is_idempotent():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)

    payload, visit_id, risk_id = _visit_payload(patient_id, worker_id)

    first = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )
    second = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == visit_id
    assert second.json()["id"] == visit_id

    listing = client.get(f"/api/patients/{patient_id}/visits", headers={"Authorization": f"Bearer {worker_token}"})
    created = [v for v in listing.json() if v["id"] == visit_id]
    assert len(created) == 1
    assert len(created[0]["risk_flags"]) == 1


def test_invalid_vitals_and_risk_levels_rejected():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)

    base_payload, _, _ = _visit_payload(patient_id, worker_id)

    bad_bp = dict(base_payload)
    bad_bp["id"] = str(uuid.uuid4())
    bad_bp["systolic_bp"] = 5
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=bad_bp,
    )
    assert r.status_code == 422, r.text

    bad_temp = dict(base_payload)
    bad_temp["id"] = str(uuid.uuid4())
    bad_temp["body_temp_c"] = 99.9
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=bad_temp,
    )
    assert r.status_code == 422, r.text

    bad_hr = dict(base_payload)
    bad_hr["id"] = str(uuid.uuid4())
    bad_hr["heart_rate"] = 5
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=bad_hr,
    )
    assert r.status_code == 422, r.text

    bad_sugar = dict(base_payload)
    bad_sugar["id"] = str(uuid.uuid4())
    bad_sugar["blood_sugar"] = 99999
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=bad_sugar,
    )
    assert r.status_code == 422, r.text

    bad_risk = dict(base_payload)
    bad_risk["id"] = str(uuid.uuid4())
    bad_risk["risk_flags"] = [
        {
            "id": str(uuid.uuid4()),
            "model_risk_level": "purple",
            "trend_adjusted_level": "green",
        }
    ]
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=bad_risk,
    )
    assert r.status_code == 422, r.text


def test_path_patient_id_mismatch_rejected():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)
    other_patient_id = str(uuid.uuid4())

    payload, _, _ = _visit_payload(patient_id, worker_id)

    response = client.post(
        f"/api/patients/{other_patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )
    assert response.status_code in {400, 404}, response.text


def test_worker_id_mismatch_rejected():
    admin_token = _seed_and_login_admin()
    worker_token, _ = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)

    payload, _, _ = _visit_payload(patient_id, str(uuid.uuid4()))

    response = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )
    assert response.status_code == 400, response.text


def test_visit_for_other_workers_patient_forbidden():
    admin_token = _seed_and_login_admin()
    worker1, _ = _register_worker(admin_token, phone=_unique_phone())
    worker2_token, worker2_id = _register_worker(admin_token, phone=_unique_phone())
    patient_id = _create_patient(worker2_token)

    payload, _, _ = _visit_payload(patient_id, worker2_id)

    response = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker1}"},
        json=payload,
    )
    assert response.status_code in {400, 403}, response.text


def test_risk_level_case_insensitive_and_none_reason():
    admin_token = _seed_and_login_admin()
    worker_token, worker_id = _register_worker(admin_token)
    patient_id = _create_patient(worker_token)

    visit_id = str(uuid.uuid4())
    risk_id = str(uuid.uuid4())
    payload = {
        "id": visit_id,
        "patient_id": patient_id,
        "worker_id": worker_id,
        "visit_date": "2026-08-15T09:30:00+00:00",
        "created_locally_at": "2026-08-15T09:35:00+00:00",
        "risk_flags": [
            {
                "id": risk_id,
                "model_risk_level": "  GREEN  ",
                "trend_adjusted_level": "RED",
                "trend_reason": None,
            }
        ],
    }

    response = client.post(
        f"/api/patients/{patient_id}/visits",
        headers={"Authorization": f"Bearer {worker_token}"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    flags = response.json()["risk_flags"]
    assert len(flags) == 1
    assert flags[0]["model_risk_level"] == "green"
    assert flags[0]["trend_adjusted_level"] == "red"
    assert flags[0]["trend_reason"] is None


def test_get_visits_missing_patient_404():
    admin_token = _seed_and_login_admin()
    worker_token, _ = _register_worker(admin_token)
    missing = str(uuid.uuid4())

    response = client.get(f"/api/patients/{missing}/visits", headers={"Authorization": f"Bearer {worker_token}"})
    assert response.status_code == 404, response.text
