import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import (
    AuditLog,
    Facility,
    FacilityType,
    Patient,
    RefreshToken,
    Review,
    ReviewStatus,
    RiskFlag,
    RiskLevel,
    User,
    UserRole,
    Visit,
)


@pytest.fixture()
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _build_worker_and_facility(session: Session):
    facility = Facility(
        id=uuid.uuid4(),
        name="Integration PHC",
        region="Test Region",
        type=FacilityType.PHC.value,
    )
    worker = User(
        id=uuid.uuid4(),
        role=UserRole.WORKER.value,
        name="Test Worker",
        phone="9876500001",
        email="worker.test@herdoc.local",
        facility_id=facility.id,
        password_hash="placeholder",
    )
    session.add_all([facility, worker])
    session.flush()
    return facility, worker


def _build_doctor(session: Session, facility: Facility):
    doctor = User(
        id=uuid.uuid4(),
        role=UserRole.DOCTOR.value,
        name="Test Doctor",
        phone="9876500002",
        email="doctor.test@herdoc.local",
        facility_id=facility.id,
        password_hash="placeholder",
    )
    session.add(doctor)
    session.flush()
    return doctor


def _build_patient(session: Session, worker: User):
    patient = Patient(
        id=uuid.uuid4(),
        worker_id=worker.id,
        name="Test Patient",
        age=26,
        phone="9876500010",
        village="Testville",
        edd=date(2026, 11, 30),
    )
    session.add(patient)
    session.flush()
    return patient


# =============== INSERT TESTS ===============


def test_insert_facility(in_memory_db):
    facility = Facility(
        id=uuid.uuid4(),
        name="New Sub Center",
        region="East",
        type=FacilityType.SUB_CENTER.value,
    )
    in_memory_db.add(facility)
    in_memory_db.commit()

    loaded = in_memory_db.get(Facility, facility.id)
    assert loaded is not None
    assert loaded.name == "New Sub Center"
    assert loaded.type == FacilityType.SUB_CENTER.value
    assert loaded.region == "East"


def test_insert_user(in_memory_db):
    facility, _ = _build_worker_and_facility(in_memory_db)
    admin = User(
        id=uuid.uuid4(),
        role=UserRole.ADMIN.value,
        name="Inserted Admin",
        phone="9876500009",
        email="admin.insert@herdoc.local",
        facility_id=facility.id,
        password_hash="hash-value",
        pin_hash="pin-hash",
    )
    in_memory_db.add(admin)
    in_memory_db.commit()

    loaded = in_memory_db.get(User, admin.id)
    assert loaded is not None
    assert loaded.role == UserRole.ADMIN.value
    assert loaded.phone == "9876500009"
    assert loaded.email == "admin.insert@herdoc.local"
    assert loaded.facility_id == facility.id
    assert loaded.is_active is True
    assert loaded.failed_login_attempts == 0
    assert loaded.locked_until is None


# =============== RELATIONSHIP TESTS ===============


def test_patient_worker_relationship(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    patient = _build_patient(in_memory_db, worker)
    in_memory_db.commit()

    loaded_patient = in_memory_db.get(Patient, patient.id)
    assert loaded_patient.worker_id == worker.id
    assert loaded_patient.worker.id == worker.id
    assert loaded_patient.worker.name == "Test Worker"
    assert worker in loaded_patient.worker.facility.users


def test_visit_patient_relationship(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    patient = _build_patient(in_memory_db, worker)
    visit = Visit(
        id=uuid.uuid4(),
        patient_id=patient.id,
        worker_id=worker.id,
        visit_date=date(2026, 8, 18),
        systolic_bp=118,
        diastolic_bp=76,
        blood_sugar=92,
        body_temp_c=36.5,
        heart_rate=70,
        created_locally_at=datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc),
    )
    in_memory_db.add(visit)
    in_memory_db.commit()

    loaded = in_memory_db.get(Visit, visit.id)
    assert loaded.patient_id == patient.id
    assert loaded.patient.id == patient.id
    assert loaded.patient.name == "Test Patient"
    assert loaded in patient.visits


def test_visit_worker_relationship(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    patient = _build_patient(in_memory_db, worker)
    visit = Visit(
        id=uuid.uuid4(),
        patient_id=patient.id,
        worker_id=worker.id,
        visit_date=date(2026, 8, 18),
        systolic_bp=120,
        diastolic_bp=80,
        created_locally_at=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
    )
    in_memory_db.add(visit)
    in_memory_db.commit()

    loaded_visit = in_memory_db.get(Visit, visit.id)
    assert loaded_visit.worker_id == worker.id
    assert loaded_visit.worker.role == UserRole.WORKER.value
    assert loaded_visit in worker.visits


def test_risk_flag_visit_relationship(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    patient = _build_patient(in_memory_db, worker)
    visit = Visit(
        id=uuid.uuid4(),
        patient_id=patient.id,
        worker_id=worker.id,
        visit_date=date(2026, 8, 18),
        systolic_bp=160,
        diastolic_bp=105,
        created_locally_at=datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc),
    )
    risk = RiskFlag(
        id=uuid.uuid4(),
        visit_id=visit.id,
        model_risk_level=RiskLevel.HIGH.value,
        trend_adjusted_level=RiskLevel.HIGH.value,
        trend_reason="severe hypertension",
    )
    in_memory_db.add_all([visit, risk])
    in_memory_db.commit()

    loaded = in_memory_db.get(RiskFlag, risk.id)
    assert loaded.visit_id == visit.id
    assert loaded.visit.patient_id == patient.id
    assert loaded in visit.risk_flags


def test_review_patient_relationship(in_memory_db):
    facility, worker = _build_worker_and_facility(in_memory_db)
    doctor = _build_doctor(in_memory_db, facility)
    patient = _build_patient(in_memory_db, worker)
    review = Review(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.id,
        status=ReviewStatus.PENDING.value,
        notes="Requires further observation",
    )
    in_memory_db.add(review)
    in_memory_db.commit()

    loaded = in_memory_db.get(Review, review.id)
    assert loaded.patient_id == patient.id
    assert loaded.patient.village == "Testville"
    assert loaded.doctor_id == doctor.id
    assert loaded.status == ReviewStatus.PENDING.value
    assert loaded in patient.reviews
    assert loaded in doctor.reviews


def test_refresh_token_user_relationship(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    token = RefreshToken(
        id=uuid.uuid4(),
        user_id=worker.id,
        token_hash="sha256:abc123",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    in_memory_db.add(token)
    in_memory_db.commit()

    loaded = in_memory_db.get(RefreshToken, token.id)
    assert loaded.user_id == worker.id
    assert loaded.user.email == worker.email
    assert loaded.revoked_at is None
    assert loaded in worker.refresh_tokens


def test_audit_log_user_relationship(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    metadata = {
        "action": "patient_sync",
        "device_id": "mobile-001",
        "count": 12,
        "success": True,
        "errors": [],
    }
    log = AuditLog(
        id=uuid.uuid4(),
        user_id=worker.id,
        event_type="patient.sync",
        event_metadata=metadata,
    )
    in_memory_db.add(log)
    in_memory_db.commit()

    loaded = in_memory_db.get(AuditLog, log.id)
    assert loaded.user_id == worker.id
    assert loaded.user.name == worker.name
    assert loaded.event_metadata["action"] == "patient_sync"
    assert loaded.event_metadata["count"] == 12
    assert loaded.event_metadata["errors"] == []
    assert loaded in worker.audit_logs


# =============== TRANSACTION ROLLBACK ===============


def test_transaction_rollback_preserves_consistency(in_memory_db):
    facility, worker = _build_worker_and_facility(in_memory_db)
    in_memory_db.commit()
    facility_id = facility.id
    worker_id = worker.id

    patient = Patient(
        id=uuid.uuid4(),
        worker_id=worker_id,
        name="About to Rollback",
        age=30,
        village="Rollback City",
    )
    bad_visit = Visit(
        id=uuid.uuid4(),
        patient_id=patient.id,
        worker_id=worker_id,
        visit_date=date(2026, 8, 18),
        systolic_bp=120,
        created_locally_at=datetime.now(timezone.utc),
    )
    in_memory_db.add_all([patient, bad_visit])
    in_memory_db.flush()

    in_memory_db.rollback()

    assert in_memory_db.get(Patient, patient.id) is None
    assert in_memory_db.get(Visit, bad_visit.id) is None

    assert in_memory_db.get(Facility, facility_id) is not None
    assert in_memory_db.get(User, worker_id) is not None


def test_nested_flush_rollback_on_integrity_error(in_memory_db):
    facility = Facility(
        id=uuid.uuid4(),
        name="Unique Test Facility",
        region="R-Zero",
        type=FacilityType.SUB_CENTER.value,
    )
    user_a = User(
        id=uuid.uuid4(),
        role=UserRole.WORKER.value,
        name="Alice User",
        phone="9999999999",
        email="alice.unique@herdoc.local",
        facility_id=facility.id,
        password_hash="hash",
    )
    in_memory_db.add_all([facility, user_a])
    in_memory_db.commit()
    facility_id = facility.id
    user_a_id = user_a.id

    user_b = User(
        id=uuid.uuid4(),
        role=UserRole.DOCTOR.value,
        name="Bob User",
        phone="9999999999",
        email="bob.unique@herdoc.local",
        facility_id=facility_id,
        password_hash="hash",
    )
    in_memory_db.add(user_b)
    with pytest.raises(IntegrityError):
        in_memory_db.commit()

    in_memory_db.rollback()

    assert in_memory_db.get(User, user_a_id) is not None
    assert in_memory_db.get(Facility, facility_id) is not None
    found_user_a = in_memory_db.query(User).filter_by(phone="9999999999").first()
    assert found_user_a is not None
    assert found_user_a.id == user_a_id


# =============== DUPLICATE UUID ===============


def test_duplicate_uuid_raises_integrity_error(in_memory_db):
    fid = uuid.uuid4()
    f1 = Facility(id=fid, name="First", region="R1", type=FacilityType.PHC.value)
    in_memory_db.add(f1)
    in_memory_db.commit()

    f2 = Facility(id=fid, name="Second", region="R2", type=FacilityType.SUB_CENTER.value)
    in_memory_db.add(f2)
    with pytest.raises(IntegrityError):
        in_memory_db.commit()


def test_duplicate_user_uuid_rollback_and_retry_with_new(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    in_memory_db.commit()

    pid = uuid.uuid4()
    p1 = Patient(
        id=pid,
        worker_id=worker.id,
        name="Original Patient",
        age=22,
        village="Village Alpha",
    )
    in_memory_db.add(p1)
    in_memory_db.commit()

    p2 = Patient(
        id=pid,
        worker_id=worker.id,
        name="Collision Patient",
        age=24,
        village="Village Beta",
    )
    in_memory_db.add(p2)
    with pytest.raises(IntegrityError):
        in_memory_db.commit()

    in_memory_db.rollback()

    p2_new = Patient(
        id=uuid.uuid4(),
        worker_id=worker.id,
        name="Collision Patient",
        age=24,
        village="Village Beta",
    )
    in_memory_db.add(p2_new)
    in_memory_db.commit()
    assert in_memory_db.get(Patient, p2_new.id) is not None
    assert in_memory_db.get(Patient, pid).name == "Original Patient"


# =============== FOREIGN KEY REJECTION ===============


def test_fk_rejection_patient_invalid_worker(in_memory_db):
    bad_worker_id = uuid.uuid4()
    patient = Patient(
        id=uuid.uuid4(),
        worker_id=bad_worker_id,
        name="Orphan Patient",
        age=30,
        village="Nowhere",
    )
    in_memory_db.add(patient)
    with pytest.raises((IntegrityError, SQLAlchemyError)):
        in_memory_db.commit()


def test_fk_rejection_visit_invalid_patient(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    in_memory_db.commit()

    visit = Visit(
        id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        worker_id=worker.id,
        visit_date=date(2026, 8, 18),
        systolic_bp=120,
        created_locally_at=datetime.now(timezone.utc),
    )
    in_memory_db.add(visit)
    with pytest.raises((IntegrityError, SQLAlchemyError)):
        in_memory_db.commit()


def test_fk_rejection_risk_flag_invalid_visit(in_memory_db):
    risk = RiskFlag(
        id=uuid.uuid4(),
        visit_id=uuid.uuid4(),
        model_risk_level=RiskLevel.LOW.value,
        trend_adjusted_level=RiskLevel.LOW.value,
    )
    in_memory_db.add(risk)
    with pytest.raises((IntegrityError, SQLAlchemyError)):
        in_memory_db.commit()


def test_fk_rejection_review_invalid_doctor(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    patient = _build_patient(in_memory_db, worker)
    in_memory_db.commit()

    review = Review(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=uuid.uuid4(),
        status=ReviewStatus.PENDING.value,
    )
    in_memory_db.add(review)
    with pytest.raises((IntegrityError, SQLAlchemyError)):
        in_memory_db.commit()


def test_fk_rejection_refresh_token_invalid_user(in_memory_db):
    token = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="x",
        expires_at=datetime.now(timezone.utc),
    )
    in_memory_db.add(token)
    with pytest.raises((IntegrityError, SQLAlchemyError)):
        in_memory_db.commit()


def test_fk_rejection_audit_log_invalid_user(in_memory_db):
    log = AuditLog(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        event_type="test",
        event_metadata={},
    )
    in_memory_db.add(log)
    with pytest.raises((IntegrityError, SQLAlchemyError)):
        in_memory_db.commit()


# =============== MYSQL JSON METADATA ===============


def test_json_metadata_complex_structure(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    complex_metadata = {
        "event": "visit_created",
        "payload": {
            "vitals": {"bp": [120, 80], "temp": 36.6},
            "flags": [],
            "nested": {"deep": {"value": 42}},
        },
        "tags": ["v1", "offline", "worker-x"],
        "context": None,
    }
    log = AuditLog(
        id=uuid.uuid4(),
        user_id=worker.id,
        event_type="complex.json",
        event_metadata=complex_metadata,
    )
    in_memory_db.add(log)
    in_memory_db.commit()

    loaded = in_memory_db.get(AuditLog, log.id)
    md = loaded.event_metadata
    assert md["event"] == "visit_created"
    assert md["payload"]["vitals"]["bp"] == [120, 80]
    assert md["payload"]["nested"]["deep"]["value"] == 42
    assert md["tags"] == ["v1", "offline", "worker-x"]
    assert md["context"] is None


def test_json_metadata_empty_and_bool(in_memory_db):
    _, worker = _build_worker_and_facility(in_memory_db)
    log_empty = AuditLog(
        id=uuid.uuid4(),
        user_id=worker.id,
        event_type="empty.meta",
        event_metadata={},
    )
    log_bools = AuditLog(
        id=uuid.uuid4(),
        user_id=worker.id,
        event_type="bool.meta",
        event_metadata={"yes": True, "no": False, "nul": None},
    )
    in_memory_db.add_all([log_empty, log_bools])
    in_memory_db.commit()

    assert in_memory_db.get(AuditLog, log_empty.id).event_metadata == {}
    bm = in_memory_db.get(AuditLog, log_bools.id).event_metadata
    assert bm["yes"] is True
    assert bm["no"] is False
    assert bm["nul"] is None


# =============== SEED IDEMPOTENCY (in-memory) ===============


def test_seed_idempotency_creates_then_updates(in_memory_db):
    from app.db.seed import seed_demo_data

    r1 = seed_demo_data(in_memory_db, commit=False)
    assert r1["created_count"] >= 4
    assert r1["facility_created"] is True
    r2 = seed_demo_data(in_memory_db, commit=False)
    assert r2["created_count"] == 0
    assert r2["facility_id"] == r1["facility_id"]
    assert r2["admin_id"] == r1["admin_id"]
    assert r2["doctor_id"] == r1["doctor_id"]
    assert r2["worker_id"] == r1["worker_id"]
