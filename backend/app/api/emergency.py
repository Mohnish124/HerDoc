from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.auth import _log_audit, require_role
from app.db.models import Facility, User
from app.db.session import get_session_local
from app.services import telegram_service
from app.services.telegram_service import TelegramError, TelegramNotConfiguredError

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["emergency"])

# Any authenticated HerDoc user may raise an SOS.
require_emergency_user = require_role("worker", "doctor", "admin")


class EmergencyRequest(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    message: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _coords_together(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.message is not None:
            self.message = self.message.strip() or None
        return self


def _get_db() -> Session:
    return get_session_local()()


def _record(db: Session, user: User, outcome: str, payload: EmergencyRequest) -> None:
    """Best-effort audit record; never lets a DB problem mask the SOS result."""
    try:
        _log_audit(
            db,
            user.id,
            "emergency.sos",
            {
                "outcome": outcome,
                "role": user.role,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "has_note": payload.message is not None,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        LOGGER.exception("Failed to write emergency audit log")


@router.post("/emergency")
def send_emergency(payload: EmergencyRequest, current_user: User = Depends(require_emergency_user)) -> dict[str, Any]:
    db = _get_db()
    try:
        facility_name = None
        if current_user.facility_id is not None:
            try:
                facility = db.get(Facility, current_user.facility_id)
                facility_name = facility.name if facility else None
            except Exception:
                LOGGER.exception("Facility lookup failed for emergency alert")

        try:
            telegram_service.send_emergency_alert(
                user_name=current_user.name,
                role=current_user.role,
                phone=current_user.phone,
                facility_name=facility_name,
                latitude=payload.latitude,
                longitude=payload.longitude,
                note=payload.message,
            )
        except TelegramNotConfiguredError:
            _record(db, current_user, "not_configured", payload)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Emergency alerts are not configured on the server",
            )
        except TelegramError:
            _record(db, current_user, "failed", payload)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not deliver the emergency alert. Please call emergency services directly.",
            )

        _record(db, current_user, "sent", payload)
        return {"status": "sent", "location_included": payload.latitude is not None}
    finally:
        db.close()
