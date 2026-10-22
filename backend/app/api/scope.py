"""Facility isolation rules shared by every endpoint that returns patient data.

Workers see only their own patients. Doctors and admins see only patients whose
worker belongs to their own facility. A doctor or admin with no facility sees
nothing: missing scope fails closed instead of widening access.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Patient, User


def require_user_facility(user: User) -> uuid.UUID:
    """Return the caller's facility id, or 403 if the account has none."""
    if user.facility_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a facility",
        )
    return user.facility_id


def resolve_facility_filter(user: User, requested_facility_id: uuid.UUID | None) -> uuid.UUID:
    """Doctors and admins may only filter by their own facility."""
    own_facility_id = require_user_facility(user)
    if requested_facility_id is not None and requested_facility_id != own_facility_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access patients within your own facility",
        )
    return own_facility_id


def ensure_patient_in_scope(db: Session, patient: Patient, user: User) -> None:
    if user.role == "worker":
        if patient.worker_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This patient belongs to another worker",
            )
        return

    own_facility_id = require_user_facility(user)
    worker = db.get(User, patient.worker_id) if patient.worker_id is not None else None
    if worker is None or worker.facility_id != own_facility_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This patient is outside your facility",
        )
