"""Password hashing with bcrypt (used directly — passlib is incompatible with
bcrypt 4+/5).

bcrypt only considers the first 72 bytes of the password, and raises on longer
input, so we truncate to 72 bytes before hashing/verifying.
"""
from __future__ import annotations

import bcrypt

_MAX_BCRYPT_BYTES = 72


def _to_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False
