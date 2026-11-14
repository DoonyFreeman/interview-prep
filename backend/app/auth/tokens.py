"""JWT creation/verification (long-lived access token, no refresh).

Named ``tokens`` rather than ``jwt`` to avoid confusion with ``jose.jwt``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings


def create_access_token(subject: str, *, account_created_at: datetime) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire, "account_created_at": account_created_at.isoformat()}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_payload(token: str) -> dict | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    return payload


def decode_token(token: str) -> str | None:
    """Return the token subject (user id as str), or None if invalid/expired."""
    payload = _decode_payload(token)
    return payload.get("sub") if payload is not None else None


def token_matches_account(token: str, created_at: datetime) -> bool:
    payload = _decode_payload(token)
    return payload is not None and payload.get("account_created_at") == created_at.isoformat()
