from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.auth import require_role
from app.db.models import Patient, User
from app.db.session import get_session_local

router = APIRouter(prefix="/api", tags=["patients"])


class PatientCreateRequest(BaseModel):
    id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    age: int = Field(..., ge=1, le=120)
    village: str = Field(..., min_length=1, max_length=255)
    edd: date
    phone: str | None = Field(default=None, min_length=7, max_length=32)

    @field_validator("name", "village")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) < 7 or len(cleaned) > 32:
            raise ValueError("Phone number must be between 7 and 32 characters")
        if not all(ch.isdigit() or ch in "+()-. " for ch in cleaned):
            raise ValueError("Phone number contains invalid characters")
        return cleaned


class PatientOut(BaseModel):
    id: str
    worker_id: str
    name: str
    age: int
    village: str
    edd: str | None
    phone: str | None
    created_at: str | None = None


def _get_db() -> Session:
    return get_session_local()()


def _serialize_patient(patient: Patient) -> dict:
    return {
        "id": str(patient.id),
        "worker_id": str(patient.worker_id),
        "name": patient.name,
        "age": patient.age,
        "village": patient.village,
        "edd": patient.edd.isoformat() if patient.edd else None,
        "phone": patient.phone,
        "created_at": patient.created_at.isoformat() if patient.created_at else None,
    }


@router.get("/patients")
def list_patients(current_user: User = Depends(require_role("worker", "doctor", "admin"))):
    db = _get_db()
    try:
        if current_user.role == "worker":
            patients = db.query(Patient).filter(Patient.worker_id == current_user.id).order_by(Patient.created_at.desc()).all()
        else:
            if current_user.facility_id is not None:
                patients = (
                    db.query(Patient)
                    .join(User, Patient.worker_id == User.id)
                    .filter(User.facility_id == current_user.facility_id)
                    .order_by(Patient.created_at.desc())
                    .all()
                )
            else:
                patients = db.query(Patient).order_by(Patient.created_at.desc()).all()
        return [_serialize_patient(patient) for patient in patients]
    finally:
        db.close()


@router.post("/patients")
def create_patient(payload: PatientCreateRequest, current_user: User = Depends(require_role("worker"))):
    db = _get_db()
    try:
        existing = db.query(Patient).filter(Patient.id == payload.id).first()
        if existing is not None:
            if current_user.role == "worker" and existing.worker_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This patient belongs to another worker",
                )
            return _serialize_patient(existing)

        patient = Patient(
            id=payload.id,
            worker_id=current_user.id,
            name=payload.name,
            age=payload.age,
            village=payload.village,
            edd=payload.edd,
            phone=payload.phone,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return _serialize_patient(patient)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create patient") from exc
    finally:
        db.close()


@router.get("/patients/{patient_id}")
def get_patient(patient_id: uuid.UUID, current_user: User = Depends(require_role("worker", "doctor", "admin"))):
    db = _get_db()
    try:
        patient = db.get(Patient, patient_id)
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        # Guard against IDOR: worker can only access own patients
        if current_user.role == "worker":
            if patient.worker_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This patient belongs to another worker",
                )
        # Doctor can only access patients within their assigned facility
        elif current_user.role == "doctor" and current_user.facility_id is not None:
            worker = patient.worker
            if worker and worker.facility_id != current_user.facility_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This patient is outside your assigned facility",
                )

        worker = patient.worker
        res = _serialize_patient(patient)
        res["worker"] = {
            "id": str(worker.id) if worker else None,
            "name": worker.name if worker else "Unassigned",
            "phone": worker.phone if worker else None,
        }
        return res
    finally:
        db.close()
