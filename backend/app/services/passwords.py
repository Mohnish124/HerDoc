"""Password hashing, validation and verification for HerDoc.

Uses bcrypt with a minimum cost factor of 12.
"""
from __future__ import annotations

import logging
from typing import Final

import bcrypt

LOGGER = logging.getLogger(__name__)

PASSWORD_MIN_LENGTH: Final[int] = 10
BCRYPT_COST_FACTOR: Final[int] = 12

COMMON_PASSWORDS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "Password1",
        "Password123",
        "Password12",
        "Password!",
        "Password@123",
        "Password1234",
        "Password01",
        "Password2024",
        "Password2025",
        "Password321",
        "Passw0rd",
        "P@ssw0rd",
        "Admin123",
        "Admin@123",
        "Admin2024",
        "Welcome1",
        "Welcome123",
        "Welcome2024",
        "Welcome2025",
        "Welcome@123",
        "Welcome!123",
        "Qwerty123",
        "Qwerty@123",
        "Letmein123",
        "Letmein@123",
        "Secret123",
        "Changeme123",
        "Abcd1234",
        "Test1234",
        "Hello1234",
        "Dragon123",
        "Football123",
        "Baseball123",
        "Monkey123",
        "Shadow123",
        "Master123",
        "Login123",
        "Access123",
        "Trustno1",
        "Herdoc123",
        "User1234",
        "Work1234",
        "Pass1234",
        "Secure123",
        "Spring2024",
        "Summer2024",
        "MyPassword1",
        "MyPass123",
        "NewPassword1",
    }
)


class PasswordPolicyError(ValueError):
    """Raised when a candidate password fails the policy check."""


def validate_password_policy(password: str) -> None:
    """Validate a password against the policy.

    Raises :class:`PasswordPolicyError` with a safe (non-sensitive) message on failure.
    """
    if not isinstance(password, str):
        raise PasswordPolicyError("Password must be a string.")

    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
        )

    if password in COMMON_PASSWORDS:
        raise PasswordPolicyError("Password is too common; please choose another.")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with a minimum cost of 12.

    The plaintext password is never logged.
    """
    validate_password_policy(password)
    salt = bcrypt.gensalt(rounds=BCRYPT_COST_FACTOR)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored bcrypt hash.

    Returns ``True`` on match, ``False`` otherwise.
    Raises :class:`ValueError` if ``password_hash`` is empty.
    The plaintext password is never logged.
    """
    if not password_hash:
        raise ValueError("Cannot verify against an empty password hash.")
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError as exc:
        if "Invalid salt" in str(exc):
            return False
        raise
