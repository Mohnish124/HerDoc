from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth import require_role
from app.db.models import Facility, Patient, Review, RiskFlag, User, Visit
from app.db.session import get_session_local

router = APIRouter(prefix="/api", tags=["dashboard"])


def _get_db() -> Session:
    return get_session_local()()


@router.get("/dashboard/flagged")
def get_flagged_patients(
    facility_id: uuid.UUID | None = Query(default=None),
    worker_id: uuid.UUID | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    current_user: User = Depends(require_role("doctor", "admin")),
):
    db = _get_db()
    try:
        # Enforce facility scope
        effective_facility_id = facility_id
        if current_user.role == "doctor":
            if current_user.facility_id is not None:
                if facility_id is not None and facility_id != current_user.facility_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Doctors can only access patients within their own assigned facility",
                    )
                effective_facility_id = current_user.facility_id

        # Query all patients within facility / worker scope
        query = db.query(Patient).join(User, Patient.worker_id == User.id)
        if effective_facility_id is not None:
            query = query.filter(User.facility_id == effective_facility_id)
        if worker_id is not None:
            query = query.filter(Patient.worker_id == worker_id)

        patients = query.all()
        flagged_list = []

        for patient in patients:
            # Get latest visit
            latest_visit = (
                db.query(Visit)
                .filter(Visit.patient_id == patient.id)
                .order_by(Visit.created_locally_at.desc())
                .first()
            )
            if not latest_visit:
                continue

            # Get latest risk flag for the visit
            latest_flag = (
                db.query(RiskFlag)
                .filter(RiskFlag.visit_id == latest_visit.id)
                .order_by(RiskFlag.created_at.desc())
                .first()
            )

            eff_risk = (
                latest_flag.trend_adjusted_level
                if latest_flag and latest_flag.trend_adjusted_level
                else (latest_flag.model_risk_level if latest_flag else "green")
            ).lower()

            # Filter by risk level if requested
            if risk_level:
                if eff_risk != risk_level.strip().lower():
                    continue

            # Get latest review
            latest_review = (
                db.query(Review)
                .filter(Review.patient_id == patient.id)
                .order_by(Review.reviewed_at.desc())
                .first()
            )

            # Get worker & facility info
            worker = patient.worker
            facility = None
            if worker and worker.facility_id:
                facility = db.get(Facility, worker.facility_id)

            flagged_list.append({
                "id": str(patient.id),
                "name": patient.name,
                "age": patient.age,
                "village": patient.village,
                "edd": patient.edd.isoformat() if patient.edd else None,
                "phone": patient.phone,
                "created_at": patient.created_at.isoformat() if patient.created_at else None,
                "worker": {
                    "id": str(worker.id) if worker else None,
                    "name": worker.name if worker else "Unassigned",
                    "phone": worker.phone if worker else None,
                },
                "facility": {
                    "id": str(facility.id) if facility else None,
                    "name": facility.name if facility else "Unassigned PHC",
                },
                "last_visit": {
                    "id": str(latest_visit.id),
                    "visit_date": latest_visit.visit_date.isoformat(),
                    "systolic_bp": latest_visit.systolic_bp,
                    "diastolic_bp": latest_visit.diastolic_bp,
                    "blood_sugar": latest_visit.blood_sugar,
                    "body_temp_c": latest_visit.body_temp_c,
                    "heart_rate": latest_visit.heart_rate,
                    "created_locally_at": (
                        latest_visit.created_locally_at.isoformat()
                        if latest_visit.created_locally_at
                        else None
                    ),
                },
                "trend_adjusted_level": eff_risk,
                "trend_reason": latest_flag.trend_reason if latest_flag else None,
                "latest_risk": {
                    "model_risk_level": latest_flag.model_risk_level if latest_flag else "green",
                    "trend_adjusted_level": eff_risk,
                    "trend_reason": latest_flag.trend_reason if latest_flag else None,
                },
                "review_status": latest_review.status if latest_review else "pending",
                "review": {
                    "id": str(latest_review.id) if latest_review else None,
                    "status": latest_review.status if latest_review else "pending",
                    "notes": latest_review.notes if latest_review else None,
                    "reviewed_at": (
                        latest_review.reviewed_at.isoformat()
                        if latest_review and latest_review.reviewed_at
                        else None
                    ),
                },
            })

        # Sorting: RED first (0), YELLOW second (1), GREEN third (2), then newest visit date descending
        priority_map = {"red": 0, "yellow": 1, "green": 2}

        def sort_key(item):
            risk = item["trend_adjusted_level"].lower()
            prio = priority_map.get(risk, 3)
            visit_time = item["last_visit"]["created_locally_at"] or ""
            return (prio, -1 * (datetime.fromisoformat(visit_time).timestamp() if visit_time else 0))

        flagged_list.sort(key=sort_key)
        return flagged_list
    finally:
        db.close()


@router.get("/dashboard/facility-overview")
def get_facility_overview(
    facility_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role("doctor", "admin")),
):
    db = _get_db()
    try:
        # Enforce facility scope
        target_facility_id = facility_id
        if current_user.role == "doctor":
            if current_user.facility_id is not None:
                if facility_id is not None and facility_id != current_user.facility_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Doctors can only access their own facility overview",
                    )
                target_facility_id = current_user.facility_id

        # Query facility info if specified
        facility_name = "All Facilities"
        if target_facility_id is not None:
            fac = db.get(Facility, target_facility_id)
            if fac:
                facility_name = fac.name

        # Query patients in scope
        patients_query = db.query(Patient).join(User, Patient.worker_id == User.id)
        if target_facility_id is not None:
            patients_query = patients_query.filter(User.facility_id == target_facility_id)

        patients = patients_query.all()
        total_patients = len(patients)

        # Count active flags from latest visit of each patient
        active_flags = {"green": 0, "yellow": 0, "red": 0}
        for p in patients:
            latest_visit = (
                db.query(Visit)
                .filter(Visit.patient_id == p.id)
                .order_by(Visit.created_locally_at.desc())
                .first()
            )
            if not latest_visit:
                continue

            latest_flag = (
                db.query(RiskFlag)
                .filter(RiskFlag.visit_id == latest_visit.id)
                .order_by(RiskFlag.created_at.desc())
                .first()
            )

            risk = (
                latest_flag.trend_adjusted_level
                if latest_flag and latest_flag.trend_adjusted_level
                else (latest_flag.model_risk_level if latest_flag else "green")
            ).lower()

            if risk in active_flags:
                active_flags[risk] += 1
            else:
                active_flags["green"] += 1

        # Count active workers in last 7 days
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        visits_query = db.query(Visit.worker_id).join(User, Visit.worker_id == User.id)
        if target_facility_id is not None:
            visits_query = visits_query.filter(User.facility_id == target_facility_id)

        # Visits created within last 7 days
        recent_visits = visits_query.filter(
            (Visit.created_locally_at >= seven_days_ago) | (Visit.visit_date >= seven_days_ago.date())
        ).distinct().all()

        active_workers_count = len(recent_visits)

        return {
            "facility_id": str(target_facility_id) if target_facility_id else None,
            "facility_name": facility_name,
            "total_patients": total_patients,
            "active_flags": active_flags,
            "active_workers_last_7_days": active_workers_count,
        }
    finally:
        db.close()


@router.get("/dashboard/filters")
def get_dashboard_filters(current_user: User = Depends(require_role("doctor", "admin"))):
    db = _get_db()
    try:
        facilities_query = db.query(Facility)
        workers_query = db.query(User).filter(User.role == "worker")

        if current_user.role == "doctor" and current_user.facility_id is not None:
            facilities_query = facilities_query.filter(Facility.id == current_user.facility_id)
            workers_query = workers_query.filter(User.facility_id == current_user.facility_id)

        facilities = facilities_query.all()
        workers = workers_query.all()

        return {
            "facilities": [{"id": str(f.id), "name": f.name} for f in facilities],
            "workers": [{"id": str(w.id), "name": w.name, "facility_id": str(w.facility_id) if w.facility_id else None} for w in workers],
        }
    finally:
        db.close()
