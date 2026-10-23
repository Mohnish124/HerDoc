"""Seed the synthetic HerDoc demo dataset into a LOCAL or isolated demo database.

Creates 5 demo workers (phones 9000000006-9000000010, one shared demo PIN), 3 fictional patients per
worker and 4 visits per patient with risk results produced by the real risk model
(see app/demo/demo_dataset.json and web/scripts/build-demo-dataset.mjs).

Safety:
- Requires --demo. Refuses production settings, Render environments and known production database hosts.
- Writes only to SQLite or a localhost database unless --allow-remote-host names the exact demo host.
- Prints only a safe target summary (no credentials). Requires migrations at head.
- Never drops, truncates, deletes or overwrites. Stable record ids make reruns create nothing new.
- Any requested phone or record id already used by a non-demo record stops the run before writing.
- The demo PIN is read from HERDOC_DEMO_WORKER_PIN or a hidden prompt; it is hashed, never stored or printed.

Usage (from backend/):
    python -m app.demo.seed_demo_dataset --demo [--facility-name "Demo PHC"] [--allow-remote-host HOST]
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.api.patients import PatientCreateRequest
from app.api.visits import VisitCreateRequest
from app.config import get_settings
from app.db.models import AuditLog, Facility, FacilityType, Patient, RiskFlag, User, UserRole, Visit
from app.demo.identity import demo_id
from app.services.auth_service import hash_pin

DATASET_PATH = Path(__file__).with_name("demo_dataset.json")
PIN_ENV_VAR = "HERDOC_DEMO_WORKER_PIN"
DEFAULT_FACILITY_NAME = "Demo PHC"
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PRODUCTION_HOST_MARKERS = ("aivencloud.com", "onrender.com", "render.com")


class DemoSeedError(RuntimeError):
    pass


def load_dataset(path: Path = DATASET_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assess_target(url, *, is_production: bool, environ, allow_remote_host: str | None = None) -> str:
    """Return a credential-free summary of the target, or raise DemoSeedError if it is not a safe demo target."""
    if is_production or environ.get("RENDER"):
        raise DemoSeedError("Refusing to seed: production settings or a Render environment detected.")
    backend = url.get_backend_name()
    if backend == "sqlite":
        return f"isolated SQLite database file '{Path(url.database or '').name or ':memory:'}'"
    host = (url.host or "").lower()
    if any(marker in host for marker in PRODUCTION_HOST_MARKERS):
        raise DemoSeedError("Refusing to seed: the database host belongs to a known production provider.")
    if host in LOCAL_HOSTS:
        return f"local {backend} database '{url.database}' on {host}"
    if allow_remote_host and host == allow_remote_host.strip().lower():
        return f"explicitly allowed demo {backend} database '{url.database}' on {host}"
    raise DemoSeedError(
        "Refusing to seed: the database is not local. Use a local/isolated demo database, or pass "
        "--allow-remote-host with the exact host of a dedicated demo database."
    )


def check_migrations(engine) -> None:
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    if current != expected:
        raise DemoSeedError("Database migrations are not at head; run 'alembic upgrade head' on the demo database first.")


@dataclass
class SeedReport:
    facility_created: bool = False
    created: dict = field(default_factory=lambda: {"workers": 0, "patients": 0, "visits": 0, "risk_flags": 0})
    existing: dict = field(default_factory=lambda: {"workers": 0, "patients": 0, "visits": 0, "risk_flags": 0})


def _conflicts(db: Session, dataset: dict) -> list[str]:
    """Records the run would collide with that are not this dataset's own demo records."""
    problems = []
    for worker in dataset["workers"]:
        wid = demo_id(worker["key"])
        by_phone = db.query(User).filter(User.phone == worker["phone"]).first()
        if by_phone is not None and by_phone.id != wid:
            problems.append(f"phone {worker['phone']} already belongs to a non-demo account")
        by_id = db.get(User, wid)
        if by_id is not None and (by_id.phone != worker["phone"] or by_id.role != UserRole.WORKER.value):
            problems.append(f"record id for {worker['name']} is used by a different account")
    for patient in dataset["patients"]:
        existing = db.get(Patient, demo_id(patient["key"]))
        if existing is not None and existing.worker_id != demo_id(patient["worker_key"]):
            problems.append(f"record id for {patient['name']} belongs to another worker's patient")
        for i, _ in enumerate(patient["visits"]):
            visit = db.get(Visit, demo_id(f"{patient['key']}-visit-{i + 1}"))
            if visit is not None and visit.patient_id != demo_id(patient["key"]):
                problems.append(f"visit id for {patient['name']} visit {i + 1} belongs to another patient")
    return problems


def seed_demo_dataset(db: Session, *, pin: str, facility_name: str = DEFAULT_FACILITY_NAME, today=None, dataset=None,
                      allow_remote_host: str | None = None) -> SeedReport:
    """Create missing demo records in one transaction. Existing demo records are left untouched.

    The target is checked here too (not only in the CLI), so no caller can seed a production database.
    """
    assess_target(db.get_bind().url, is_production=get_settings().is_production, environ=os.environ, allow_remote_host=allow_remote_host)
    dataset = dataset or load_dataset()
    today = today or datetime.now(timezone.utc).date()
    report = SeedReport()

    problems = _conflicts(db, dataset)
    if problems:
        raise DemoSeedError("Nothing was written. Conflicts: " + "; ".join(problems))
    try:
        pin_hash = hash_pin(pin)  # validates the PIN against the existing PIN policy
    except ValueError as exc:
        raise DemoSeedError(f"Demo PIN rejected by the PIN policy: {exc}") from exc

    try:
        facility = db.query(Facility).filter(Facility.name == facility_name).first()
        if facility is None:
            facility = Facility(id=uuid.uuid4(), name=facility_name, region="Demo (synthetic)", type=FacilityType.PHC.value)
            db.add(facility)
            db.flush()
            report.facility_created = True

        for worker in dataset["workers"]:
            wid = demo_id(worker["key"])
            if db.get(User, wid) is not None:
                report.existing["workers"] += 1
                continue
            db.add(User(
                id=wid, role=UserRole.WORKER.value, name=worker["name"], phone=worker["phone"],
                email=None, password_hash=None, pin_hash=pin_hash, facility_id=facility.id,
                is_active=True, failed_login_attempts=0, locked_until=None,
            ))
            report.created["workers"] += 1
        db.flush()

        for patient in dataset["patients"]:
            pid, wid = demo_id(patient["key"]), demo_id(patient["worker_key"])
            # Same validation as POST /api/patients.
            checked = PatientCreateRequest(
                id=pid, name=patient["name"], age=patient["age"], village=patient["village"],
                edd=today + timedelta(days=patient["edd_days_ahead"]), phone=None,
            )
            if db.get(Patient, pid) is None:
                db.add(Patient(id=pid, worker_id=wid, name=checked.name, age=checked.age, village=checked.village, edd=checked.edd, phone=None))
                report.created["patients"] += 1
            else:
                report.existing["patients"] += 1
            db.flush()

            for i, v in enumerate(patient["visits"]):
                vid, fid = demo_id(f"{patient['key']}-visit-{i + 1}"), demo_id(f"{patient['key']}-visit-{i + 1}-flag")
                when = datetime.combine(today - timedelta(days=v["days_ago"]), time(10, 0), tzinfo=timezone.utc)
                # Same validation as POST /api/patients/{id}/visits (ranges, risk codes, timezone-aware dates).
                checked_visit = VisitCreateRequest(
                    id=vid, patient_id=pid, worker_id=wid, visit_date=when, created_locally_at=when,
                    systolic_bp=v["systolic_bp"], diastolic_bp=v["diastolic_bp"], blood_sugar=v["blood_sugar"],
                    body_temp_c=v["body_temp_c"], heart_rate=v["heart_rate"],
                    risk_flags=[{"id": fid, "model_risk_level": v["model_risk_level"], "trend_adjusted_level": v["trend_adjusted_level"], "trend_reason": v["trend_reason"]}],
                )
                if db.get(Visit, vid) is None:
                    db.add(Visit(
                        id=vid, patient_id=pid, worker_id=wid, visit_date=when.date(),
                        systolic_bp=checked_visit.systolic_bp, diastolic_bp=checked_visit.diastolic_bp,
                        blood_sugar=checked_visit.blood_sugar, body_temp_c=checked_visit.body_temp_c,
                        heart_rate=checked_visit.heart_rate, created_locally_at=when, synced_at=when,
                    ))
                    report.created["visits"] += 1
                    db.flush()
                else:
                    report.existing["visits"] += 1
                flag = checked_visit.risk_flags[0]
                if db.get(RiskFlag, fid) is None:
                    db.add(RiskFlag(id=fid, visit_id=vid, model_risk_level=flag.model_risk_level,
                                    trend_adjusted_level=flag.trend_adjusted_level, trend_reason=flag.trend_reason))
                    report.created["risk_flags"] += 1
                else:
                    report.existing["risk_flags"] += 1

        if any(report.created.values()):
            db.add(AuditLog(id=uuid.uuid4(), user_id=None, event_type="demo.seed",
                            event_metadata={"created": report.created, "facility": facility_name}))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return report


def _read_pin() -> str:
    pin = os.environ.get(PIN_ENV_VAR, "").strip()
    if pin:
        return pin
    first = getpass.getpass("Demo worker PIN (shared by all five demo workers): ").strip()
    if first != getpass.getpass("Repeat demo PIN: ").strip():
        raise DemoSeedError("PIN entries did not match.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the synthetic HerDoc demo dataset (local/isolated databases only).")
    parser.add_argument("--demo", action="store_true", help="Required: confirms this is a demo database.")
    parser.add_argument("--facility-name", default=DEFAULT_FACILITY_NAME, help="Facility for the demo workers (created if missing).")
    parser.add_argument("--allow-remote-host", help="Exact host of a dedicated, non-production demo database.")
    args = parser.parse_args(argv)
    if not args.demo:
        print("Refusing to seed without --demo. Nothing was written.", file=sys.stderr)
        return 2

    from app.config import get_settings
    from app.db.session import get_engine, get_session_local

    try:
        settings = get_settings()
        engine = get_engine()
        summary = assess_target(engine.url, is_production=settings.is_production, environ=os.environ, allow_remote_host=args.allow_remote_host)
        print(f"Target: {summary}")
        check_migrations(engine)
        pin = _read_pin()
        db = get_session_local()()
        try:
            report = seed_demo_dataset(db, pin=pin, facility_name=args.facility_name, allow_remote_host=args.allow_remote_host)
        finally:
            db.close()
    except DemoSeedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Facility '{args.facility_name}': {'created' if report.facility_created else 'already present'}")
    for kind in ("workers", "patients", "visits", "risk_flags"):
        print(f"{kind}: {report.created[kind]} created, {report.existing[kind]} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
