"""Deployment safety checks for staging and production environments.

Validates invariants at settings load time so the service fails fast rather than
starting with unsafe configuration. Local and Docker Compose development are
unaffected unless ``ENVIRONMENT`` is set to ``staging`` or ``production``.
"""

from __future__ import annotations

from app.core.config import Environment, ExecutionMode, Settings

_LOCALHOST_MARKERS = ("localhost", "127.0.0.1")
_WEAK_JWT_SECRETS = frozenset(
    {
        "dev-only-change-me-before-production",
        "change-me-in-production-use-long-random-value",
        "changeme",
        "secret",
    }
)
_VALID_SAMESITE = frozenset({"lax", "strict", "none"})


def _url_uses_localhost(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in _LOCALHOST_MARKERS)


def _cookie_secure_resolved(settings: Settings) -> bool:
    if settings.auth_cookie_secure is not None:
        return settings.auth_cookie_secure
    return settings.environment is not Environment.LOCAL


def validate_deployment_settings(settings: Settings) -> None:
    """Raise ``ValueError`` when staging/production invariants are violated."""
    if settings.environment not in (Environment.STAGING, Environment.PRODUCTION):
        return

    errors: list[str] = []

    if settings.enable_real_trading:
        errors.append("enable_real_trading must be false in staging/production")
    if settings.execution_mode is ExecutionMode.TRADE:
        errors.append("execution_mode=trade is not allowed in staging/production")

    if settings.jwt_secret.strip().lower() in _WEAK_JWT_SECRETS:
        errors.append("jwt_secret is a known weak placeholder; use a long random value")

    if not settings.auth_refresh_cookie_enabled:
        errors.append("auth_refresh_cookie_enabled must be true in staging/production")

    if not _cookie_secure_resolved(settings):
        errors.append("auth_cookie_secure must be true in staging/production (HTTPS only)")

    samesite = settings.auth_cookie_samesite.strip().lower()
    if samesite not in _VALID_SAMESITE:
        errors.append(f"auth_cookie_samesite must be one of {sorted(_VALID_SAMESITE)}")
    elif samesite == "none" and not _cookie_secure_resolved(settings):
        errors.append("auth_cookie_samesite=none requires auth_cookie_secure=true")

    if not settings.database_url.strip():
        errors.append("database_url is required in staging/production")
    elif _url_uses_localhost(settings.database_url):
        errors.append("database_url must point to managed Postgres (not localhost)")

    if not settings.redis_url.strip():
        errors.append("redis_url is required in staging/production")
    elif _url_uses_localhost(settings.redis_url):
        errors.append("redis_url must point to managed Redis (not localhost)")

    if not settings.qdrant_url.strip():
        errors.append("qdrant_url is required in staging/production")
    elif _url_uses_localhost(settings.qdrant_url):
        errors.append("qdrant_url must point to hosted Qdrant (not localhost)")

    if not settings.cors_origins:
        errors.append("cors_origins must include the deployed frontend URL(s)")

    if not settings.rate_limit_use_redis:
        errors.append("rate_limit_use_redis must be true in staging/production")

    if settings.environment is Environment.PRODUCTION and settings.debug:
        errors.append("debug must be false in production")

    if errors:
        joined = "; ".join(errors)
        raise ValueError(f"deployment safety check failed: {joined}")


def deployment_posture(settings: Settings) -> dict[str, object]:
    """Return a redaction-safe summary for startup logs (no secrets)."""
    return {
        "environment": settings.environment.value,
        "execution_mode": settings.execution_mode.value,
        "real_trading_enabled": settings.real_trading_enabled,
        "enable_real_trading": settings.enable_real_trading,
        "provider_mode": settings.provider_mode,
        "auth_refresh_cookie_enabled": settings.auth_refresh_cookie_enabled,
        "auth_cookie_secure": _cookie_secure_resolved(settings),
        "auth_cookie_samesite": settings.auth_cookie_samesite,
        "rate_limit_use_redis": settings.rate_limit_use_redis,
        "cors_origin_count": len(settings.cors_origins),
        "log_json": settings.log_json,
        "debug": settings.debug,
        "openai_configured": bool(settings.openai_api_key.strip()),
    }
