"""Refresh-token hashing helpers for database-side storage.

Rule: **NEVER store a plaintext refresh token in the database.**

Call sequence:
    1. ``jwt_string = create_refresh_token(user_id)``    -> plaintext JWT
    2. ``hash_string = hash_refresh_token(jwt_string)``   -> SHA-256 hex
    3. Write ``hash_string`` into ``refresh_tokens.token_hash`` in MySQL
    4. Return ``jwt_string`` to the client ONLY

Verification:
    - Client sends JWT refresh token in request
    - ``verify_refresh_token_jwt`` -> get claims (incl. ``jti``)
    - Look up stored ``token_hash`` row for user + ``jti``
    - ``verify_refresh_token_hash(incoming_jwt, stored_hash)`` must be True
    - And row's ``revoked_at`` must be None
"""
from __future__ import annotations

import hashlib
import logging
from typing import Final

LOGGER = logging.getLogger(__name__)

HASH_ALGORITHM: Final[str] = "sha256"


def hash_refresh_token(token: str) -> str:
    """Return a SHA-256 hex digest of the refresh token for DB storage.

    The plaintext token is NOT logged or stored.
    """
    if not isinstance(token, str) or not token:
        raise ValueError("Token must be a non-empty string.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_refresh_token_hash(token: str, stored_hash: str) -> bool:
    """Constant-time-ish comparison of the token hash against a stored hash.

    Returns ``True`` on match, ``False`` on mismatch.
    Never raises for non-empty inputs.
    """
    if not isinstance(token, str) or not token:
        return False
    if not isinstance(stored_hash, str) or not stored_hash:
        return False
    candidate = hash_refresh_token(token)
    if len(candidate) != len(stored_hash):
        return False
    return hashlib.sha256(token.encode("utf-8")).hexdigest() == stored_hash


def token_stored_hash_is_plaintext_refused(hash_value: str) -> bool:
    """Sanity check to catch accidental plaintext storage.

    JWTs have 3 base64url sections separated by dots and start with
    ``eyJ`` (base64 of ``{"``). A valid SHA-256 hex hash is 64 chars of [0-9a-f].
    If the stored value looks like a JWT, this returns ``True`` and should
    be treated as a security bug.
    """
    if not isinstance(hash_value, str):
        return False
    if len(hash_value) == 64 and all(c in "0123456789abcdef" for c in hash_value):
        return False
    if hash_value.count(".") >= 2 and hash_value.startswith("ey"):
        return True
    return hash_value.count(".") >= 2
