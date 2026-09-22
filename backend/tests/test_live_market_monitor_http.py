"""HTTP honesty for GET /canonical/market-status."""

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
from app.security.rate_limit import reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def monitor_settings() -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-key-for-market-monitor-32bxx",
        access_token_denylist_use_redis=False,
        market_data_cache_use_redis=False,
        rate_limit_use_redis=False,
        perpetual_evidence_source="replay",
        watcher_orchestration_enabled=False,
        market_watcher_enabled=False,
    )


@pytest.fixture
def monitor_client(monitor_settings: Settings) -> Iterator[TestClient]:
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
    app = create_app(settings=monitor_settings)
    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _register(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "monitor@example.com",
            "password": "secure-password-1",
            "organization_name": "Monitor Org",
        },
    )
    assert response.status_code == 201, response.text
    tokens = response.json()["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_market_status_requires_auth(monitor_client: TestClient) -> None:
    response = monitor_client.get("/canonical/market-status")
    assert response.status_code == 401


def test_replay_market_status_is_not_a_live_mark(monitor_client: TestClient) -> None:
    headers = _register(monitor_client)
    response = monitor_client.get("/canonical/market-status", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authority"] == "canonical_market_monitor"
    assert body["live_executable"] is False
    assert body["watcher_activated"] is False
    assert body["compatibility_price_used"] is False
    assert body["perpetual"] is True
    assert body["symbol"] == "BTCUSDT"
    assert body["mode"] == "replay"
    assert body["availability"] == "replay"
    price = body["current_price"]
    assert price["usable_as_current_market_price"] is False
    assert price["presentation"] == "replay_fixture"
    assert price["is_live"] is False
    assert price["is_mock"] is True
    assert price["fallback_used"] is False
    assert price["price"] not in {"47326", "65000", 47326, 65000}
    assert body["source"]["source_family"] == "replay_fixture"
    assert body["source"]["market_type"] == "perpetual"
    assert body["ohlcv"]["available"] is True
    assert body["provider"]["is_mock"] is True
    assert body["provider"]["using_fallback"] is False
    assert body["activation"]["state"] == "inactive"
    assert body["activation"]["configured_source"] == "replay"
    assert body["activation"]["rollback_source"] == "replay"
    assert body["activation"]["read_only"] is True
    assert body["activation"]["exchange_credentials_used"] is False
    assert body["activation"]["spot_fallback_permitted"] is False
    assert body["activation"]["trade_freshness_seconds"] == 10
    assert body["activation"]["first_symbol"] == "BTCUSDT"


def test_market_status_rejects_unknown_symbol(monitor_client: TestClient) -> None:
    headers = _register(monitor_client)
    response = monitor_client.get(
        "/canonical/market-status",
        params={"symbol": "ETHUSDT"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_perpetual_instrument"


def test_health_posture_unchanged(monitor_client: TestClient) -> None:
    response = monitor_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "paper"
    assert body["real_trading_enabled"] is False
    assert body["perpetual_evidence_source"] == "replay"
    assert body["perpetual_evidence_activation"] == "inactive"
    assert body["live_quote_freshness_seconds"] == 10
    if "market_watcher_enabled" in body:
        assert body["market_watcher_enabled"] is False
    if "watcher_orchestration_enabled" in body:
        assert body["watcher_orchestration_enabled"] is False
