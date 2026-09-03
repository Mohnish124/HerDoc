import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import AuditLog, Facility, FacilityType, Patient, Review, RiskFlag, User, UserRole, Visit
from app.db.seed import seed_demo_data
from app.db.session import get_session_local
from app.services.auth_service import hash_password, hash_pin

client = TestClient(app)


@pytest.fixture(scope="module")
def multi_facility_data():
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)

        # Facility 1 (from seed)
        f1 = db.query(Facility).filter(Facility.name == "Demo PHC").first()
        doc1 = db.query(User).filter(User.email == "doctor@herdoc.local").first()
        w1 = db.query(User).filter(User.phone == "9000000003").first()
        admin = db.query(User).filter(User.email == "admin@herdoc.local").first()

        # Facility 2
        f2 = db.query(Facility).filter(Facility.name == "South District PHC").first()
        if f2 is None:
            f2 = Facility(id=uuid.uuid4(), name="South District PHC", region="South", type=FacilityType.PHC.value)
            db.add(f2)
            db.flush()

        # Doctor 2
        doc2 = db.query(User).filter(User.email == "dr.south@herdoc.local").first()
        if doc2 is None:
            doc2 = User(
                id=uuid.uuid4(),
                name="Dr. South",
                email="dr.south@herdoc.local",
                password_hash=hash_password("DoctorPass!2024"),
                role=UserRole.DOCTOR.value,
                facility_id=f2.id,
                is_active=True,
            )
            db.add(doc2)
            db.flush()

        # Worker 2
        w2 = db.query(User).filter(User.phone == "9000000099").first()
        if w2 is None:
            w2 = User(
                id=uuid.uuid4(),
                name="ASHA Rekha",
                phone="9000000099",
                pin_hash=hash_pin("2468"),
                role=UserRole.WORKER.value,
                facility_id=f2.id,
                is_active=True,
            )
            db.add(w2)
            db.flush()

        # Patient 1 at Facility 1 (Yellow Trend Risk)
        p1_id = uuid.uuid4()
        p1 = Patient(
            id=p1_id,
            worker_id=w1.id,
            name="Facility1 Yellow Patient",
            age=25,
            village="North Rampur",
            phone=f"91{uuid.uuid4().int % 100000000:08d}",
        )
        db.add(p1)
        db.flush()

        v1 = Visit(
            id=uuid.uuid4(),
            patient_id=p1.id,
            worker_id=w1.id,
            visit_date=datetime.now(timezone.utc).date() - timedelta(days=2),
            systolic_bp=128,
            diastolic_bp=84,
            blood_sugar=95,
            body_temp_c=37.0,
            heart_rate=78,
            created_locally_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add(v1)
        db.flush()
        db.add(
            RiskFlag(
                id=uuid.uuid4(),
                visit_id=v1.id,
                model_risk_level="green",
                trend_adjusted_level="yellow",
                trend_reason="Blood pressure has risen steadily.",
            )
        )

        # Patient 2 at Facility 1 (Red High Risk)
        p2_id = uuid.uuid4()
        p2 = Patient(
            id=p2_id,
            worker_id=w1.id,
            name="Facility1 Red Patient",
            age=30,
            village="North Rampur",
            phone=f"91{uuid.uuid4().int % 100000000:08d}",
        )
        db.add(p2)
        db.flush()

        v2 = Visit(
            id=uuid.uuid4(),
            patient_id=p2.id,
            worker_id=w1.id,
            visit_date=datetime.now(timezone.utc).date() - timedelta(days=1),
            systolic_bp=152,
            diastolic_bp=96,
            blood_sugar=140,
            body_temp_c=37.5,
            heart_rate=90,
            created_locally_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(v2)
        db.flush()
        db.add(RiskFlag(id=uuid.uuid4(), visit_id=v2.id, model_risk_level="red", trend_adjusted_level="red"))

        # Patient 3 at Facility 2 (Red High Risk)
        p3_id = uuid.uuid4()
        p3 = Patient(
            id=p3_id,
            worker_id=w2.id,
            name="Facility2 Red Patient",
            age=28,
            village="South Kalyanpur",
            phone=f"91{uuid.uuid4().int % 100000000:08d}",
        )
        db.add(p3)
        db.flush()

        v3 = Visit(
            id=uuid.uuid4(),
            patient_id=p3.id,
            worker_id=w2.id,
            visit_date=datetime.now(timezone.utc).date() - timedelta(days=1),
            systolic_bp=160,
            diastolic_bp=100,
            blood_sugar=150,
            body_temp_c=37.8,
            heart_rate=94,
            created_locally_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(v3)
        db.flush()
        db.add(RiskFlag(id=uuid.uuid4(), visit_id=v3.id, model_risk_level="red", trend_adjusted_level="red"))

        db.commit()
        return {
            "f1_id": str(f1.id),
            "f2_id": str(f2.id),
            "doc1_email": "doctor@herdoc.local",
            "doc2_email": "dr.south@herdoc.local",
            "admin_email": "admin@herdoc.local",
            "w1_phone": "9000000003",
            "w1_id": str(w1.id),
            "w2_id": str(w2.id),
            "p1_id": str(p1_id),
            "p2_id": str(p2_id),
            "p3_id": str(p3_id),
        }
    finally:
        db.close()


def test_role_restrictions_deny_worker(multi_facility_data):
    data = multi_facility_data

    # Login as Worker
    worker_login = client.post(
        "/api/auth/login/worker",
        json={"phone": data["w1_phone"], "pin": "2468"},
    )
    assert worker_login.status_code == 200
    token = worker_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Worker DENY on flagged dashboard
    flagged_resp = client.get("/api/dashboard/flagged", headers=headers)
    assert flagged_resp.status_code == 403

    # Worker DENY on reviews
    review_resp = client.post(
        "/api/reviews",
        headers=headers,
        json={"patient_id": data["p1_id"], "status": "reviewed"},
    )
    assert review_resp.status_code == 403

    # Worker DENY on facility overview
    overview_resp = client.get("/api/dashboard/facility-overview", headers=headers)
    assert overview_resp.status_code == 403


def test_facility_restrictions_for_doctor(multi_facility_data):
    data = multi_facility_data

    # Login as Doctor 1 (Facility 1)
    doc1_login = client.post(
        "/api/auth/login/doctor",
        json={"email": data["doc1_email"], "password": "DoctorPass!2024"},
    )
    assert doc1_login.status_code == 200
    doc1_token = doc1_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {doc1_token}"}

    # Doctor 1 attempting to query Facility 2 flagged cases receives 403
    forbidden_flagged = client.get(f"/api/dashboard/flagged?facility_id={data['f2_id']}", headers=headers)
    assert forbidden_flagged.status_code == 403

    # Doctor 1 attempting to review Patient at Facility 2 receives 403
    forbidden_review = client.post(
        "/api/reviews",
        headers=headers,
        json={"patient_id": data["p3_id"], "status": "reviewed", "notes": "Cross-facility review attempt"},
    )
    assert forbidden_review.status_code == 403

    # Doctor 1 querying own facility flagged sees Facility 1 patients only
    own_flagged = client.get("/api/dashboard/flagged", headers=headers)
    assert own_flagged.status_code == 200
    flagged_ids = [p["id"] for p in own_flagged.json()]
    assert data["p1_id"] in flagged_ids
    assert data["p2_id"] in flagged_ids
    assert data["p3_id"] not in flagged_ids


def test_sorting_red_first_yellow_second(multi_facility_data):
    data = multi_facility_data

    doc1_login = client.post(
        "/api/auth/login/doctor",
        json={"email": data["doc1_email"], "password": "DoctorPass!2024"},
    )
    headers = {"Authorization": f"Bearer {doc1_login.json()['access_token']}"}

    flagged_resp = client.get("/api/dashboard/flagged", headers=headers)
    assert flagged_resp.status_code == 200
    flagged = flagged_resp.json()

    # Verify RED is indexed before YELLOW
    p_red = next(p for p in flagged if p["id"] == data["p2_id"])
    p_yellow = next(p for p in flagged if p["id"] == data["p1_id"])

    assert flagged.index(p_red) < flagged.index(p_yellow)
    assert p_red["trend_adjusted_level"] == "red"
    assert p_yellow["trend_adjusted_level"] == "yellow"
    assert p_yellow["trend_reason"] is not None


def test_review_creation_update_and_audit_logging(multi_facility_data):
    data = multi_facility_data

    doc1_login = client.post(
        "/api/auth/login/doctor",
        json={"email": data["doc1_email"], "password": "DoctorPass!2024"},
    )
    headers = {"Authorization": f"Bearer {doc1_login.json()['access_token']}"}

    # 1. Create Review (reviewed)
    create_resp = client.post(
        "/api/reviews",
        headers=headers,
        json={
            "patient_id": data["p1_id"],
            "status": "reviewed",
            "notes": "Patient advised standard antenatal care routine.",
        },
    )
    assert create_resp.status_code == 200
    review_out = create_resp.json()
    assert review_out["status"] == "reviewed"
    assert review_out["reviewed_at"] is not None
    assert "antenatal care" in review_out["notes"]

    # 2. Update Review (referred)
    update_resp = client.post(
        "/api/reviews",
        headers=headers,
        json={
            "patient_id": data["p1_id"],
            "status": "referred",
            "notes": "Escalated: Refer to District Hospital immediately.",
        },
    )
    assert update_resp.status_code == 200
    updated_out = update_resp.json()
    assert updated_out["status"] == "referred"
    assert updated_out["reviewed_at"] is not None
    assert "District Hospital" in updated_out["notes"]

    # 3. Update Review back to pending -> reviewed_at becomes None
    pending_resp = client.post(
        "/api/reviews",
        headers=headers,
        json={
            "patient_id": data["p1_id"],
            "status": "pending",
        },
    )
    assert pending_resp.status_code == 200
    assert pending_resp.json()["reviewed_at"] is None

    # 4. Verify Audit Log was recorded
    db = get_session_local()()
    try:
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.event_type == "patient_reviewed")
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        assert len(logs) >= 3
        latest_log = logs[0]
        assert latest_log.event_metadata["patient_id"] == data["p1_id"]
    finally:
        db.close()


def test_facility_overview_metrics(multi_facility_data):
    data = multi_facility_data

    # Login as Doctor 1
    doc1_login = client.post(
        "/api/auth/login/doctor",
        json={"email": data["doc1_email"], "password": "DoctorPass!2024"},
    )
    headers = {"Authorization": f"Bearer {doc1_login.json()['access_token']}"}

    overview_resp = client.get("/api/dashboard/facility-overview", headers=headers)
    assert overview_resp.status_code == 200
    overview = overview_resp.json()

    assert overview["total_patients"] >= 2
    assert overview["active_flags"]["red"] >= 1
    assert overview["active_flags"]["yellow"] >= 1
    assert overview["active_workers_last_7_days"] >= 1


def test_admin_filtering_across_facilities(multi_facility_data):
    data = multi_facility_data

    # Login as Admin
    admin_login = client.post(
        "/api/auth/login/admin",
        json={"email": data["admin_email"], "password": "AdminPass!2024"},
    )
    headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Admin filtering by Facility 2
    f2_flagged = client.get(f"/api/dashboard/flagged?facility_id={data['f2_id']}", headers=headers)
    assert f2_flagged.status_code == 200
    f2_list = f2_flagged.json()
    assert len(f2_list) >= 1
    assert any(p["id"] == data["p3_id"] for p in f2_list)

    # Admin filtering by Worker 1
    w1_flagged = client.get(f"/api/dashboard/flagged?worker_id={data['w1_id']}", headers=headers)
    assert w1_flagged.status_code == 200
    assert len(w1_flagged.json()) >= 2
