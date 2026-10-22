"""Identify demo/seed accounts so they can never be used in production.

The seed script (app/db/seed.py) and the docs publish fixed credentials for
accounts on the reserved ``herdoc.local`` domain and a few fixed phone numbers.
``.local`` is reserved for mDNS, so no real staff email can use it.
"""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import User

DEMO_EMAIL_DOMAIN = "herdoc.local"
DEMO_PHONES = frozenset({"9000000001", "9000000002", "9000000003"})


def is_demo_identity(*, email: str | None = None, phone: str | None = None) -> bool:
    if email and email.strip().lower().endswith("@" + DEMO_EMAIL_DOMAIN):
        return True
    return bool(phone and phone.strip() in DEMO_PHONES)


def count_active_demo_accounts(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.is_active.is_(True))
        .filter(or_(User.email.like(f"%@{DEMO_EMAIL_DOMAIN}"), User.phone.in_(DEMO_PHONES)))
        .count()
    )
