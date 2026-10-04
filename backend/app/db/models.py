import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, func, Column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.uuid_types import GUID



class UserRole(str, Enum):
    WORKER = "worker"
    DOCTOR = "doctor"
    ADMIN = "admin"


class FacilityType(str, Enum):
    PHC = "PHC"
    SUB_CENTER = "sub_center"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVIEWED = "reviewed"
    REFERRED = "referred"


class RiskLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    region = Column(String(255), nullable=False)
    type = Column(String(30), nullable=False)

    users = relationship("User", back_populates="facility")

    __table_args__ = (Index("ix_facilities_name", "name"),)


class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    role = Column(String(20), nullable=False, default=UserRole.WORKER.value)
    name = Column(String(255), nullable=False)
    phone = Column(String(32), nullable=True, unique=True)
    email = Column(String(255), nullable=True, unique=True)
    password_hash = Column(String(255), nullable=True)
    pin_hash = Column(String(255), nullable=True)
    facility_id = Column(GUID, ForeignKey("facilities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    facility = relationship("Facility", back_populates="users")
    patients = relationship("Patient", back_populates="worker")
    visits = relationship("Visit", back_populates="worker")
    reviews = relationship("Review", back_populates="doctor")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("ix_users_facility_id", "facility_id"),
        Index("ix_users_created_at", "created_at"),
    )


class Patient(Base):
    __tablename__ = "patients"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    worker_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    phone = Column(String(32), nullable=True)
    village = Column(String(255), nullable=False)
    edd = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    worker = relationship("User", back_populates="patients")
    visits = relationship("Visit", back_populates="patient")
    reviews = relationship("Review", back_populates="patient")

    __table_args__ = (
        Index("ix_patients_worker_id", "worker_id"),
        Index("ix_patients_created_at", "created_at"),
    )


class Visit(Base):
    __tablename__ = "visits"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    patient_id = Column(GUID, ForeignKey("patients.id"), nullable=False)
    worker_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    visit_date = Column(Date, nullable=False)
    systolic_bp = Column(Integer, nullable=True)
    diastolic_bp = Column(Integer, nullable=True)
    blood_sugar = Column(Integer, nullable=True)
    body_temp_c = Column(Float, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    created_locally_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("Patient", back_populates="visits")
    worker = relationship("User", back_populates="visits")
    risk_flags = relationship("RiskFlag", back_populates="visit")

    __table_args__ = (
        Index("ix_visits_patient_id", "patient_id"),
        Index("ix_visits_worker_id", "worker_id"),
        Index("ix_visits_created_locally_at", "created_locally_at"),
        Index("ix_visits_synced_at", "synced_at"),
    )


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    visit_id = Column(GUID, ForeignKey("visits.id"), nullable=False)
    model_risk_level = Column(String(20), nullable=False)
    trend_adjusted_level = Column(String(20), nullable=False)
    trend_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    visit = relationship("Visit", back_populates="risk_flags")

    __table_args__ = (
        Index("ix_risk_flags_visit_id", "visit_id"),
        Index("ix_risk_flags_created_at", "created_at"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    patient_id = Column(GUID, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default=ReviewStatus.PENDING.value, nullable=False)
    notes = Column(String(1500), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("Patient", back_populates="reviews")
    doctor = relationship("User", back_populates="reviews")

    __table_args__ = (
        Index("ix_reviews_patient_id", "patient_id"),
        Index("ix_reviews_doctor_id", "doctor_id"),
        Index("ix_reviews_status", "status"),
        Index("ix_reviews_reviewed_at", "reviewed_at"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(100), nullable=False)
    event_metadata = Column("metadata", JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_log_user_id", "user_id"),
        Index("ix_audit_log_created_at", "created_at"),
    )


def facility_factory(name: str, region: str, facility_type: str = FacilityType.PHC.value) -> Facility:
    return Facility(id=uuid.uuid4(), name=name, region=region, type=facility_type)


def user_factory(
    *,
    role: str,
    name: str,
    facility_id: uuid.UUID | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> User:
    return User(
        id=uuid.uuid4(),
        role=role,
        name=name,
        phone=phone,
        email=email,
        facility_id=facility_id,
        password_hash="demo-hash",
    )


UserRoleAlias = UserRole
VisitStatusAlias = ReviewStatus
