"""Rate limiting tests (Redis-backed with in-memory fallback)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.security.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceededError,
    RedisRateLimiter,
    get_rate_limiter,
    reset_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def limit_settings() -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-rate-limit-secret-key-32bytes-min",
        rate_limit_use_redis=False,
        rate_limit_allow_in_memory_fallback=True,
    )


@pytest.fixture
def limit_client(limit_settings: Settings) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    get_settings.cache_clear()
    app = create_app(settings=limit_settings)
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_in_memory_limiter_allows_under_limit() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        limiter.check("test:key", limit=3, window_seconds=60)


def test_in_memory_limiter_blocks_over_limit() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(2):
        limiter.check("test:block", limit=2, window_seconds=60)
    with pytest.raises(RateLimitExceededError, match="Too many requests"):
        limiter.check("test:block", limit=2, window_seconds=60)


def test_register_rate_limit_returns_429(limit_client: TestClient) -> None:
    for index in range(10):
        response = limit_client.post(
            "/auth/register",
            json={
                "email": f"user{index}@example.com",
                "password": "secure-password-1",
                "organization_name": f"Blocked Org {index}",
            },
        )
        assert response.status_code == 201, response.text

    blocked = limit_client.post(
        "/auth/register",
        json={
            "email": "one-too-many@example.com",
            "password": "secure-password-1",
            "organization_name": "Blocked Org overflow",
        },
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limit_exceeded"


def test_refresh_endpoint_is_rate_limited(limit_client: TestClient) -> None:
    invalid_token = "x" * 32
    for _ in range(60):
        response = limit_client.post("/auth/refresh", json={"refresh_token": invalid_token})
        assert response.status_code in {401, 429}, response.text

    blocked = limit_client.post("/auth/refresh", json={"refresh_token": invalid_token})
    assert blocked.status_code == 429


def test_reset_rate_limiter_clears_shared_in_memory_state(limit_client: TestClient) -> None:
    """Regression: global limiter singleton must not leak counts across reset boundaries."""
    for index in range(10):
        response = limit_client.post(
            "/auth/register",
            json={
                "email": f"reset-leak-{index}@example.com",
                "password": "secure-password-1",
                "organization_name": f"Reset Org {index}",
            },
        )
        assert response.status_code == 201, response.text

    blocked = limit_client.post(
        "/auth/register",
        json={
            "email": "reset-leak-overflow@example.com",
            "password": "secure-password-1",
            "organization_name": "Reset Org overflow",
        },
    )
    assert blocked.status_code == 429

    reset_rate_limiter()

    recovered = limit_client.post(
        "/auth/register",
        json={
            "email": "reset-leak-recovered@example.com",
            "password": "secure-password-1",
            "organization_name": "Reset Org recovered",
        },
    )
    assert recovered.status_code == 201, recovered.text


def test_register_succeeds_in_isolated_test_after_global_exhaustion(
    limit_client: TestClient,
) -> None:
    """Regression: conftest autouse reset prevents cross-test 429 flakes in full pytest runs."""
    response = limit_client.post(
        "/auth/register",
        json={
            "email": "isolated-register@example.com",
            "password": "secure-password-1",
            "organization_name": "Isolated Org",
        },
    )
    assert response.status_code == 201, response.text


def test_redis_limiter_falls_back_when_redis_unavailable(limit_settings: Settings) -> None:
    settings = limit_settings.model_copy(
        update={
            "rate_limit_use_redis": True,
            "redis_url": "redis://127.0.0.1:59999/0",
            "rate_limit_allow_in_memory_fallback": True,
        }
    )
    reset_rate_limiter()
    limiter = get_rate_limiter(settings)
    assert isinstance(limiter, RedisRateLimiter)
    assert limiter.using_redis is False
    limiter.check("fallback:key", limit=5, window_seconds=60)


def test_redis_required_without_fallback_raises(limit_settings: Settings) -> None:
    settings = limit_settings.model_copy(
        update={
            "rate_limit_use_redis": True,
            "redis_url": "redis://127.0.0.1:59999/0",
            "rate_limit_allow_in_memory_fallback": False,
        }
    )
    reset_rate_limiter()
    with pytest.raises(RuntimeError, match="Redis rate limiting is required"):
        get_rate_limiter(settings)
