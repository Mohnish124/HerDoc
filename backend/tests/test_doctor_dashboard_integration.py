import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import Facility, Patient, RiskFlag, User, UserRole, Visit
from app.db.seed import seed_demo_data
from app.db.session import get_session_local

client = TestClient(app)


def _setup_dashboard_test_data():
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)

        # Get existing facility and worker
        facility = db.query(Facility).first()
        worker = db.query(User).filter(User.role == UserRole.WORKER.value).first()
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR.value).first()

        # Create Patient 1 (Yellow Trend Escalated)
        p1_id = uuid.uuid4()
        p1 = Patient(
            id=p1_id,
            worker_id=worker.id,
            name="Anjali Sharma",
            age=24,
            village="Rampur",
            phone="9876500001",
        )
        db.add(p1)
        db.flush()

        v1 = Visit(
            id=uuid.uuid4(),
            patient_id=p1.id,
            worker_id=worker.id,
            visit_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
            systolic_bp=110,
            diastolic_bp=70,
            blood_sugar=85,
            body_temp_c=36.8,
            heart_rate=72,
            created_locally_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
        )
        db.add(v1)
        db.flush()
        db.add(RiskFlag(id=uuid.uuid4(), visit_id=v1.id, model_risk_level="green", trend_adjusted_level="green"))

        v2 = Visit(
            id=uuid.uuid4(),
            patient_id=p1.id,
            worker_id=worker.id,
            visit_date=datetime(2026, 8, 17, tzinfo=timezone.utc).date(),
            systolic_bp=128,
            diastolic_bp=84,
            blood_sugar=95,
            body_temp_c=37.0,
            heart_rate=78,
            created_locally_at=datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc),
        )
        db.add(v2)
        db.flush()
        db.add(
            RiskFlag(
                id=uuid.uuid4(),
                visit_id=v2.id,
                model_risk_level="green",
                trend_adjusted_level="yellow",
                trend_reason="Blood pressure has risen steadily over your last 2 visits.",
            )
        )

        # Create Patient 2 (Red High Risk)
        p2_id = uuid.uuid4()
        p2 = Patient(
            id=p2_id,
            worker_id=worker.id,
            name="Sunita Devi",
            age=32,
            village="Kalyanpur",
            phone="9876500002",
        )
        db.add(p2)
        db.flush()

        v3 = Visit(
            id=uuid.uuid4(),
            patient_id=p2.id,
            worker_id=worker.id,
            visit_date=datetime(2026, 8, 18, tzinfo=timezone.utc).date(),
            systolic_bp=150,
            diastolic_bp=98,
            blood_sugar=140,
            body_temp_c=37.5,
            heart_rate=92,
            created_locally_at=datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc),
        )
        db.add(v3)
        db.flush()
        db.add(RiskFlag(id=uuid.uuid4(), visit_id=v3.id, model_risk_level="red", trend_adjusted_level="red"))

        db.commit()
        return {
            "doctor_id": str(doctor.id),
            "worker_id": str(worker.id),
            "facility_id": str(facility.id),
            "p1_id": str(p1_id),
            "p2_id": str(p2_id),
        }
    finally:
        db.close()


def test_doctor_dashboard_sorting_and_triage_flow():
    data = _setup_dashboard_test_data()

    # 1. Doctor Login
    login_resp = client.post(
        "/api/auth/login/doctor",
        json={"email": "doctor@herdoc.local", "password": "DoctorPass!2024"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Flagged Patients
    flagged_resp = client.get("/api/dashboard/flagged", headers=headers)
    assert flagged_resp.status_code == 200
    flagged = flagged_resp.json()
    assert len(flagged) >= 2

    # Verify Sorting: Red First, Yellow Second
    p_red = next(p for p in flagged if p["id"] == data["p2_id"])
    p_yellow = next(p for p in flagged if p["id"] == data["p1_id"])

    idx_red = flagged.index(p_red)
    idx_yellow = flagged.index(p_yellow)
    assert idx_red < idx_yellow, "RED risk patients must be sorted before YELLOW risk patients"

    assert p_red["latest_risk"]["trend_adjusted_level"] == "red"
    assert p_yellow["latest_risk"]["trend_adjusted_level"] == "yellow"
    assert "risen steadily" in p_yellow["latest_risk"]["trend_reason"]

    # 3. Test Filter Endpoints
    filter_resp = client.get("/api/dashboard/filters", headers=headers)
    assert filter_resp.status_code == 200
    assert len(filter_resp.json()["workers"]) > 0

    # 4. View Patient Detail Visits
    visits_resp = client.get(f"/api/patients/{data['p1_id']}/visits", headers=headers)
    assert visits_resp.status_code == 200
    patient_visits = visits_resp.json()
    assert len(patient_visits) == 2

    # 5. Submit Doctor Clinical Review (Referred)
    review_resp = client.post(
        "/api/reviews",
        headers=headers,
        json={
            "patient_id": data["p1_id"],
            "status": "referred",
            "notes": "Referred to District Hospital for preeclampsia monitoring.",
        },
    )
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["status"] == "referred"
    assert "preeclampsia monitoring" in review_data["notes"]

    # 6. Verify Updated Review Status in Flagged Dashboard
    updated_flagged_resp = client.get("/api/dashboard/flagged", headers=headers)
    assert updated_flagged_resp.status_code == 200
    updated_p1 = next(p for p in updated_flagged_resp.json() if p["id"] == data["p1_id"])
    assert updated_p1["review"]["status"] == "referred"


def test_worker_cannot_submit_doctor_review():
    data = _setup_dashboard_test_data()

    # Login as Worker (seeded credentials: phone="9000000003", pin="2468")
    worker_login = client.post(
        "/api/auth/login/worker",
        json={"phone": "9000000003", "pin": "2468"},
    )
    assert worker_login.status_code == 200, worker_login.text
    worker_token = worker_login.json()["access_token"]

    # Worker attempting POST /api/reviews must receive 403 Forbidden
    forbidden_resp = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "patient_id": data["p1_id"],
            "status": "reviewed",
            "notes": "Worker attempting review",
        },
    )
    assert forbidden_resp.status_code == 403
