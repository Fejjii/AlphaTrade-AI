"""Password hashing and validation."""

from __future__ import annotations

import bcrypt

from app.core.config import Settings
from app.core.errors import ValidationAppError


def validate_password(password: str, settings: Settings) -> None:
    if len(password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters.",
        )
    if len(password) > settings.password_max_length:
        raise ValidationAppError(
            f"Password must be at most {settings.password_max_length} characters.",
        )
    if len(password.encode("utf-8")) > settings.bcrypt_max_password_bytes:
        raise ValidationAppError(
            "Password exceeds the bcrypt byte limit; use a shorter password.",
        )


def hash_password(password: str, settings: Settings) -> str:
    validate_password(password, settings)
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("utf-8")


def verify_password(password: str, hashed_password: str, settings: Settings) -> bool:
    if len(password.encode("utf-8")) > settings.bcrypt_max_password_bytes:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False
