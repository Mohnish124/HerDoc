import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Facility, FacilityType, User, UserRole
from app.services.auth_service import hash_password, hash_pin


DEMO_NAMESPACE = uuid.UUID("b1a7f1d0-4a6b-4e6e-9f9c-8f2f1e2b3a4d")

DEMO_FACILITY_NAME = "Demo PHC"
DEMO_FACILITY_REGION = "North"
DEMO_FACILITY_TYPE = FacilityType.PHC.value

DEMO_USERS = [
    {
        "email": "admin@herdoc.local",
        "phone": "9000000001",
        "role": UserRole.ADMIN,
        "name": "Demo Admin",
        "password": "AdminPass!2024",
        "pin": "2468",
    },
    {
        "email": "doctor@herdoc.local",
        "phone": "9000000002",
        "role": UserRole.DOCTOR,
        "name": "Demo Doctor",
        "password": "DoctorPass!2024",
        "pin": "1357",
    },
    {
        "email": "worker@herdoc.local",
        "phone": "9000000003",
        "role": UserRole.WORKER,
        "name": "Demo Worker",
        "password": "WorkerPass!2024",
        "pin": "2468",
    },
]

PLACEHOLDER_PASSWORD_HASH = hash_password("AdminPass!2024")


def _deterministic_uuid(label: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, label)


def facility_deterministic_id() -> uuid.UUID:
    return _deterministic_uuid(f"facility:{DEMO_FACILITY_NAME}:{DEMO_FACILITY_REGION}")


def user_deterministic_id(email: str) -> uuid.UUID:
    return _deterministic_uuid(f"user:{email.lower()}")


def _find_existing_user(session: Session, *, email: str, phone: str) -> Optional[User]:
    if email:
        user = session.query(User).filter(User.email == email).first()
        if user is not None:
            return user
    if phone:
        user = session.query(User).filter(User.phone == phone).first()
        if user is not None:
            return user
    return None


def _upsert_facility(session: Session) -> tuple[Facility, bool]:
    facility_id = facility_deterministic_id()
    facility = session.get(Facility, facility_id)
    created = False
    if facility is None:
        facility = (
            session.query(Facility)
            .filter(Facility.name == DEMO_FACILITY_NAME, Facility.region == DEMO_FACILITY_REGION)
            .first()
        )
    if facility is None:
        facility = Facility(
            id=facility_id,
            name=DEMO_FACILITY_NAME,
            region=DEMO_FACILITY_REGION,
            type=DEMO_FACILITY_TYPE,
        )
        session.add(facility)
        session.flush()
        created = True
    else:
        changed = False
        if facility.name != DEMO_FACILITY_NAME:
            facility.name = DEMO_FACILITY_NAME
            changed = True
        if facility.region != DEMO_FACILITY_REGION:
            facility.region = DEMO_FACILITY_REGION
            changed = True
        if facility.type != DEMO_FACILITY_TYPE:
            facility.type = DEMO_FACILITY_TYPE
            changed = True
        if changed:
            session.flush()
    return facility, created


def _upsert_user(session: Session, *, config: dict, facility: Facility) -> tuple[User, bool, bool]:
    email = config["email"]
    phone = config["phone"]
    expected_id = user_deterministic_id(email)

    user = session.get(User, expected_id)
    if user is None:
        user = _find_existing_user(session, email=email, phone=phone)

    created = False
    updated = False

    password_hash = hash_password(config["password"]) if config.get("password") else PLACEHOLDER_PASSWORD_HASH
    pin_hash = hash_pin(config["pin"]) if config.get("pin") else None

    if user is None:
        user = User(
            id=expected_id,
            role=config["role"].value,
            name=config["name"],
            phone=phone,
            email=email,
            facility_id=facility.id,
            password_hash=password_hash if config["role"] in (UserRole.ADMIN, UserRole.DOCTOR) else None,
            pin_hash=pin_hash if config["role"] == UserRole.WORKER else None,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
        session.add(user)
        session.flush()
        created = True
    else:
        target_role = config["role"].value
        if user.role != target_role:
            user.role = target_role
            updated = True
        if user.name != config["name"]:
            user.name = config["name"]
            updated = True
        if user.phone != phone:
            user.phone = phone
            updated = True
        if user.email != email:
            user.email = email
            updated = True
        if user.facility_id != facility.id:
            user.facility_id = facility.id
            updated = True
        if user.role in (UserRole.ADMIN.value, UserRole.DOCTOR.value):
            if user.password_hash != password_hash:
                user.password_hash = password_hash
                updated = True
        else:
            if user.pin_hash != pin_hash:
                user.pin_hash = pin_hash
                updated = True
        if user.is_active is not True:
            user.is_active = True
            updated = True
        if updated:
            session.flush()

    return user, created, updated


def seed_demo_data(session: Session, *, commit: bool = False) -> dict:
    facility, facility_created = _upsert_facility(session)
    results = {
        "facility_id": facility.id,
        "facility_created": facility_created,
        "users": {},
        "created_count": 1 if facility_created else 0,
        "updated_count": 0,
    }

    for config in DEMO_USERS:
        user, created, updated = _upsert_user(session, config=config, facility=facility)
        role_key = config["role"].value
        results["users"][config["email"]] = {
            "id": user.id,
            "created": created,
            "updated": updated,
            "role": role_key,
        }
        results[f"{role_key}_id"] = user.id
        if created:
            results["created_count"] += 1
        if updated:
            results["updated_count"] += 1

    results["seeded_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if commit:
        session.commit()

    return results


def print_seed_report(results: dict) -> None:
    print("=== HERDOC DEMO SEED REPORT ===")
    print(f"Facility ID:        {results['facility_id']}  (created={results['facility_created']})")
    print(f"Admin ID:           {results.get('admin_id')}")
    print(f"Doctor ID:          {results.get('doctor_id')}")
    print(f"Worker ID:          {results.get('worker_id')}")
    print(f"Records created:    {results['created_count']}")
    print(f"Records updated:    {results['updated_count']}")
    print(f"Timestamp:          {results['seeded_at']}")
    for email, info in results["users"].items():
        print(f"  - {email} -> role={info['role']} id={info['id']} created={info['created']} updated={info['updated']}")
    print("=== END REPORT ===")


if __name__ == "__main__":
    from app.db.session import get_session_local

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        report = seed_demo_data(db, commit=True)
        print_seed_report(report)
    finally:
        db.close()
