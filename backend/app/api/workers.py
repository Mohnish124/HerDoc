from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.models import AuditLog, Facility, Patient, RefreshToken, User, UserRole, Visit
from app.db.session import get_session_local

router = APIRouter(prefix="/api", tags=["workers"])


class WorkerStatusUpdateRequest(BaseModel):
    is_active: bool


def _get_db() -> Session:
    return get_session_local()()


@router.get("/workers")
def list_workers(
    facility_id: uuid.UUID | None = Query(default=None),
    current_admin: User = Depends(require_admin()),
):
    db = _get_db()
    try:
        # Determine facility scope
        target_facility_id = facility_id
        if current_admin.facility_id is not None:
            target_facility_id = current_admin.facility_id

        query = db.query(User).filter(User.role == UserRole.WORKER.value)
        if target_facility_id is not None:
            query = query.filter(User.facility_id == target_facility_id)

        workers = query.order_by(User.name.asc()).all()
        results = []

        for w in workers:
            # Latest sync from visits
            latest_visit = (
                db.query(Visit)
                .filter(Visit.worker_id == w.id)
                .order_by(Visit.created_locally_at.desc())
                .first()
            )
            last_sync_time = None
            if latest_visit:
                last_sync_time = (
                    latest_visit.synced_at.isoformat()
                    if latest_visit.synced_at
                    else (latest_visit.created_locally_at.isoformat() if latest_visit.created_locally_at else None)
                )

            # Total patients count
            patient_count = db.query(Patient).filter(Patient.worker_id == w.id).count()

            # Facility info
            fac_name = "Unassigned"
            if w.facility_id:
                fac = db.get(Facility, w.facility_id)
                if fac:
                    fac_name = fac.name

            results.append({
                "id": str(w.id),
                "name": w.name,
                "phone": w.phone,
                "is_active": bool(w.is_active),
                "facility_id": str(w.facility_id) if w.facility_id else None,
                "facility_name": fac_name,
                "last_sync": last_sync_time,
                "patients_count": patient_count,
            })

        return results
    finally:
        db.close()


@router.patch("/workers/{worker_id}/status")
@router.post("/workers/{worker_id}/deactivate")
def update_worker_status(
    worker_id: uuid.UUID,
    payload: WorkerStatusUpdateRequest | None = None,
    current_admin: User = Depends(require_admin()),
):
    # Default to deactivating if payload is omitted (e.g. POST /workers/{id}/deactivate)
    target_active = payload.is_active if payload is not None else False

    db = _get_db()
    try:
        worker = db.get(User, worker_id)
        if worker is None or worker.role != UserRole.WORKER.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field worker not found")

        # Check facility scope
        if current_admin.facility_id is not None and worker.facility_id != current_admin.facility_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify workers outside your assigned facility",
            )

        worker.is_active = target_active

        # If deactivating, revoke all active refresh tokens immediately
        if not target_active:
            tokens = db.query(RefreshToken).filter(RefreshToken.user_id == worker.id, RefreshToken.revoked_at.is_(None)).all()
            now = datetime.now(timezone.utc)
            for t in tokens:
                t.revoked_at = now

        action_name = "worker_activated" if target_active else "worker_deactivated"
        db.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=current_admin.id,
                event_type=action_name,
                event_metadata={
                    "worker_id": str(worker.id),
                    "worker_name": worker.name,
                    "worker_phone": worker.phone,
                    "is_active": target_active,
                    "admin_id": str(current_admin.id),
                },
            )
        )
        db.commit()
        db.refresh(worker)

        return {
            "id": str(worker.id),
            "name": worker.name,
            "phone": worker.phone,
            "is_active": bool(worker.is_active),
            "message": f"Worker account {'activated' if target_active else 'deactivated'} successfully",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to update worker status",
        ) from exc
    finally:
        db.close()
