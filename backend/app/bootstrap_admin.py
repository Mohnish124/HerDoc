"""Create the first HerDoc administrator (and their facility) on an empty database.

Admin registration over HTTP requires an existing admin, so the very first admin
is created offline with this command. It refuses to run once any admin exists,
never takes the password on the command line, and shows which database it will
write to before doing anything.

Usage (from backend/, with DATABASE_URL etc. exported for the TARGET database):
    python -m app.bootstrap_admin --name "Dr. A" --email a@example.org \\
        --facility-name "PHC Rampur" --facility-region "North" --facility-type PHC

The password is read from HERDOC_BOOTSTRAP_ADMIN_PASSWORD if set, otherwise prompted.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditLog, Facility, FacilityType, User, UserRole
from app.services.auth_service import hash_password
from app.services.demo_accounts import is_demo_identity

PASSWORD_ENV_VAR = "HERDOC_BOOTSTRAP_ADMIN_PASSWORD"


class BootstrapError(RuntimeError):
    pass


def bootstrap_first_admin(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    facility_name: str,
    facility_region: str,
    facility_type: str = FacilityType.PHC.value,
) -> User:
    """Create the first admin and their facility in one transaction."""
    email = email.strip().lower()
    if not name.strip() or "@" not in email:
        raise BootstrapError("A name and a valid email are required.")
    if is_demo_identity(email=email):
        raise BootstrapError("Demo (herdoc.local) emails cannot be used for real administrators.")
    if facility_type not in {item.value for item in FacilityType}:
        raise BootstrapError(f"Facility type must be one of: {sorted(item.value for item in FacilityType)}")
    if not facility_name.strip() or not facility_region.strip():
        raise BootstrapError("Facility name and region are required.")
    if db.query(User).filter(User.role == UserRole.ADMIN.value).first() is not None:
        raise BootstrapError("An administrator already exists. Use the web portal to add more admins.")
    if db.query(User).filter(User.email == email).first() is not None:
        raise BootstrapError("That email is already registered.")

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise BootstrapError(str(exc)) from exc

    try:
        facility = Facility(
            id=uuid.uuid4(),
            name=facility_name.strip(),
            region=facility_region.strip(),
            type=facility_type,
        )
        db.add(facility)
        db.flush()
        admin = User(
            id=uuid.uuid4(),
            role=UserRole.ADMIN.value,
            name=name.strip(),
            email=email,
            password_hash=password_hash,
            pin_hash=None,
            facility_id=facility.id,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
        db.add(admin)
        db.flush()
        db.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=admin.id,
                event_type="admin.bootstrap",
                event_metadata={"facility_id": str(facility.id)},
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return admin


def _read_password() -> str:
    password = os.environ.get(PASSWORD_ENV_VAR)
    if password:
        return password
    first = getpass.getpass("New admin password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise BootstrapError("Passwords do not match.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the first HerDoc administrator.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--facility-name", required=True)
    parser.add_argument("--facility-region", required=True)
    parser.add_argument("--facility-type", default=FacilityType.PHC.value)
    parser.add_argument("--yes", action="store_true", help="Skip the database confirmation prompt.")
    args = parser.parse_args(argv)

    from app.db.session import get_engine, get_session_local

    target = get_engine().url.render_as_string(hide_password=True)
    print(f"Target database: {target}")
    if not args.yes:
        answer = input("Create the first admin in THIS database? Type 'yes' to continue: ")
        if answer.strip().lower() != "yes":
            print("Aborted.")
            return 1

    db = get_session_local()()
    try:
        admin = bootstrap_first_admin(
            db,
            name=args.name,
            email=args.email,
            password=_read_password(),
            facility_name=args.facility_name,
            facility_region=args.facility_region,
            facility_type=args.facility_type,
        )
    except BootstrapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()

    print(f"Created admin {admin.email} (id {admin.id}) in facility {admin.facility_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
