from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import require_role
from app.db.models import Patient, Review, RiskFlag, User, Visit
from app.db.session import get_session_local

router = APIRouter(prefix="/api", tags=["sync"])

_ALLOWED_RISK_LEVELS = {"green", "yellow", "red"}


class SyncBatchRequest(BaseModel):
    patients: list[dict[str, Any]] = Field(default_factory=list)
    visits: list[dict[str, Any]] = Field(default_factory=list)
    risk_flags: list[dict[str, Any]] = Field(default_factory=list)
    last_synced_at: datetime | str | None = None


class SyncBatchResult(BaseModel):
    success: int = 0
    updated: int = 0
    already_synced: int = 0
    failed: int = 0


def _get_db() -> Session:
    return get_session_local()()


def _normalize_timestamp(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_uuid(raw: Any) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str):
        return uuid.UUID(raw)
    raise ValueError("Invalid UUID")


def _validate_patient_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Patient record must be an object")
    patient_id = _coerce_uuid(payload.get("id"))
    worker_id = _coerce_uuid(payload.get("worker_id"))
    name = str(payload.get("name", "")).strip()
    age = payload.get("age")
    village = str(payload.get("village", "")).strip()
    phone = payload.get("phone")
    edd = payload.get("edd")

    if not name:
        raise ValueError("Patient name is required")
    if not isinstance(age, int) or age < 1 or age > 120:
        raise ValueError("Patient age must be a valid integer between 1 and 120")
    if not village:
        raise ValueError("Patient village is required")

    if phone is not None:
        phone = str(phone).strip()
        if not phone:
            phone = None
        elif len(phone) < 7 or len(phone) > 32:
            raise ValueError("Phone number must be between 7 and 32 characters")

    if edd is not None:
        if isinstance(edd, datetime):
            edd_date = edd.date()
        elif isinstance(edd, date):
            edd_date = edd
        else:
            edd_date = datetime.fromisoformat(str(edd).replace("Z", "+00:00")).date()
    else:
        edd_date = None

    return {
        "id": patient_id,
        "worker_id": worker_id,
        "name": name,
        "age": age,
        "village": village,
        "edd": edd_date,
        "phone": phone,
    }


def _validate_visit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Visit record must be an object")
    visit_id = _coerce_uuid(payload.get("id"))
    patient_id = _coerce_uuid(payload.get("patient_id"))
    worker_id = _coerce_uuid(payload.get("worker_id"))
    created_locally_at = _normalize_timestamp(payload.get("created_locally_at"))
    if created_locally_at is None:
        raise ValueError("created_locally_at is required")

    visit_date_raw = payload.get("visit_date")
    if isinstance(visit_date_raw, datetime):
        visit_date = visit_date_raw.date()
    elif isinstance(visit_date_raw, date):
        visit_date = visit_date_raw
    else:
        visit_date = datetime.fromisoformat(str(visit_date_raw).replace("Z", "+00:00")).date()

    def _int_or_none(value: Any, *, min_value: int | None = None, max_value: int | None = None) -> int | None:
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("Invalid numeric value")
        num = int(value)
        if min_value is not None and num < min_value:
            raise ValueError("Value below minimum")
        if max_value is not None and num > max_value:
            raise ValueError("Value exceeds maximum")
        return num

    def _float_or_none(value: Any, *, min_value: float | None = None, max_value: float | None = None) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("Invalid numeric value")
        num = float(value)
        if min_value is not None and num < min_value:
            raise ValueError("Value below minimum")
        if max_value is not None and num > max_value:
            raise ValueError("Value exceeds maximum")
        return num

    return {
        "id": visit_id,
        "patient_id": patient_id,
        "worker_id": worker_id,
        "visit_date": visit_date,
        "systolic_bp": _int_or_none(payload.get("systolic_bp"), min_value=40, max_value=300),
        "diastolic_bp": _int_or_none(payload.get("diastolic_bp"), min_value=20, max_value=200),
        "blood_sugar": _int_or_none(payload.get("blood_sugar"), min_value=20, max_value=1000),
        "body_temp_c": _float_or_none(payload.get("body_temp_c"), min_value=30.0, max_value=45.0),
        "heart_rate": _int_or_none(payload.get("heart_rate"), min_value=20, max_value=250),
        "created_locally_at": created_locally_at,
    }


def _validate_risk_flag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Risk flag record must be an object")
    risk_id = _coerce_uuid(payload.get("id"))
    visit_id = _coerce_uuid(payload.get("visit_id"))
    model_risk_level = str(payload.get("model_risk_level", "")).strip().lower()
    trend_adjusted_level = str(payload.get("trend_adjusted_level", "")).strip().lower()
    trend_reason_raw = payload.get("trend_reason")

    if model_risk_level not in _ALLOWED_RISK_LEVELS:
        raise ValueError("model_risk_level must be one of green, yellow, red")
    if trend_adjusted_level not in _ALLOWED_RISK_LEVELS:
        raise ValueError("trend_adjusted_level must be one of green, yellow, red")
    trend_reason = None if trend_reason_raw is None else str(trend_reason_raw).strip() or None

    return {
        "id": risk_id,
        "visit_id": visit_id,
        "model_risk_level": model_risk_level,
        "trend_adjusted_level": trend_adjusted_level,
        "trend_reason": trend_reason,
    }


def _record_is_same_patient(existing: Patient, candidate: dict[str, Any]) -> bool:
    return (
        existing.worker_id == candidate["worker_id"]
        and existing.name == candidate["name"]
        and existing.age == candidate["age"]
        and existing.village == candidate["village"]
        and (existing.edd.isoformat() if existing.edd else None) == (candidate["edd"].isoformat() if candidate["edd"] else None)
        and (existing.phone.strip() if existing.phone else None) == (candidate["phone"].strip() if candidate["phone"] else None)
    )


def _to_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _dt_matches(dt1: datetime | None, dt2: datetime | None) -> bool:
    if dt1 is None and dt2 is None:
        return True
    if dt1 is None or dt2 is None:
        return False
    u1 = _to_utc_datetime(dt1)
    u2 = _to_utc_datetime(dt2)
    return abs((u1 - u2).total_seconds()) <= 2


def _record_is_same_visit(existing: Visit, candidate: dict[str, Any]) -> bool:
    body_temp_match = (
        existing.body_temp_c is None and candidate["body_temp_c"] is None
    ) or (
        existing.body_temp_c is not None
        and candidate["body_temp_c"] is not None
        and round(existing.body_temp_c, 2) == round(candidate["body_temp_c"], 2)
    )
    return (
        existing.patient_id == candidate["patient_id"]
        and existing.worker_id == candidate["worker_id"]
        and existing.visit_date == candidate["visit_date"]
        and existing.systolic_bp == candidate["systolic_bp"]
        and existing.diastolic_bp == candidate["diastolic_bp"]
        and existing.blood_sugar == candidate["blood_sugar"]
        and body_temp_match
        and existing.heart_rate == candidate["heart_rate"]
        and _dt_matches(existing.created_locally_at, candidate["created_locally_at"])
    )


def _record_is_same_risk_flag(existing: RiskFlag, candidate: dict[str, Any]) -> bool:
    return (
        existing.visit_id == candidate["visit_id"]
        and existing.model_risk_level == candidate["model_risk_level"]
        and existing.trend_adjusted_level == candidate["trend_adjusted_level"]
        and (existing.trend_reason.strip() if existing.trend_reason else None) == (candidate["trend_reason"].strip() if candidate["trend_reason"] else None)
    )


@router.post("/sync")
def sync_batch(payload: SyncBatchRequest, current_user: User = Depends(require_role("worker"))):
    db = _get_db()
    try:
        patient_results = SyncBatchResult()
        visit_results = SyncBatchResult()
        risk_results = SyncBatchResult()

        patients = []
        for item in payload.patients:
            try:
                patient = _validate_patient_payload(item)
                if patient["worker_id"] != current_user.id:
                    patient_results.failed += 1
                    continue
                patients.append(patient)
            except Exception:
                patient_results.failed += 1

        visits = []
        for item in payload.visits:
            try:
                visit = _validate_visit_payload(item)
                if visit["worker_id"] != current_user.id:
                    visit_results.failed += 1
                    continue
                visits.append(visit)
            except Exception:
                visit_results.failed += 1

        risk_flags = []
        for item in payload.risk_flags:
            try:
                flag = _validate_risk_flag_payload(item)
                risk_flags.append(flag)
            except Exception:
                risk_results.failed += 1

        now = datetime.now(timezone.utc)
        cutoff = _normalize_timestamp(payload.last_synced_at)
        if cutoff is None:
            cutoff = datetime.fromtimestamp(0, tz=timezone.utc)

        with db.begin():
            known_patients: dict[str, Patient] = {}
            for patient in patients:
                existing = db.get(Patient, patient["id"])
                if existing is None:
                    existing = Patient(
                        id=patient["id"],
                        worker_id=patient["worker_id"],
                        name=patient["name"],
                        age=patient["age"],
                        village=patient["village"],
                        edd=patient["edd"],
                        phone=patient["phone"],
                    )
                    db.add(existing)
                    patient_results.success += 1
                else:
                    if _record_is_same_patient(existing, patient):
                        patient_results.already_synced += 1
                    else:
                        existing.worker_id = patient["worker_id"]
                        existing.name = patient["name"]
                        existing.age = patient["age"]
                        existing.village = patient["village"]
                        existing.edd = patient["edd"]
                        existing.phone = patient["phone"]
                        patient_results.updated += 1
                known_patients[str(patient["id"])] = existing

            known_visits: dict[str, Visit] = {}
            for visit in visits:
                patient = known_patients.get(str(visit["patient_id"]))
                if patient is None:
                    patient = db.get(Patient, visit["patient_id"])
                if patient is None:
                    patient = db.query(Patient).filter(Patient.id == visit["patient_id"]).first()
                if patient is None:
                    visit_results.failed += 1
                    continue
                if patient.worker_id != current_user.id:
                    visit_results.failed += 1
                    continue

                existing = db.get(Visit, visit["id"])
                if existing is None:
                    existing = Visit(
                        id=visit["id"],
                        patient_id=visit["patient_id"],
                        worker_id=visit["worker_id"],
                        visit_date=visit["visit_date"],
                        systolic_bp=visit["systolic_bp"],
                        diastolic_bp=visit["diastolic_bp"],
                        blood_sugar=visit["blood_sugar"],
                        body_temp_c=visit["body_temp_c"],
                        heart_rate=visit["heart_rate"],
                        created_locally_at=visit["created_locally_at"],
                        synced_at=now,
                    )
                    db.add(existing)
                    visit_results.success += 1
                else:
                    if existing.patient_id != visit["patient_id"] or existing.worker_id != current_user.id:
                        visit_results.failed += 1
                        continue
                    if _record_is_same_visit(existing, visit):
                        existing.synced_at = now
                        visit_results.already_synced += 1
                    else:
                        existing.patient_id = visit["patient_id"]
                        existing.worker_id = visit["worker_id"]
                        existing.visit_date = visit["visit_date"]
                        existing.systolic_bp = visit["systolic_bp"]
                        existing.diastolic_bp = visit["diastolic_bp"]
                        existing.blood_sugar = visit["blood_sugar"]
                        existing.body_temp_c = visit["body_temp_c"]
                        existing.heart_rate = visit["heart_rate"]
                        existing.created_locally_at = visit["created_locally_at"]
                        existing.synced_at = now
                        visit_results.updated += 1
                known_visits[str(visit["id"])] = existing

            for flag in risk_flags:
                visit = known_visits.get(str(flag["visit_id"]))
                if visit is None:
                    visit = db.get(Visit, flag["visit_id"])
                if visit is None:
                    risk_results.failed += 1
                    continue
                if visit.worker_id != current_user.id:
                    risk_results.failed += 1
                    continue

                existing = db.get(RiskFlag, flag["id"])
                if existing is None:
                    existing = RiskFlag(
                        id=flag["id"],
                        visit_id=flag["visit_id"],
                        model_risk_level=flag["model_risk_level"],
                        trend_adjusted_level=flag["trend_adjusted_level"],
                        trend_reason=flag["trend_reason"],
                    )
                    db.add(existing)
                    risk_results.success += 1
                else:
                    if _record_is_same_risk_flag(existing, flag):
                        risk_results.already_synced += 1
                    else:
                        existing.visit_id = flag["visit_id"]
                        existing.model_risk_level = flag["model_risk_level"]
                        existing.trend_adjusted_level = flag["trend_adjusted_level"]
                        existing.trend_reason = flag["trend_reason"]
                        risk_results.updated += 1

        review_cutoff = (cutoff - timedelta(seconds=2)) if cutoff > datetime.fromtimestamp(0, tz=timezone.utc) else cutoff
        review_rows = (
            db.query(Review)
            .join(Patient, Review.patient_id == Patient.id)
            .filter(Patient.worker_id == current_user.id)
            .filter(Review.reviewed_at.is_not(None))
            .filter(Review.reviewed_at >= review_cutoff)
            .order_by(Review.reviewed_at.desc())
            .all()
        )

        reviews_payload = [
            {
                "id": str(review.id),
                "patient_id": str(review.patient_id),
                "doctor_id": str(review.doctor_id),
                "status": review.status,
                "notes": review.notes,
                "reviewed_at": _isoformat(review.reviewed_at),
            }
            for review in review_rows
        ]

        return {
            "patients": patient_results.model_dump(),
            "visits": visit_results.model_dump(),
            "risk_flags": risk_results.model_dump(),
            "server_updates": {"reviews": reviews_payload},
            "reviews": reviews_payload,
            "sync_timestamp": _isoformat(now),
        }
    finally:
        db.close()
