"""Access-token denylist fail-closed behavior (AT-018)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.security.token_denylist import (
    TokenDenylistUnavailableError,
    _InMemoryDenylist,
    _RedisDenylist,
    get_access_token_denylist,
    reset_access_token_denylist,
)
from tests.test_deployment_safety import _STAGING_BASE


@pytest.fixture(autouse=True)
def _reset_denylist() -> Iterator[None]:
    reset_access_token_denylist()
    yield
    reset_access_token_denylist()


def _local_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "local",
        "log_json": False,
        "database_url": "sqlite+pysqlite:///:memory:",
        "jwt_secret": "test-denylist-secret-key-32bytes-min",
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


def test_staging_construction_failure_raises_instead_of_memory_fallback() -> None:
    settings = Settings(**_STAGING_BASE)
    with (
        patch("redis.from_url", side_effect=ConnectionError("redis down")),
        pytest.raises(ConnectionError),
    ):
        get_access_token_denylist(settings)


def test_local_construction_failure_falls_back_to_memory() -> None:
    settings = _local_settings()
    with patch("redis.from_url", side_effect=ConnectionError("redis down")):
        denylist = get_access_token_denylist(settings)
    assert isinstance(denylist, _InMemoryDenylist)


def test_local_construction_failure_raises_when_fallback_disabled() -> None:
    settings = _local_settings(rate_limit_allow_in_memory_fallback=False)
    with (
        patch("redis.from_url", side_effect=ConnectionError("redis down")),
        pytest.raises(ConnectionError),
    ):
        get_access_token_denylist(settings)


def test_add_fails_closed_outside_local() -> None:
    settings = Settings(**_STAGING_BASE)
    denylist = _RedisDenylist(settings)
    with (
        patch.object(denylist._client, "setex", side_effect=ConnectionError("redis down")),
        pytest.raises(TokenDenylistUnavailableError),
    ):
        denylist.add("jti-1", ttl_seconds=60)


def test_add_fails_open_in_local() -> None:
    settings = _local_settings()
    denylist = _RedisDenylist(settings)
    with patch.object(denylist._client, "setex", side_effect=ConnectionError("redis down")):
        denylist.add("jti-1", ttl_seconds=60)  # no raise


def test_is_denied_fails_closed_outside_local() -> None:
    settings = Settings(**_STAGING_BASE)
    denylist = _RedisDenylist(settings)
    with patch.object(denylist._client, "exists", side_effect=ConnectionError("redis down")):
        assert denylist.is_denied("jti-1") is True


def test_is_denied_fails_open_in_local() -> None:
    settings = _local_settings()
    denylist = _RedisDenylist(settings)
    with patch.object(denylist._client, "exists", side_effect=ConnectionError("redis down")):
        assert denylist.is_denied("jti-1") is False
