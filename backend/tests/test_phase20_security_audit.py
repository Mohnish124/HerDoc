import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.auth import _rate_limiter
from app.db.models import AuditLog, Facility, FacilityType, Patient, RefreshToken, Review, User, UserRole, Visit
from app.db.seed import seed_demo_data
from app.db.session import get_session_local
from app.services.auth_service import (
    ACCESS_TOKEN_TTL,
    BCRYPT_COST_FACTOR,
    PIN_BCRYPT_COST,
    REFRESH_TOKEN_TTL,
    hash_password,
    hash_pin,
    hash_refresh_token,
    validate_password_policy,
    validate_pin_policy,
    verify_password,
    verify_pin,
)

client = TestClient(app)


@pytest.fixture(scope="module")
def security_audit_fixture():
    db = get_session_local()()
    try:
        seed_demo_data(db, commit=True)

        f1 = db.query(Facility).filter(Facility.name == "Demo PHC").first()
        admin = db.query(User).filter(User.email == "admin@herdoc.local").first()
        doc1 = db.query(User).filter(User.email == "doctor@herdoc.local").first()
        w1 = db.query(User).filter(User.phone == "9000000003").first()

        # Create Facility 2 and Doctor 2 for cross-facility isolation testing
        f2 = db.query(Facility).filter(Facility.name == "Facility Two").first()
        if f2 is None:
            f2 = Facility(id=uuid.uuid4(), name="Facility Two", region="South", type=FacilityType.PHC.value)
            db.add(f2)
            db.flush()

        doc2 = db.query(User).filter(User.email == "doc2@herdoc.local").first()
        if doc2 is None:
            doc2 = User(
                id=uuid.uuid4(),
                name="Dr. Two",
                email="doc2@herdoc.local",
                password_hash=hash_password("DoctorPass!2024"),
                role=UserRole.DOCTOR.value,
                facility_id=f2.id,
                is_active=True,
            )
            db.add(doc2)
            db.flush()

        w2 = db.query(User).filter(User.phone == "9000000088").first()
        if w2 is None:
            w2 = User(
                id=uuid.uuid4(),
                name="ASHA Two",
                phone="9000000088",
                pin_hash=hash_pin("2468"),
                role=UserRole.WORKER.value,
                facility_id=f2.id,
                is_active=True,
            )
            db.add(w2)
            db.flush()

        # Patient at Facility 1
        p1 = Patient(
            id=uuid.uuid4(),
            worker_id=w1.id,
            name="Facility 1 Patient",
            age=24,
            village="Village 1",
        )
        db.add(p1)

        # Patient at Facility 2
        p2 = Patient(
            id=uuid.uuid4(),
            worker_id=w2.id,
            name="Facility 2 Patient",
            age=26,
            village="Village 2",
        )
        db.add(p2)

        db.commit()

        return {
            "admin_email": "admin@herdoc.local",
            "doc1_email": "doctor@herdoc.local",
            "doc2_email": "doc2@herdoc.local",
            "w1_phone": "9000000003",
            "w2_phone": "9000000088",
            "p1_id": str(p1.id),
            "p2_id": str(p2.id),
            "f1_id": str(f1.id),
            "f2_id": str(f2.id),
        }
    finally:
        db.close()


def test_cryptographic_primitives_and_token_lifecycles():
    # 1. Bcrypt cost factors
    assert BCRYPT_COST_FACTOR >= 12, "Bcrypt password cost factor must be >= 12"
    assert PIN_BCRYPT_COST >= 12, "Bcrypt PIN cost factor must be >= 12"

    # 2. Token TTLs
    assert ACCESS_TOKEN_TTL == timedelta(minutes=15), "JWT access token TTL must be 15 minutes"
    assert REFRESH_TOKEN_TTL == timedelta(days=30), "Refresh token TTL must be 30 days"

    # 3. Password policy enforcement
    with pytest.raises(ValueError):
        validate_password_policy("short")  # < 10 chars
    with pytest.raises(ValueError):
        validate_password_policy("Password123")  # Common password

    # 4. PIN policy enforcement
    with pytest.raises(ValueError):
        validate_pin_policy("123")  # < 4 digits
    with pytest.raises(ValueError):
        validate_pin_policy("1234567")  # > 6 digits
    with pytest.raises(ValueError):
        validate_pin_policy("1111")  # All same digit
    with pytest.raises(ValueError):
        validate_pin_policy("1234")  # Sequential
    with pytest.raises(ValueError):
        validate_pin_policy("abcd")  # Non-numeric


def test_lockout_and_rate_limiting_defense():
    _rate_limiter.clear()
    phone = f"96{uuid.uuid4().int % 100000000:08d}"

    # Register worker
    admin_login = client.post("/api/auth/login/admin", json={"email": "admin@herdoc.local", "password": "AdminPass!2024"})
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/auth/register/worker",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Lockout Test Worker", "phone": phone, "temporary_pin": "2468"},
    )

    # Attempt 4 failed logins -> 401
    for _ in range(4):
        resp = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "9999"})
        assert resp.status_code == 401

    # 5th failed login triggers 15-minute lockout -> 403
    lockout_resp = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "9999"})
    assert lockout_resp.status_code == 403
    assert "locked" in lockout_resp.json()["detail"].lower()

    # Even with correct PIN, account is locked -> 403
    correct_pin_while_locked = client.post("/api/auth/login/worker", json={"phone": phone, "pin": "2468"})
    assert correct_pin_while_locked.status_code == 403


def test_idor_and_facility_isolation(security_audit_fixture):
    data = security_audit_fixture

    # Login Doctor 1 (Facility 1)
    doc1_login = client.post("/api/auth/login/doctor", json={"email": data["doc1_email"], "password": "DoctorPass!2024"})
    doc1_token = doc1_login.json()["access_token"]
    doc1_headers = {"Authorization": f"Bearer {doc1_token}"}

    # Login Worker 1 (Facility 1)
    w1_login = client.post("/api/auth/login/worker", json={"phone": data["w1_phone"], "pin": "2468"})
    w1_token = w1_login.json()["access_token"]
    w1_headers = {"Authorization": f"Bearer {w1_token}"}

    # 1. IDOR: Worker 1 cannot fetch Patient 2 (assigned to Worker 2) -> 403
    w1_p2_resp = client.get(f"/api/patients/{data['p2_id']}", headers=w1_headers)
    assert w1_p2_resp.status_code == 403

    # 2. IDOR: Worker 1 cannot create visits for Patient 2 -> 403
    w1_visit_p2_resp = client.post(
        f"/api/patients/{data['p2_id']}/visits",
        headers=w1_headers,
        json={
            "id": str(uuid.uuid4()),
            "patient_id": data["p2_id"],
            "worker_id": str(uuid.uuid4()),
            "visit_date": datetime.now(timezone.utc).isoformat(),
            "created_locally_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert w1_visit_p2_resp.status_code in {400, 403}

    # 3. Facility Isolation: Doctor 1 cannot fetch Patient 2 (at Facility 2) -> 403
    doc1_p2_resp = client.get(f"/api/patients/{data['p2_id']}", headers=doc1_headers)
    assert doc1_p2_resp.status_code == 403

    # 4. Facility Isolation: Doctor 1 cannot list visits for Patient 2 -> 403
    doc1_p2_visits_resp = client.get(f"/api/patients/{data['p2_id']}/visits", headers=doc1_headers)
    assert doc1_p2_visits_resp.status_code == 403

    # 5. Facility Isolation: Doctor 1 cannot review Patient 2 -> 403
    doc1_review_p2_resp = client.post(
        "/api/reviews",
        headers=doc1_headers,
        json={"patient_id": data["p2_id"], "status": "reviewed"},
    )
    assert doc1_review_p2_resp.status_code == 403


def test_token_rotation_revocation_and_hash_storage():
    admin_login = client.post("/api/auth/login/admin", json={"email": "admin@herdoc.local", "password": "AdminPass!2024"})
    assert admin_login.status_code == 200
    refresh_token = admin_login.json()["refresh_token"]

    # Verify refresh token is stored ONLY as a hash in MySQL
    db = get_session_local()()
    try:
        t_hash = hash_refresh_token(refresh_token)
        stored_token = db.query(RefreshToken).filter(RefreshToken.token_hash == t_hash).first()
        assert stored_token is not None, "Refresh token hash must be recorded in DB"
        # Confirm no plaintext refresh token JWT string is stored in table
        assert db.query(RefreshToken).filter(RefreshToken.token_hash == refresh_token).first() is None
    finally:
        db.close()

    # Refresh token rotation: calling /api/auth/refresh returns a new token pair and revokes previous
    refresh_resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_refresh_token = refresh_resp.json()["refresh_token"]
    assert new_refresh_token != refresh_token

    # Reusing the old refresh token is rejected -> 401
    reuse_resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_resp.status_code == 401
