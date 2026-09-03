from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.auth import require_role
from app.db.models import Patient, RiskFlag, RiskLevel, User, Visit
from app.db.session import get_session_local

router = APIRouter(prefix="/api", tags=["visits"])

_ALLOWED_RISK_LEVELS = {RiskLevel.GREEN.value, RiskLevel.YELLOW.value, RiskLevel.RED.value}


class RiskFlagIn(BaseModel):
    id: uuid.UUID
    model_risk_level: str = Field(..., min_length=1, max_length=20)
    trend_adjusted_level: str = Field(..., min_length=1, max_length=20)
    trend_reason: str | None = Field(default=None, max_length=255)

    @field_validator("model_risk_level", "trend_adjusted_level")
    @classmethod
    def validate_risk_level(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_RISK_LEVELS:
            raise ValueError(f"Risk level must be one of: {sorted(_ALLOWED_RISK_LEVELS)}")
        return normalized

    @field_validator("trend_reason")
    @classmethod
    def validate_trend_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class RiskFlagOut(BaseModel):
    id: str
    visit_id: str
    model_risk_level: str
    trend_adjusted_level: str
    trend_reason: str | None = None
    created_at: str | None = None


class VisitCreateRequest(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    worker_id: uuid.UUID
    visit_date: datetime
    systolic_bp: int | None = Field(default=None, ge=40, le=300)
    diastolic_bp: int | None = Field(default=None, ge=20, le=200)
    blood_sugar: int | None = Field(default=None, ge=20, le=1000)
    body_temp_c: float | None = Field(default=None, ge=30.0, le=45.0)
    heart_rate: int | None = Field(default=None, ge=20, le=250)
    created_locally_at: datetime
    risk_flags: list[RiskFlagIn] = Field(default_factory=list)

    @field_validator("visit_date", "created_locally_at")
    @classmethod
    def require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
        return value


class VisitOut(BaseModel):
    id: str
    patient_id: str
    worker_id: str
    visit_date: str
    systolic_bp: int | None = Field(default=None, ge=0)
    diastolic_bp: int | None = Field(default=None, ge=0)
    blood_sugar: int | None = Field(default=None, ge=0)
    body_temp_c: float | None = Field(default=None, ge=0)
    heart_rate: int | None = Field(default=None, ge=0)
    created_locally_at: str
    synced_at: str | None = None
    risk_flags: list[RiskFlagOut] = Field(default_factory=list)


def _get_db() -> Session:
    return get_session_local()()


def _serialize_risk_flag(risk_flag: RiskFlag) -> dict:
    return {
        "id": str(risk_flag.id),
        "visit_id": str(risk_flag.visit_id),
        "model_risk_level": risk_flag.model_risk_level,
        "trend_adjusted_level": risk_flag.trend_adjusted_level,
        "trend_reason": risk_flag.trend_reason,
        "created_at": risk_flag.created_at.isoformat() if risk_flag.created_at else None,
    }


def _serialize_visit(visit: Visit) -> dict:
    def _risk_key(item: RiskFlag):
        created = item.created_at or datetime.min.replace(tzinfo=timezone.utc)
        return created

    return {
        "id": str(visit.id),
        "patient_id": str(visit.patient_id),
        "worker_id": str(visit.worker_id),
        "visit_date": visit.visit_date.isoformat(),
        "systolic_bp": visit.systolic_bp,
        "diastolic_bp": visit.diastolic_bp,
        "blood_sugar": visit.blood_sugar,
        "body_temp_c": visit.body_temp_c,
        "heart_rate": visit.heart_rate,
        "created_locally_at": visit.created_locally_at.isoformat() if visit.created_locally_at else None,
        "synced_at": visit.synced_at.isoformat() if visit.synced_at else None,
        "risk_flags": [_serialize_risk_flag(flag) for flag in sorted(visit.risk_flags, key=_risk_key)],
    }


def _enforce_patient_scope(db: Session, patient: Patient, current_user: User) -> None:
    if current_user.role == "worker":
        if patient.worker_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This patient belongs to another worker",
            )
    else:
        if current_user.facility_id is not None and patient.worker_id is not None:
            worker = db.query(User).filter(User.id == patient.worker_id).first()
            if worker is None or worker.facility_id != current_user.facility_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This patient is outside your facility",
                )


@router.get("/patients/{patient_id}/visits")
def list_patient_visits(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_role("worker", "doctor", "admin")),
):
    db = _get_db()
    try:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        _enforce_patient_scope(db, patient, current_user)

        visits = (
            db.query(Visit)
            .filter(Visit.patient_id == patient.id)
            .order_by(Visit.created_locally_at.desc())
            .all()
        )
        return [_serialize_visit(visit) for visit in visits]
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to fetch patient visits") from exc
    finally:
        db.close()


@router.post("/patients/{patient_id}/visits")
def create_patient_visit(
    patient_id: uuid.UUID,
    payload: VisitCreateRequest,
    current_user: User = Depends(require_role("worker")),
):
    db = _get_db()
    try:
        if payload.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient ID in path must match patient_id in payload",
            )

        if payload.worker_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="worker_id must match the authenticated worker",
            )

        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        if patient.worker_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This patient belongs to another worker",
            )

        existing = db.query(Visit).filter(Visit.id == payload.id).first()
        if existing is not None:
            if existing.patient_id != patient_id or existing.worker_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This visit belongs to a different patient or worker",
                )
            return _serialize_visit(existing)

        visit_date_value = payload.visit_date.date()
        visit = Visit(
            id=payload.id,
            patient_id=patient_id,
            worker_id=current_user.id,
            visit_date=visit_date_value,
            systolic_bp=payload.systolic_bp,
            diastolic_bp=payload.diastolic_bp,
            blood_sugar=payload.blood_sugar,
            body_temp_c=payload.body_temp_c,
            heart_rate=payload.heart_rate,
            created_locally_at=payload.created_locally_at,
            synced_at=datetime.now(timezone.utc),
        )
        db.add(visit)
        db.flush()

        risk_flag_ids_seen: set[uuid.UUID] = set()
        for flag_in in payload.risk_flags:
            if flag_in.id in risk_flag_ids_seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate risk flag id: {flag_in.id}",
                )
            risk_flag_ids_seen.add(flag_in.id)

            existing_flag = db.query(RiskFlag).filter(RiskFlag.id == flag_in.id).first()
            if existing_flag is not None:
                if existing_flag.visit_id != visit.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Risk flag {flag_in.id} already attached to another visit",
                    )
                continue

            db.add(
                RiskFlag(
                    id=flag_in.id,
                    visit_id=visit.id,
                    model_risk_level=flag_in.model_risk_level,
                    trend_adjusted_level=flag_in.trend_adjusted_level,
                    trend_reason=flag_in.trend_reason,
                )
            )

        db.commit()
        db.refresh(visit)
        return _serialize_visit(visit)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:  # pragma: no cover
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create visit") from exc
    finally:
        db.close()
