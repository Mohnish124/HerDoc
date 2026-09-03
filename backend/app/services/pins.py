"""PIN hashing, validation and verification for HerDoc.

PINs are 4-6 digit credentials typically used by mobile field workers
(ASHA/ANM). They are hashed with bcrypt for storage.

Security notes:
- Plaintext PIN values MUST NEVER be logged or serialised.
- Hash verification only returns a boolean; no error message leaks length/format.
"""
from __future__ import annotations

import logging
from typing import Final

import bcrypt

LOGGER = logging.getLogger(__name__)

PIN_MIN_LENGTH: Final[int] = 4
PIN_MAX_LENGTH: Final[int] = 6

PIN_BCRYPT_COST: Final[int] = 12


class PinPolicyError(ValueError):
    """Raised when a candidate PIN fails the policy check.

    The message intentionally never contains the PIN.
    """


def _is_sequential(digits: list[int]) -> bool:
    if len(digits) < 2:
        return False
    step = digits[1] - digits[0]
    if step not in (1, -1):
        return False
    return all(digits[i + 1] - digits[i] == step for i in range(len(digits) - 1))


def _all_same_digit(digits: list[int]) -> bool:
    return len(set(digits)) == 1


def _has_consecutive_repeats(digits: list[int]) -> bool:
    return any(digits[i] == digits[i + 1] for i in range(len(digits) - 1))


def validate_pin_policy(pin: str) -> None:
    """Validate a PIN against the format + anti-guessing policy.

    Raises :class:`PinPolicyError` with a safe message (never the PIN).
    """
    if not isinstance(pin, str):
        raise PinPolicyError("PIN must be a string of digits.")

    length = len(pin)
    if length < PIN_MIN_LENGTH or length > PIN_MAX_LENGTH:
        raise PinPolicyError(
            f"PIN must be between {PIN_MIN_LENGTH} and {PIN_MAX_LENGTH} digits long."
        )

    if not pin.isdigit():
        raise PinPolicyError("PIN must contain only digits (0-9).")

    digits = [int(ch) for ch in pin]

    if _all_same_digit(digits):
        raise PinPolicyError("PIN cannot use a single repeated digit.")

    if _is_sequential(digits):
        raise PinPolicyError("PIN cannot be an ascending or descending sequence.")

    if _has_consecutive_repeats(digits):
        raise PinPolicyError("PIN cannot use consecutive repeated digits.")


def hash_pin(pin: str) -> str:
    """Hash a PIN using bcrypt.

    The PIN value is never logged.
    """
    validate_pin_policy(pin)
    salt = bcrypt.gensalt(rounds=PIN_BCRYPT_COST)
    hashed = bcrypt.hashpw(pin.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Verify a PIN against a stored bcrypt hash.

    Returns ``True`` on match, ``False`` otherwise.
    Raises :class:`ValueError` if ``pin_hash`` is empty.
    Never logs or returns PIN content.
    """
    if not pin_hash:
        raise ValueError("Cannot verify against an empty PIN hash.")

    if not isinstance(pin, str) or not pin.isdigit():
        return False

    try:
        return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
    except ValueError:
        return False
