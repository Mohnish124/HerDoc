from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.auth import require_role
from app.db.models import AuditLog, Patient, Review, ReviewStatus, User
from app.db.session import get_session_local

router = APIRouter(prefix="/api", tags=["reviews"])

_VALID_REVIEW_STATUSES = {
    ReviewStatus.PENDING.value,
    ReviewStatus.REVIEWED.value,
    ReviewStatus.REFERRED.value,
    ReviewStatus.APPROVED.value,
    ReviewStatus.REJECTED.value,
}


class ReviewCreateRequest(BaseModel):
    patient_id: uuid.UUID
    status: str = Field(..., min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=1500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _VALID_REVIEW_STATUSES:
            raise ValueError(f"Review status must be one of: {sorted(_VALID_REVIEW_STATUSES)}")
        return normalized

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def _get_db() -> Session:
    return get_session_local()()


@router.post("/reviews")
def create_or_update_review(
    payload: ReviewCreateRequest,
    current_user: User = Depends(require_role("doctor", "admin")),
):
    db = _get_db()
    try:
        patient = db.get(Patient, payload.patient_id)
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        # Doctors can only review patients within their assigned facility
        if current_user.role == "doctor" and current_user.facility_id is not None:
            worker = patient.worker
            if worker and worker.facility_id != current_user.facility_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Doctors can only review patients within their own facility",
                )

        now = datetime.now(timezone.utc)
        effective_reviewed_at = now if payload.status != ReviewStatus.PENDING.value else None

        review = (
            db.query(Review)
            .filter(Review.patient_id == payload.patient_id)
            .order_by(Review.reviewed_at.desc())
            .first()
        )

        if review is None:
            review = Review(
                id=uuid.uuid4(),
                patient_id=payload.patient_id,
                doctor_id=current_user.id,
                status=payload.status,
                notes=payload.notes,
                reviewed_at=effective_reviewed_at,
            )
            db.add(review)
        else:
            review.doctor_id = current_user.id
            review.status = payload.status
            review.notes = payload.notes
            review.reviewed_at = effective_reviewed_at

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=current_user.id,
                event_type="patient_reviewed",
                event_metadata={
                    "patient_id": str(payload.patient_id),
                    "status": payload.status,
                    "doctor_name": current_user.name,
                    "doctor_role": current_user.role,
                    "notes": payload.notes,
                },
            )
        )
        db.commit()
        db.refresh(review)

        return {
            "id": str(review.id),
            "patient_id": str(review.patient_id),
            "doctor_id": str(review.doctor_id),
            "doctor_name": current_user.name,
            "status": review.status,
            "notes": review.notes,
            "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to save clinical review",
        ) from exc
    finally:
        db.close()
