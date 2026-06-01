"""HttpOnly refresh-token cookie helpers."""

from __future__ import annotations

from fastapi import Response

from app.core.config import Environment, Settings


def refresh_cookie_secure(settings: Settings) -> bool:
    """Resolve secure flag — explicit override or environment default."""
    if settings.auth_cookie_secure is not None:
        return settings.auth_cookie_secure
    return settings.environment is not Environment.LOCAL


def set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    """Attach the rotating refresh token as an httpOnly cookie."""
    if not settings.auth_refresh_cookie_enabled:
        return
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=refresh_cookie_secure(settings),
        samesite=settings.auth_cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=settings.auth_refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    """Remove the refresh cookie on logout."""
    if not settings.auth_refresh_cookie_enabled:
        return
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        path=settings.auth_refresh_cookie_path,
        httponly=True,
        secure=refresh_cookie_secure(settings),
        samesite=settings.auth_cookie_samesite,
    )
