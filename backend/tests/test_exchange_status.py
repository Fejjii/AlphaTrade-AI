"""Tests for GET /exchange/status (owner-scoped, redacted)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
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

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "exchange-status-test-secret-min-32-bytes",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
}

_DEMO_SETTINGS = {
    **_BASE,
    "exchange_mode": "paper_exchange_demo",
    "blofin_demo_enabled": True,
    "blofin_api_key": "demo-key",
    "blofin_api_secret": "demo-secret",
    "blofin_api_passphrase": "demo-pass",
    "blofin_demo_rest_base_url": "https://demo-trading-openapi.blofin.com",
}


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


def _build_client(settings: Settings) -> Iterator[TestClient]:
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
    app = create_app(settings=settings)
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    engine.dispose()


@pytest.fixture
def exchange_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def _handler(request: httpx.Request) -> httpx.Response:
        if "query-apikey" in request.url.path:
            return httpx.Response(
                200,
                json={"code": "0", "data": [{"permissions": "read trade"}]},
            )
        return httpx.Response(200, json={"code": "0", "data": []})

    from app.providers.exchange import factory as exchange_factory

    original_build = exchange_factory.build_blofin_client

    def _build(settings, *, transport=None, **kwargs):
        return original_build(
            settings, transport=transport or httpx.MockTransport(_handler), **kwargs
        )

    monkeypatch.setattr(exchange_factory, "build_blofin_client", _build)
    yield from _build_client(Settings(**_DEMO_SETTINGS))


@pytest.fixture
def internal_client() -> Iterator[TestClient]:
    yield from _build_client(Settings(**_BASE))


def _register_owner(client: TestClient, email: str = "owner@example.com") -> dict[str, str]:
    reg = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "organization_name": "Exchange Org",
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_exchange_status_requires_owner(exchange_client: TestClient) -> None:
    response = exchange_client.get("/exchange/status")
    assert response.status_code == 401


def test_exchange_status_redacts_secrets(exchange_client: TestClient) -> None:
    headers = _register_owner(exchange_client)
    response = exchange_client.get("/exchange/status", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    raw = json.dumps(body).lower()

    assert body["exchange_mode"] == "paper_exchange_demo"
    assert body["execution_mode"] == "paper"
    assert body["real_trading_enabled"] is False
    assert body["blofin_demo_enabled"] is True
    assert body["demo_active"] is True
    assert body["api_key_configured"] is True
    assert body["api_secret_configured"] is True
    assert body["api_passphrase_configured"] is True
    assert body["credentials_configured"] is True

    forbidden = (
        "demo-key",
        "demo-secret",
        "demo-pass",
        "blofin_api_key",
        "blofin_api_secret",
        "blofin_api_passphrase",
        "demo-trading-openapi",
        "access-sign",
        "access-key",
    )
    for needle in forbidden:
        assert needle not in raw

    if body.get("provider"):
        provider_raw = json.dumps(body["provider"]).lower()
        for needle in forbidden:
            assert needle not in provider_raw


def test_exchange_status_internal_mode_booleans_only(internal_client: TestClient) -> None:
    headers = _register_owner(internal_client)
    response = internal_client.get("/exchange/status", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exchange_mode"] == "paper_internal"
    assert body["demo_active"] is False
    assert body["credentials_configured"] is False
    assert body["api_key_configured"] is False
