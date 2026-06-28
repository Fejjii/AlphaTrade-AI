"""Tests for GET /alerts/routing/summary (owner-scoped, read-only)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import suppress
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import MarketWatcherBridgeDecision
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    MarketWatcherBridgeDecisionType,
)
from app.security.rate_limit import reset_rate_limiter
from app.services.alert_routing_diagnostics_service import (
    RoutingDiagnosticsInputs,
    compute_alert_routing_readiness,
)

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "alert-routing-diagnostics-test-secret-min-32",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "alert_webhook_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
    "market_watcher_bridge_enabled": False,
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
def client() -> Iterator[TestClient]:
    yield from _build_client(Settings(**_BASE))


@pytest.fixture
def telegram_enabled_client() -> Iterator[TestClient]:
    settings = {**_BASE, "telegram_alerts_enabled": True}
    yield from _build_client(Settings(**settings))


@pytest.fixture
def external_delivery_client() -> Iterator[TestClient]:
    settings = {
        **_BASE,
        "alert_delivery_enabled": True,
        "alert_webhook_enabled": True,
        "alert_webhook_url": "https://example.com/hook",
    }
    yield from _build_client(Settings(**settings))


def _register_owner(
    client: TestClient,
    email: str = "owner@example.com",
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    reg = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "organization_name": "Alerts Org",
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    org_id = uuid.UUID(reg.json()["organization"]["id"])
    user_id = uuid.UUID(reg.json()["user"]["id"])
    return {"Authorization": f"Bearer {token}"}, org_id, user_id


def _seed_bridge_failure(
    client: TestClient,
    *,
    org_id: uuid.UUID,
) -> None:
    override = client.app.dependency_overrides[get_session]
    session_gen = override()
    session = next(session_gen)
    try:
        session.add(
            MarketWatcherBridgeDecision(
                id=uuid.uuid4(),
                organization_id=org_id,
                decision=MarketWatcherBridgeDecisionType.FAILED,
                reason="Bridge failed with bot123456789:ABCDEF_secret",
                blockers=[],
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        with suppress(StopIteration):
            next(session_gen)


def _safe_inputs(**overrides: object) -> RoutingDiagnosticsInputs:
    base = RoutingDiagnosticsInputs(
        real_trading_enabled=False,
        paper_only=True,
        external_delivery_enabled=False,
        telegram_enabled=False,
        telegram_configured=True,
        telegram_user_enabled=False,
        telegram_chat_configured=True,
        webhook_enabled=False,
        webhook_configured=True,
        worker_enabled=False,
        worker_running=False,
        worker_running_unexpected=False,
        bridge_enabled=False,
        bridge_running=False,
        bridge_paper_only=True,
        bridge_last_decision=None,
        bridge_last_error=None,
        failed_alerts_count=0,
        pending_alerts_count=0,
        delivery_disabled=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_routing_summary_requires_owner(client: TestClient) -> None:
    response = client.get("/alerts/routing/summary")
    assert response.status_code == 401


def test_routing_summary_ready_when_safely_disabled(client: TestClient) -> None:
    headers, _, _ = _register_owner(client)
    response = client.get("/alerts/routing/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["readiness"] == "ready"
    assert body["alerts_enabled"] is True
    assert body["telegram_enabled"] is False
    assert body["webhook_enabled"] is False
    assert body["external_delivery_enabled"] is False
    assert body["paper_only"] is True
    assert body["worker_enabled"] is False
    assert body["worker_running"] is False
    assert body["bridge_enabled"] is False
    assert body["market_watcher_configured"] is False


def test_routing_summary_redacts_bridge_errors(client: TestClient) -> None:
    headers, org_id, _ = _register_owner(client, email="bridge-fail@example.com")
    _seed_bridge_failure(client, org_id=org_id)
    response = client.get("/alerts/routing/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    raw = json.dumps(body).lower()
    assert body["readiness"] == "degraded"
    assert body["bridge_last_error"] is not None
    assert "bot123456789" not in raw
    assert "abcdef_secret" not in raw


def test_routing_summary_blocked_telegram_without_token(
    telegram_enabled_client: TestClient,
) -> None:
    headers, _, _ = _register_owner(telegram_enabled_client, email="telegram-missing@example.com")
    response = telegram_enabled_client.get("/alerts/routing/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["readiness"] == "blocked"
    assert body["telegram_enabled"] is True
    assert any("telegram" in warning.lower() for warning in body["warnings"])


def test_routing_summary_external_delivery_enabled_paper_only(
    external_delivery_client: TestClient,
) -> None:
    headers, _, _ = _register_owner(external_delivery_client, email="external@example.com")
    response = external_delivery_client.get("/alerts/routing/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["external_delivery_enabled"] is True
    assert body["paper_only"] is True
    assert body["readiness"] in {"ready", "degraded"}


def test_compute_readiness_rules() -> None:
    assert compute_alert_routing_readiness(_safe_inputs()) == "ready"

    assert compute_alert_routing_readiness(_safe_inputs(real_trading_enabled=True)) == "blocked"
    assert (
        compute_alert_routing_readiness(
            _safe_inputs(external_delivery_enabled=True, paper_only=False)
        )
        == "blocked"
    )
    assert (
        compute_alert_routing_readiness(_safe_inputs(worker_running_unexpected=True)) == "blocked"
    )
    assert (
        compute_alert_routing_readiness(
            _safe_inputs(telegram_enabled=True, telegram_configured=False)
        )
        == "blocked"
    )
    assert (
        compute_alert_routing_readiness(
            _safe_inputs(webhook_enabled=True, webhook_configured=False)
        )
        == "blocked"
    )
    assert compute_alert_routing_readiness(_safe_inputs(bridge_paper_only=False)) == "blocked"
    assert (
        compute_alert_routing_readiness(
            _safe_inputs(
                bridge_last_decision="attempt_execute",
                bridge_last_error="bridge tried place_order",
            )
        )
        == "blocked"
    )

    assert (
        compute_alert_routing_readiness(_safe_inputs(bridge_enabled=True, bridge_running=False))
        == "degraded"
    )
    assert compute_alert_routing_readiness(_safe_inputs(failed_alerts_count=2)) == "degraded"
    assert (
        compute_alert_routing_readiness(
            _safe_inputs(delivery_disabled=True, pending_alerts_count=3)
        )
        == "degraded"
    )
