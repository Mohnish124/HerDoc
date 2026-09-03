"""Unit tests for all authentication primitives: passwords, pins, JWT, refresh tokens."""
from __future__ import annotations

import re
import time
import uuid
from datetime import timedelta

import bcrypt
import pytest

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


# ============================================================
# PASSWORD TESTS
# ============================================================


class TestPasswordConstants:
    def test_password_min_length_is_10(self):
        assert PASSWORD_MIN_LENGTH == 10

    def test_bcrypt_cost_factor_at_least_12(self):
        assert BCRYPT_COST_FACTOR >= 12

    def test_common_password_blocklist_size_approximately_50(self):
        assert 40 <= len(COMMON_PASSWORDS) <= 60


class TestPasswordPolicyValidation:
    def test_accepts_valid_10_char_password(self):
        validate_password_policy("StrongP@ss1")

    def test_rejects_password_too_short(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("Short1!")

    def test_rejects_password_exactly_9_chars(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("123456789")

    def test_rejects_empty_password(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("")

    def test_rejects_non_string_password(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy(12345)  # type: ignore[arg-type]

    def test_rejects_common_password_blocklist_members(self):
        common_samples = ["Password123", "Admin123", "Welcome123", "Qwerty123", "Changeme123"]
        for pw in common_samples:
            with pytest.raises(PasswordPolicyError):
                validate_password_policy(pw)

    def test_common_password_set_membership_trimming(self):
        common_sample = list(COMMON_PASSWORDS)[0]
        with pytest.raises(PasswordPolicyError):
            validate_password_policy(common_sample)

    def test_policy_error_does_not_contain_password(self):
        try:
            validate_password_policy("MySecretP@ss1")
        except PasswordPolicyError:
            pass
        bad = "VeryUniqueBadPassword1234"
        try:
            validate_password_policy(bad[:9])
        except PasswordPolicyError as exc:
            assert bad not in str(exc)


class TestPasswordHashing:
    def test_hash_password_returns_bcrypt_string_format(self):
        pw_hash = hash_password("ValidP@ss10")
        assert isinstance(pw_hash, str)
        assert pw_hash.startswith("$2b$") or pw_hash.startswith("$2a$")
        assert len(pw_hash) == 60

    def test_hash_password_bcrypt_cost_reflects_factor(self):
        pw_hash = hash_password("AnotherV@lidP@ss1")
        prefix = pw_hash.split("$")
        assert len(prefix) >= 3
        cost = int(prefix[2])
        assert cost == BCRYPT_COST_FACTOR

    def test_hash_password_two_calls_produce_different_salts(self):
        pw = "RepeatableP@ss1"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2

    def test_hash_password_rejects_common_before_hashing(self):
        with pytest.raises(PasswordPolicyError):
            hash_password("Password123")


class TestPasswordVerification:
    def test_verify_password_accepts_correct(self):
        pw = "StrongH@shMe123"
        pw_hash = hash_password(pw)
        assert verify_password(pw, pw_hash) is True

    def test_verify_password_rejects_wrong(self):
        pw_hash = hash_password("RightP@ssw0rd1")
        assert verify_password("WrongPassword1!", pw_hash) is False

    def test_verify_password_different_passwords_same_hash_format(self):
        h1 = hash_password("FirstV@lidPass1")
        h2 = hash_password("SecondV@lidPass1")
        assert h1 != h2
        assert verify_password("FirstV@lidPass1", h1)
        assert not verify_password("FirstV@lidPass1", h2)

    def test_verify_password_rejects_empty_hash(self):
        with pytest.raises(ValueError, match="empty"):
            verify_password("Anything123", "")

    def test_verify_password_with_bcrypt_invalid_salt_returns_false(self):
        assert verify_password("anything", "$2b$12$invalid_salt_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") is False


# ============================================================
# PIN TESTS
# ============================================================


class TestPinConstants:
    def test_pin_min_length_is_4(self):
        assert PIN_MIN_LENGTH == 4

    def test_pin_max_length_is_6(self):
        assert PIN_MAX_LENGTH == 6

    def test_pin_bcrypt_cost_at_least_12(self):
        assert PIN_BCRYPT_COST >= 12


class TestPinPolicyValidation:
    def test_accepts_valid_4_digit_pin(self):
        validate_pin_policy("4829")

    def test_accepts_valid_5_digit_pin(self):
        validate_pin_policy("83492")

    def test_accepts_valid_6_digit_pin(self):
        validate_pin_policy("720495")

    def test_rejects_3_digits(self):
        with pytest.raises(PinPolicyError):
            validate_pin_policy("123")

    def test_rejects_7_digits(self):
        with pytest.raises(PinPolicyError):
            validate_pin_policy("1234567")

    def test_rejects_empty_string(self):
        with pytest.raises(PinPolicyError):
            validate_pin_policy("")

    def test_rejects_non_digits(self):
        with pytest.raises(PinPolicyError):
            validate_pin_policy("12a4")

    def test_rejects_all_same_digit_pins(self):
        for p in ["1111", "222222", "99999"]:
            with pytest.raises(PinPolicyError, match="repeated"):
                validate_pin_policy(p)

    def test_rejects_sequential_ascending(self):
        for p in ["1234", "0123", "34567", "456789"]:
            with pytest.raises(PinPolicyError, match="sequence"):
                validate_pin_policy(p)

    def test_rejects_sequential_descending(self):
        for p in ["4321", "98765", "876543"]:
            with pytest.raises(PinPolicyError, match="sequence"):
                validate_pin_policy(p)

    def test_rejects_consecutive_repeats(self):
        for p in ["1123", "1224", "1233", "111123", "123345", "122345"]:
            with pytest.raises(PinPolicyError, match="consecutive repeated"):
                validate_pin_policy(p)

    def test_pin_error_message_never_contains_pin(self):
        bad_pin = "135790"
        try:
            validate_pin_policy(bad_pin)
        except PinPolicyError as exc:
            assert bad_pin not in str(exc)

    def test_rejects_non_string(self):
        with pytest.raises(PinPolicyError):
            validate_pin_policy(1234)  # type: ignore[arg-type]


class TestPinHashingAndVerification:
    def test_hash_pin_is_bcrypt_format(self):
        hashed = hash_pin("638472")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_pin_uses_declared_cost(self):
        hashed = hash_pin("739502")
        parts = hashed.split("$")
        assert int(parts[2]) == PIN_BCRYPT_COST

    def test_verify_pin_correct_match(self):
        pin = "847293"
        hashed = hash_pin(pin)
        assert verify_pin(pin, hashed) is True

    def test_verify_pin_wrong_pin(self):
        hashed = hash_pin("572839")
        assert verify_pin("999999", hashed) is False

    def test_verify_pin_rejects_empty_hash(self):
        with pytest.raises(ValueError, match="empty"):
            verify_pin("1234", "")

    def test_verify_pin_non_digits_returns_false(self):
        hashed = hash_pin("648291")
        assert verify_pin("abcd", hashed) is False

    def test_verify_pin_does_not_raise_on_invalid_format_hash(self):
        assert verify_pin("1234", "not-a-valid-bcrypt-hash") is False

    def test_hash_pin_rejects_bad_policy_before_hashing(self):
        with pytest.raises(PinPolicyError):
            hash_pin("1111")

    def test_hash_pin_plaintext_not_stored_in_hash(self):
        pin = "720485"
        hashed = hash_pin(pin)
        assert pin not in hashed
        # bcrypt output never contains a substring equal to the raw pin digits
        assert bcrypt.checkpw(pin.encode("utf-8"), hashed.encode("utf-8"))


# ============================================================
# JWT TESTS
# ============================================================


SUBJECT = "550e8400-e29b-41d4-a716-446655440000"


class TestTokenConstants:
    def test_access_token_ttl_is_15_minutes(self):
        assert ACCESS_TOKEN_TTL == timedelta(minutes=15)

    def test_refresh_token_ttl_is_30_days(self):
        assert REFRESH_TOKEN_TTL == timedelta(days=30)

    def test_algorithm_is_hs256(self):
        assert JWT_ALGORITHM == "HS256"

    def test_token_types(self):
        assert TOKEN_TYPE_ACCESS == "access"
        assert TOKEN_TYPE_REFRESH == "refresh"

    def test_required_claims_cover_minimum(self):
        for claim in ("sub", "type", "iat", "exp"):
            assert claim in REQUIRED_CLAIMS


class TestAccessTokenCreation:
    def test_create_access_token_returns_non_empty_string(self):
        tok = create_access_token(SUBJECT)
        assert isinstance(tok, str)
        assert len(tok) > 30

    def test_create_access_token_rejects_empty_subject(self):
        with pytest.raises(JWTError):
            create_access_token("")

    def test_create_access_token_rejects_negative_ttl(self):
        with pytest.raises(JWTError):
            create_access_token(SUBJECT, expires_delta=timedelta(seconds=-1))

    def test_verify_access_token_roundtrip(self):
        tok = create_access_token(SUBJECT)
        claims = verify_access_token(tok)
        assert claims["sub"] == SUBJECT
        assert claims["type"] == TOKEN_TYPE_ACCESS
        assert "iat" in claims
        assert "exp" in claims
        assert isinstance(claims["iat"], int)
        assert isinstance(claims["exp"], int)
        assert claims["exp"] - claims["iat"] == int(ACCESS_TOKEN_TTL.total_seconds())

    def test_access_token_custom_ttl(self):
        custom = timedelta(minutes=2)
        tok = create_access_token(SUBJECT, expires_delta=custom)
        claims = verify_access_token(tok)
        assert claims["exp"] - claims["iat"] == int(custom.total_seconds())


class TestAccessTokenVerificationErrors:
    def test_verify_access_token_empty(self):
        with pytest.raises(TokenInvalidError):
            verify_access_token("")

    def test_verify_access_token_garbage(self):
        with pytest.raises(TokenInvalidError):
            verify_access_token("this.is.not.a.valid.token")

    def test_verify_access_token_type_mismatch_refresh_treated_as_invalid(self):
        refresh = create_refresh_token(SUBJECT)
        with pytest.raises(TokenInvalidError):
            verify_access_token(refresh)

    def test_verify_access_token_expired(self):
        tok = create_access_token(SUBJECT, expires_delta=timedelta(milliseconds=10))
        time.sleep(0.2)
        with pytest.raises(TokenExpiredError):
            verify_access_token(tok)


class TestRefreshTokenCreation:
    def test_create_refresh_token_has_jti(self):
        tok = create_refresh_token(SUBJECT)
        claims = verify_refresh_token(tok)
        assert claims["sub"] == SUBJECT
        assert claims["type"] == TOKEN_TYPE_REFRESH
        assert "jti" in claims
        uuid.UUID(claims["jti"])

    def test_create_refresh_token_30_day_ttl(self):
        tok = create_refresh_token(SUBJECT)
        claims = verify_refresh_token(tok)
        ttl = claims["exp"] - claims["iat"]
        assert ttl == int(REFRESH_TOKEN_TTL.total_seconds())

    def test_create_refresh_token_rejects_empty_subject(self):
        with pytest.raises(JWTError):
            create_refresh_token("")

    def test_verify_refresh_token_rejects_access_token_type(self):
        acc = create_access_token(SUBJECT)
        with pytest.raises(TokenInvalidError):
            verify_refresh_token(acc)

    def test_verify_refresh_token_expired(self):
        tok = create_refresh_token(SUBJECT, expires_delta=timedelta(milliseconds=50))
        time.sleep(0.2)
        with pytest.raises(TokenExpiredError):
            verify_refresh_token(tok)

    def test_verify_refresh_token_empty(self):
        with pytest.raises(TokenInvalidError):
            verify_refresh_token("")


# ============================================================
# REFRESH TOKEN HASHING TESTS
# ============================================================


class TestRefreshTokenHashing:
    def test_hash_algorithm_is_sha256(self):
        assert HASH_ALGORITHM == "sha256"

    def test_hash_refresh_token_is_64_hex_chars(self):
        fake_token = "eyJhbGciOi.eyJzdWIi.iJIUzI1NiJ9"
        h = hash_refresh_token(fake_token)
        assert isinstance(h, str)
        assert len(h) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", h) is not None

    def test_hash_refresh_token_deterministic(self):
        tok = "abc.123.xyz"
        assert hash_refresh_token(tok) == hash_refresh_token(tok)

    def test_verify_refresh_token_hash_matches(self):
        tok = create_refresh_token(SUBJECT)
        h = hash_refresh_token(tok)
        assert verify_refresh_token_hash(tok, h) is True

    def test_verify_refresh_token_hash_wrong(self):
        h = hash_refresh_token("actual.token.value")
        assert verify_refresh_token_hash("different.token.value", h) is False

    def test_verify_refresh_token_hash_empty_token(self):
        h = hash_refresh_token("any.token.here")
        assert verify_refresh_token_hash("", h) is False

    def test_verify_refresh_token_hash_empty_hash(self):
        assert verify_refresh_token_hash("any.token.here", "") is False

    def test_plaintext_jwt_flagged_as_mistake(self):
        jwt_str = create_refresh_token(SUBJECT)
        assert token_stored_hash_is_plaintext_refused(jwt_str) is True

    def test_sha256_hex_not_flagged(self):
        h = hash_refresh_token(create_refresh_token(SUBJECT))
        assert token_stored_hash_is_plaintext_refused(h) is False

    def test_hash_refresh_token_rejects_empty(self):
        with pytest.raises(ValueError):
            hash_refresh_token("")
