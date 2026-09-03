"""Authentication primitives (backwards-compatible module).

All actual logic lives in the sub-modules:

* ``app.services.passwords``  — bcrypt password hashing
* ``app.services.pins``       — bcrypt PIN hashing (4-6 digits)
* ``app.services.tokens``     — JWT access + refresh create/verify
* ``app.services.refresh_tokens`` — SHA-256 hash-only storage helpers
"""
from app.services.passwords import (
    BCRYPT_COST_FACTOR,
    COMMON_PASSWORDS,
    PASSWORD_MIN_LENGTH,
    PasswordPolicyError,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.services.pins import (
    PIN_BCRYPT_COST,
    PIN_MAX_LENGTH,
    PIN_MIN_LENGTH,
    PinPolicyError,
    hash_pin,
    validate_pin_policy,
    verify_pin,
)
from app.services.refresh_tokens import (
    HASH_ALGORITHM,
    hash_refresh_token,
    token_stored_hash_is_plaintext_refused,
    verify_refresh_token_hash,
)
from app.services.tokens import (
    ACCESS_TOKEN_TTL,
    JWT_ALGORITHM,
    REFRESH_TOKEN_TTL,
    REQUIRED_CLAIMS,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    JWTError,
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)

__all__ = [
    "BCRYPT_COST_FACTOR",
    "COMMON_PASSWORDS",
    "PASSWORD_MIN_LENGTH",
    "PasswordPolicyError",
    "hash_password",
    "validate_password_policy",
    "verify_password",
    "PIN_BCRYPT_COST",
    "PIN_MAX_LENGTH",
    "PIN_MIN_LENGTH",
    "PinPolicyError",
    "hash_pin",
    "validate_pin_policy",
    "verify_pin",
    "HASH_ALGORITHM",
    "hash_refresh_token",
    "token_stored_hash_is_plaintext_refused",
    "verify_refresh_token_hash",
    "ACCESS_TOKEN_TTL",
    "JWT_ALGORITHM",
    "REFRESH_TOKEN_TTL",
    "REQUIRED_CLAIMS",
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "JWTError",
    "TokenExpiredError",
    "TokenInvalidError",
    "create_access_token",
    "create_refresh_token",
    "verify_access_token",
    "verify_refresh_token",
]
