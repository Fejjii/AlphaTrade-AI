"""JWT access token helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import Settings
from app.core.errors import AuthError


def create_access_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    email: str,
    settings: Settings,
) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "email": email,
        "type": "access",
        "jti": jti,
        "exp": datetime.now(UTC) + timedelta(seconds=expires_in),
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired access token.") from exc
    if payload.get("type") != "access":
        raise AuthError("Invalid access token type.")
    return payload
