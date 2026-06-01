"""JWT secret validation tests."""

from __future__ import annotations

import pytest

from app.core.config import Environment, Settings
from tests.test_deployment_safety import _PRODUCTION_BASE, _STAGING_BASE


def test_local_allows_short_jwt_secret() -> None:
    settings = Settings(environment=Environment.LOCAL, jwt_secret="short-dev-secret")
    assert settings.jwt_secret == "short-dev-secret"


def test_staging_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValueError, match="jwt_secret must be at least"):
        Settings(**{**_STAGING_BASE, "jwt_secret": "too-short"})


def test_production_requires_long_jwt_secret() -> None:
    settings = Settings(
        **{
            **_PRODUCTION_BASE,
            "jwt_secret": "production-grade-secret-with-32-byte-minimum-length",
        }
    )
    assert len(settings.jwt_secret.encode("utf-8")) >= settings.jwt_secret_min_length
