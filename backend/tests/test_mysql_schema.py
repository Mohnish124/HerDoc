import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    AuditLog,
    Facility,
    Patient,
    RefreshToken,
    Review,
    ReviewStatus,
    RiskFlag,
    User,
    UserRole,
    Visit,
)
from app.db.seed import seed_demo_data


@pytest.fixture()
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def test_tables_can_be_created(in_memory_db):
    inspector = inspect(in_memory_db.bind)
    for table_name in [
        "facilities",
        "users",
        "patients",
        "visits",
        "risk_flags",
        "reviews",
        "refresh_tokens",
        "audit_log",
    ]:
        assert inspector.has_table(table_name), f"Missing table: {table_name}"


def test_seed_demo_data_is_idempotent(in_memory_db):
    first = seed_demo_data(in_memory_db)
    second = seed_demo_data(in_memory_db)

    assert first["facility_id"] == second["facility_id"]
    assert first["admin_id"] == second["admin_id"]
    assert first["doctor_id"] == second["doctor_id"]
    assert first["worker_id"] == second["worker_id"]
    for email in ["admin@herdoc.local", "doctor@herdoc.local", "worker@herdoc.local"]:
        assert first["users"][email]["id"] == second["users"][email]["id"]
        assert first["users"][email]["role"] == second["users"][email]["role"]
    assert second["created_count"] == 0
    assert in_memory_db.query(Facility).filter_by(name="Demo PHC").count() == 1
    assert in_memory_db.query(User).filter_by(email="admin@herdoc.local").count() == 1
    assert in_memory_db.query(User).filter_by(email="doctor@herdoc.local").count() == 1
    assert in_memory_db.query(User).filter_by(email="worker@herdoc.local").count() == 1


def test_inserting_facility_and_users(in_memory_db):
    facility = Facility(id=uuid.uuid4(), name="Facility A", region="North", type="PHC")
    admin = User(
        id=uuid.uuid4(),
        role=UserRole.ADMIN.value,
        name="Admin A",
        phone="9100000001",
        email="admin_a@example.com",
        facility_id=facility.id,
        password_hash="hash",
    )
    doctor = User(
        id=uuid.uuid4(),
        role=UserRole.DOCTOR.value,
        name="Doctor A",
        phone="9100000002",
        email="doctor_a@example.com",
        facility_id=facility.id,
        password_hash="hash",
    )
    worker = User(
        id=uuid.uuid4(),
        role=UserRole.WORKER.value,
        name="Worker A",
        phone="9100000003",
        email="worker_a@example.com",
        facility_id=facility.id,
        password_hash="hash",
    )

    in_memory_db.add_all([facility, admin, doctor, worker])
    in_memory_db.commit()

    assert in_memory_db.get(Facility, facility.id) is not None
    assert in_memory_db.get(User, admin.id).email == "admin_a@example.com"
    assert in_memory_db.get(User, doctor.id).role == UserRole.DOCTOR.value
    assert in_memory_db.get(User, worker.id).facility_id == facility.id


def test_relationships_patient_worker_visit_review_refresh_and_audit(in_memory_db):
    facility = Facility(id=uuid.uuid4(), name="Facility B", region="South", type="PHC")
    worker = User(
        id=uuid.uuid4(),
        role=UserRole.WORKER.value,
        name="Worker One",
        phone="9200000001",
        email="worker_one@example.com",
        facility_id=facility.id,
        password_hash="hash",
    )
    patient = Patient(
        id=uuid.uuid4(),
        worker_id=worker.id,
        name="Patient One",
        age=28,
        village="Village A",
    )
    visit = Visit(
        id=uuid.uuid4(),
        patient_id=patient.id,
        worker_id=worker.id,
        visit_date=date(2026, 8, 18),
        created_locally_at=datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc),
    )
    risk_flag = RiskFlag(
        id=uuid.uuid4(),
        visit_id=visit.id,
        model_risk_level="high",
        trend_adjusted_level="medium",
        trend_reason="trend change",
    )
    review = Review(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=worker.id,
        status=ReviewStatus.PENDING.value,
        notes="needs review",
    )
    refresh = RefreshToken(
        id=uuid.uuid4(),
        user_id=worker.id,
        token_hash="abc123",
        expires_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    audit = AuditLog(
        id=uuid.uuid4(),
        user_id=worker.id,
        event_type="visit_saved",
        event_metadata={"source": "mobile", "status": "ok"},
    )

    in_memory_db.add_all([facility, worker, patient, visit, risk_flag, review, refresh, audit])
    in_memory_db.commit()

    assert visit.patient_id == patient.id
    assert visit.worker_id == worker.id
    assert patient.visits[0].id == visit.id
    assert worker.visits[0].id == visit.id
    assert risk_flag.visit.id == visit.id
    assert review.patient.id == patient.id
    assert refresh.user_id == worker.id
    assert audit.user_id == worker.id
    assert audit.event_metadata["source"] == "mobile"


def test_transaction_rollback(in_memory_db):
    with pytest.raises(RuntimeError):
        with in_memory_db.begin():
            facility = Facility(id=uuid.uuid4(), name="Rollback Facility", region="West", type="PHC")
            in_memory_db.add(facility)
            raise RuntimeError("rollback this transaction")

    assert in_memory_db.query(Facility).filter_by(name="Rollback Facility").count() == 0


def test_duplicate_uuid_behavior(in_memory_db):
    duplicate_id = uuid.uuid4()
    facility_one = Facility(id=duplicate_id, name="Unique ID Facility", region="Central", type="PHC")
    facility_two = Facility(id=duplicate_id, name="Duplicate ID Facility", region="North", type="PHC")

    in_memory_db.add(facility_one)
    in_memory_db.commit()

    with pytest.raises(IntegrityError):
        in_memory_db.add(facility_two)
        in_memory_db.commit()


def test_foreign_key_rejection(in_memory_db):
    patient = Patient(
        id=uuid.uuid4(),
        worker_id=uuid.uuid4(),
        name="Invalid Worker Patient",
        age=31,
        village="Village X",
    )

    with pytest.raises(IntegrityError):
        in_memory_db.add(patient)
        in_memory_db.commit()


def test_mysql_json_metadata(in_memory_db):
    audit = AuditLog(
        id=uuid.uuid4(),
        event_type="sync_complete",
        event_metadata={"payload": {"device": "mobile", "success": True, "count": 3}},
    )

    in_memory_db.add(audit)
    in_memory_db.commit()

    loaded = in_memory_db.get(AuditLog, audit.id)
    assert loaded is not None
    assert loaded.event_metadata["payload"]["device"] == "mobile"
    assert loaded.event_metadata["payload"]["success"] is True
    assert loaded.event_metadata["payload"]["count"] == 3


def test_email_uniqueness_enforced(in_memory_db):
    facility = Facility(id=uuid.uuid4(), name="Facility E", region="Central", type="sub_center")
    user1 = User(
        id=uuid.uuid4(),
        role=UserRole.ADMIN.value,
        name="Admin One",
        email="same@example.com",
        facility_id=facility.id,
    )
    in_memory_db.add_all([facility, user1])
    in_memory_db.flush()

    with pytest.raises(IntegrityError):
        user2 = User(
            id=uuid.uuid4(),
            role=UserRole.DOCTOR.value,
            name="Doctor Two",
            phone="9400000001",
            email="same@example.com",
            facility_id=facility.id,
        )
        in_memory_db.add(user2)
        in_memory_db.commit()
