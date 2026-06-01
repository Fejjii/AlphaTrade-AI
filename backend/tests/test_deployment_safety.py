"""Tests for staging/production deployment safety invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.deployment_safety import deployment_posture, validate_deployment_settings

_STAGING_BASE = {
    "environment": "staging",
    "jwt_secret": "x" * 32,
    "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
    "redis_url": "redis://redis.example.com:6379/0",
    "qdrant_url": "https://qdrant.example.com",
    "cors_origins": "https://app.example.com",
    "auth_refresh_cookie_enabled": True,
    "auth_cookie_secure": True,
    "auth_cookie_samesite": "none",
    "enable_real_trading": False,
    "execution_mode": "paper",
    "rate_limit_use_redis": True,
    "debug": False,
}

_PRODUCTION_BASE = {**_STAGING_BASE, "environment": "production"}


def test_staging_valid_settings_pass() -> None:
    settings = Settings(**_STAGING_BASE)
    assert settings.environment.value == "staging"
    assert settings.real_trading_enabled is False


def test_production_rejects_weak_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(**{**_STAGING_BASE, "environment": "production", "jwt_secret": "short"})


def test_staging_rejects_known_weak_jwt_placeholder() -> None:
    with pytest.raises(ValidationError, match="weak placeholder"):
        Settings(
            **{
                **_STAGING_BASE,
                "jwt_secret": "change-me-in-production-use-long-random-value",
            }
        )


def test_staging_rejects_missing_managed_database_url() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(**{**_STAGING_BASE, "database_url": "postgresql+psycopg://u:p@localhost:5432/db"})


def test_staging_rejects_unsafe_cookie_config() -> None:
    with pytest.raises(ValidationError, match="auth_cookie_secure"):
        Settings(**{**_STAGING_BASE, "auth_cookie_secure": False})


def test_staging_rejects_cookie_mode_disabled() -> None:
    with pytest.raises(ValidationError, match="auth_refresh_cookie_enabled"):
        Settings(**{**_STAGING_BASE, "auth_refresh_cookie_enabled": False})


def test_staging_rejects_real_trading_enabled() -> None:
    with pytest.raises(ValidationError, match="enable_real_trading"):
        Settings(**{**_STAGING_BASE, "enable_real_trading": True})


def test_staging_rejects_trade_execution_mode() -> None:
    with pytest.raises(ValidationError, match="execution_mode=trade"):
        Settings(**{**_STAGING_BASE, "execution_mode": "trade", "enable_real_trading": True})


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="debug"):
        Settings(**{**_STAGING_BASE, "environment": "production", "debug": True})


def test_deployment_posture_excludes_secrets() -> None:
    settings = Settings(**_STAGING_BASE, openai_api_key="sk-secret")
    posture = deployment_posture(settings)
    assert "sk-secret" not in str(posture)
    assert posture["openai_configured"] is True
    assert "jwt_secret" not in posture


def test_validate_deployment_skips_local() -> None:
    settings = Settings()
    validate_deployment_settings(settings)  # no raise
