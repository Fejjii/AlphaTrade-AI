"""Tests for automatic Telegram delivery readiness and preview (Slice 71)."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Membership, PaperValidationAlert
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    MembershipRole,
    PaperAlertSeverity,
    PaperAlertType,
)
from app.security.rate_limit import reset_rate_limiter
from app.services.paper_alert_service import PaperAlertService
from app.services.telegram_automatic_delivery_service import TelegramAutomaticDeliveryService

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "telegram-auto-delivery-secret-min-32-chars",
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


def _build_client(settings: Settings) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
        yield client, factory

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    engine.dispose()


@pytest.fixture
def client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    yield from _build_client(Settings(**_BASE))


@pytest.fixture
def telegram_configured_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    settings = {
        **_BASE,
        "telegram_bot_token": "bot123456789:TESTTOKEN_secret_value",
        "telegram_chat_id": "999888777",
    }
    yield from _build_client(Settings(**settings))


@pytest.fixture
def auto_ready_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    settings = {
        **_BASE,
        "telegram_bot_token": "bot123456789:TESTTOKEN_secret_value",
        "telegram_chat_id": "999888777",
        "alert_delivery_enabled": True,
        "telegram_alerts_enabled": True,
    }
    yield from _build_client(Settings(**settings))


@pytest.fixture
def real_trading_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    settings = {
        **_BASE,
        "execution_mode": "trade",
        "enable_real_trading": True,
        "telegram_bot_token": "bot123456789:TESTTOKEN_secret_value",
        "telegram_chat_id": "999888777",
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
            "organization_name": "Auto Telegram Org",
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


def _create_alert(
    factory: sessionmaker[Session],
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str = "Eligible alert for automatic Telegram preview.",
    severity: PaperAlertSeverity = PaperAlertSeverity.INFO,
    alert_type: PaperAlertType = PaperAlertType.SETUP_SIGNAL_DETECTED,
) -> uuid.UUID:
    with factory() as session:
        created = PaperAlertService(session).create(
            organization_id=org_id,
            alert_type=alert_type,
            message=message,
            severity=severity,
            user_id=user_id,
            skip_dedup=True,
        )
        assert created is not None
        session.commit()
        return created.id


def _mark_telegram_delivered(
    factory: sessionmaker[Session],
    alert_id: uuid.UUID,
) -> None:
    with factory() as session:
        row = session.scalar(
            select(PaperValidationAlert).where(PaperValidationAlert.id == alert_id)
        )
        assert row is not None
        row.delivery_status = AlertDeliveryStatus.DELIVERED
        row.delivery_channel = AlertDeliveryChannel.TELEGRAM
        row.delivered_at = datetime.now(UTC)
        row.metadata_json = {"telegram_manual_delivered": True}
        session.commit()


def _post_preview(client: TestClient, headers: dict[str, str], **body: object):
    payload = {"channel": "telegram", "limit": 5, "severity_min": "info", **body}
    return client.post("/alerts/delivery/preview", headers=headers, json=payload)


def test_preview_requires_owner(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, factory = client
    headers, org_id, user_id = _register_owner(test_client, email="reader-preview@example.com")
    _create_alert(factory, org_id=org_id, user_id=user_id)
    _set_role(factory, user_id=user_id, role=MembershipRole.TRADER)
    response = _post_preview(test_client, headers)
    assert response.status_code == 403


def _set_role(
    factory: sessionmaker[Session],
    *,
    user_id: uuid.UUID,
    role: MembershipRole,
) -> None:
    with factory() as session:
        membership = session.query(Membership).filter(Membership.user_id == user_id).one()
        membership.role = role
        session.commit()


def test_preview_is_read_only_no_audit_mutations(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = telegram_configured_client
    headers, org_id, user_id = _register_owner(test_client, email="preview-readonly@example.com")
    alert_id = _create_alert(factory, org_id=org_id, user_id=user_id)
    with factory() as session:
        before = session.scalar(
            select(PaperValidationAlert).where(PaperValidationAlert.id == alert_id)
        )
        assert before is not None
        before_status = before.delivery_status
        before_channel = before.delivery_channel

    response = _post_preview(test_client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligible_count"] >= 1

    with factory() as session:
        after = session.scalar(
            select(PaperValidationAlert).where(PaperValidationAlert.id == alert_id)
        )
        assert after is not None
        assert after.delivery_status == before_status
        assert after.delivery_channel == before_channel


def test_preview_skips_already_delivered(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = telegram_configured_client
    headers, org_id, user_id = _register_owner(test_client, email="preview-delivered@example.com")
    delivered_id = _create_alert(factory, org_id=org_id, user_id=user_id, message="Already sent.")
    eligible_id = _create_alert(factory, org_id=org_id, user_id=user_id, message="Still pending.")
    _mark_telegram_delivered(factory, delivered_id)

    response = _post_preview(test_client, headers, limit=10)
    assert response.status_code == 200
    body = response.json()
    assert body["already_delivered_count"] >= 1
    by_id = {item["alert_id"]: item for item in body["items"]}
    assert by_id[str(delivered_id)]["status"] == "already_delivered"
    assert by_id[str(eligible_id)]["status"] == "eligible"


def test_preview_deterministic_ordering(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = telegram_configured_client
    headers, org_id, user_id = _register_owner(test_client, email="preview-order@example.com")
    first = _create_alert(factory, org_id=org_id, user_id=user_id, message="First alert.")
    second = _create_alert(factory, org_id=org_id, user_id=user_id, message="Second alert.")

    r1 = _post_preview(test_client, headers, limit=10)
    r2 = _post_preview(test_client, headers, limit=10)
    ids1 = [item["alert_id"] for item in r1.json()["items"]]
    ids2 = [item["alert_id"] for item in r2.json()["items"]]
    assert ids1 == ids2
    assert ids1.index(str(second)) < ids1.index(str(first))


def test_preview_limit_enforced(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = telegram_configured_client
    headers, org_id, user_id = _register_owner(test_client, email="preview-limit@example.com")
    for i in range(4):
        _create_alert(factory, org_id=org_id, user_id=user_id, message=f"Alert {i}.")

    response = _post_preview(test_client, headers, limit=2)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_routing_summary_includes_automatic_readiness_fields(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _factory = telegram_configured_client
    headers, _, _ = _register_owner(test_client, email="routing-auto@example.com")
    response = test_client.get("/alerts/routing/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "automatic_telegram_delivery_ready" in body
    assert body["automatic_telegram_delivery_ready"] is False
    assert isinstance(body["automatic_delivery_blockers"], list)
    assert len(body["automatic_delivery_blockers"]) > 0
    assert "eligible_pending_telegram_count" in body
    assert "already_delivered_telegram_count" in body
    assert "next_delivery_preview_count" in body
    assert body["dry_run_supported"] is True
    assert body["delivery_limits"]["max_preview_limit"] == 25


def test_missing_telegram_config_blocker(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers, org_id, user_id = _register_owner(test_client, email="blocker-token@example.com")
    _create_alert(factory, org_id=org_id, user_id=user_id)
    response = test_client.get("/alerts/routing/summary", headers=headers)
    blockers = response.json()["automatic_delivery_blockers"]
    assert any("bot token" in b.lower() for b in blockers)


def test_real_trading_enabled_blocker(
    real_trading_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = real_trading_client
    _, org_id, user_id = _register_owner(test_client, email="blocker-real@example.com")
    _create_alert(factory, org_id=org_id, user_id=user_id)
    settings = Settings(
        **{
            **_BASE,
            "execution_mode": "trade",
            "enable_real_trading": True,
            "telegram_bot_token": "bot123456789:TESTTOKEN_secret_value",
            "telegram_chat_id": "999888777",
        }
    )
    with factory() as session:
        readiness = TelegramAutomaticDeliveryService(session, settings).readiness(
            organization_id=org_id,
            user_id=user_id,
            paper_only=True,
            telegram_configured=True,
            telegram_chat_configured=True,
            external_delivery_enabled=True,
        )
    assert readiness.automatic_telegram_delivery_ready is False
    assert any("Real trading" in b for b in readiness.automatic_delivery_blockers)


def test_preview_no_secrets_in_response(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = telegram_configured_client
    headers, org_id, user_id = _register_owner(test_client, email="preview-secrets@example.com")
    _create_alert(
        factory,
        org_id=org_id,
        user_id=user_id,
        message="Contact bot123456789:SECRETTOKEN_VALUE for details.",
    )
    preview = _post_preview(test_client, headers)
    summary = test_client.get("/alerts/routing/summary", headers=headers)
    combined = json.dumps(preview.json()) + json.dumps(summary.json())
    assert re.search(r"bot[0-9]{8,}:[A-Za-z0-9_-]+", combined, re.I) is None
    assert "SECRETTOKEN_VALUE" not in combined


def test_auto_ready_false_until_explicitly_enabled(
    auto_ready_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = auto_ready_client
    headers, org_id, user_id = _register_owner(test_client, email="auto-not-ready@example.com")
    _create_alert(factory, org_id=org_id, user_id=user_id)
    prefs = test_client.patch(
        "/notifications/preferences",
        headers=headers,
        json={"telegram_enabled": True},
    )
    assert prefs.status_code == 200
    body = test_client.get("/alerts/routing/summary", headers=headers).json()
    assert body["automatic_telegram_delivery_ready"] is False
    blockers = body["automatic_delivery_blockers"]
    assert any("not enabled" in b.lower() for b in blockers)
