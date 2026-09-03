import logging
import time
from datetime import timedelta

import pytest

from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_pin,
    hash_refresh_token,
    verify_access_token,
    verify_password,
    verify_pin,
    verify_refresh_token,
    verify_refresh_token_hash,
)


def test_password_hash_uses_bcrypt_and_verifies_successfully():
    raw_password = "StrongPass!2024"
    hashed = hash_password(raw_password)

    assert hashed.startswith("$2b$")
    cost = int(hashed.split("$")[2])
    assert cost >= 12
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPass!2024", hashed) is False


def test_password_rejects_too_short_and_common_values():
    with pytest.raises(ValueError, match="10"):
        hash_password("short!")

    with pytest.raises(ValueError, match="common"):
        hash_password("Password123")

    with pytest.raises(ValueError, match="common"):
        hash_password("Welcome2024")


def test_pin_hashing_requires_non_repeating_non_sequential_values_and_no_plaintext_logging(caplog):
    valid_pin = "2468"
    hashed = hash_pin(valid_pin)

    assert hashed != valid_pin
    assert verify_pin(valid_pin, hashed) is True
    assert verify_pin("1357", hashed) is False

    with pytest.raises(ValueError, match="4"):
        hash_pin("12")

    with pytest.raises(ValueError, match="sequence"):
        hash_pin("1234")

    with pytest.raises(ValueError, match="repeated"):
        hash_pin("1111")

    with caplog.at_level(logging.INFO, logger="app.services.pins"):
        hash_pin("9426")

    assert "9426" not in caplog.text


def test_access_token_expires_after_15_minutes_and_verifies_subject():
    token = create_access_token(subject="user-123")
    payload = verify_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]
    assert payload["exp"] - payload["iat"] == timedelta(minutes=15).total_seconds()

    near_expired = create_access_token(subject="user-123", expires_delta=timedelta(milliseconds=50))
    time.sleep(0.2)
    with pytest.raises(ValueError, match="expired"):
        verify_access_token(near_expired)


def test_refresh_token_storage_hashes_only_and_verifies_hash():
    raw_refresh = "refresh-token-abc-123"
    hashed = hash_refresh_token(raw_refresh)

    assert hashed != raw_refresh
    assert verify_refresh_token_hash(raw_refresh, hashed) is True
    assert verify_refresh_token_hash("different-token", hashed) is False


def test_refresh_token_jwt_has_30_day_ttl_and_verifies():
    jwt_refresh = create_refresh_token(subject="user-123")
    claims = verify_refresh_token(jwt_refresh)

    assert claims["sub"] == "user-123"
    assert claims["type"] == "refresh"
    assert "jti" in claims
    ttl = claims["exp"] - claims["iat"]
    assert ttl == timedelta(days=30).total_seconds()
