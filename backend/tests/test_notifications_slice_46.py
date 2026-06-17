"""Slice 46 — notification preferences, Telegram provider, and delivery routing."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.mutation_policy import mutation_allowed
from app.core.config import Settings
from app.db.base import Base
from app.db.models import Membership, Organization, PaperValidationAlert, User
from app.db.session import get_session
from app.main import create_app
from app.providers.alert_delivery.base import AlertDeliveryPayload
from app.providers.alert_delivery.telegram import TelegramAlertDeliveryProvider
from app.providers.alert_delivery.webhook import WebhookAlertDeliveryProvider
from app.schemas.common import (
    AlertDeliveryStatus,
    MembershipRole,
    PaperAlertSeverity,
    PaperAlertType,
)
from app.schemas.notifications import NotificationPreferencesUpdate
from app.security.passwords import hash_password
from app.services.alert_delivery_service import AlertDeliveryService
from app.services.audit_service import AuditService
from app.services.delivery_routing_service import route_alert_delivery
from app.services.notifications.preferences_service import NotificationPreferencesService
from app.services.paper_alert_service import PaperAlertService
from app.tools.registry import _require_mutation_confirmation, build_default_registry

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000500")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000501")
READER_ID = uuid.UUID("00000000-0000-0000-0000-000000000502")


@pytest.fixture
def slice46_db() -> Iterator[sessionmaker[Session]]:
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
    settings = Settings(
        environment="local",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="slice46-test-secret-key-minimum",
    )
    with factory() as session:
        org = Organization(id=ORG_ID, name="Slice46 Org")
        owner = User(
            id=USER_ID,
            email="owner46@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        reader = User(
            id=READER_ID,
            email="reader46@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        session.add(org)
        session.add(owner)
        session.add(reader)
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.add(
            Membership(user_id=READER_ID, organization_id=ORG_ID, role=MembershipRole.TRADER)
        )
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _settings(**overrides: object) -> Settings:
    base = {
        "environment": "local",
        "log_json": False,
        "execution_mode": "paper",
        "enable_real_trading": False,
        "database_url": "sqlite+pysqlite:///:memory:",
        "jwt_secret": "slice46-test-secret-key-minimum",
        "rate_limit_use_redis": False,
        "access_token_denylist_use_redis": False,
        "provider_mode": "mock",
        "alert_delivery_enabled": False,
        "alert_webhook_enabled": False,
        "telegram_alerts_enabled": False,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def slice46_client(slice46_db: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app(settings=_settings())

    def _override_session() -> Iterator[Session]:
        with slice46_db() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "owner46@test.example", "password": "TestPassword123!"},
        )
        token = login.json()["tokens"]["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


def _create_alert(session: Session, settings: Settings | None = None) -> PaperValidationAlert:
    svc = PaperAlertService(session)
    created = svc.create(
        organization_id=ORG_ID,
        alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
        message="Test alert",
        user_id=USER_ID,
    )
    assert created is not None
    row = session.scalar(select(PaperValidationAlert).where(PaperValidationAlert.id == created.id))
    assert row is not None
    return row


def test_notification_preferences_default_in_app_only(slice46_client: TestClient) -> None:
    resp = slice46_client.get("/notifications/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["in_app_enabled"] is True
    assert body["webhook_enabled"] is False
    assert body["telegram_enabled"] is False
    assert body["using_defaults"] is True


def test_patch_notification_preferences(slice46_client: TestClient) -> None:
    resp = slice46_client.patch(
        "/notifications/preferences",
        json={"webhook_enabled": True, "min_severity": "warning"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["webhook_enabled"] is True
    assert body["min_severity"] == "warning"


def test_invalid_severity_rejected(slice46_client: TestClient) -> None:
    resp = slice46_client.patch(
        "/notifications/preferences",
        json={"min_severity": "invalid"},
    )
    assert resp.status_code == 422


def test_telegram_disabled_by_default() -> None:
    provider = TelegramAlertDeliveryProvider(_settings())
    assert provider.is_enabled() is False


def test_telegram_not_called_when_disabled() -> None:
    mock_post = MagicMock()
    provider = TelegramAlertDeliveryProvider(_settings(), http_post=mock_post)
    result = provider.deliver(
        AlertDeliveryPayload(
            alert_id="a",
            organization_id=str(ORG_ID),
            alert_type="setup_signal_detected",
            severity="info",
            message="hello",
            telegram_chat_id="12345",
        )
    )
    assert result.skipped is True
    mock_post.assert_not_called()


def test_telegram_success_updates_delivery_status(slice46_db: sessionmaker[Session]) -> None:
    mock_post = MagicMock(return_value=MagicMock(status_code=200))
    settings = _settings(
        alert_delivery_enabled=True,
        telegram_alerts_enabled=True,
        telegram_bot_token="bot-token",
        telegram_chat_id="12345",
    )
    with slice46_db() as session:
        prefs = NotificationPreferencesService(session, AuditService(session))
        prefs.update(
            NotificationPreferencesUpdate(webhook_enabled=False, telegram_enabled=True),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        row = _create_alert(session, settings=settings)
        row.delivery_status = AlertDeliveryStatus.PENDING
        session.flush()
        delivery = AlertDeliveryService(session, settings, http_post=mock_post)
        result = delivery.deliver_alert(row.id, organization_id=ORG_ID, user_id=USER_ID)
        assert result.delivered is True
        assert result.alert.delivery_status == AlertDeliveryStatus.DELIVERED
        mock_post.assert_called_once()


def test_telegram_failure_redacted(slice46_db: sessionmaker[Session]) -> None:
    mock_post = MagicMock(side_effect=httpx.ConnectError("bot-token-refused"))
    settings = _settings(
        alert_delivery_enabled=True,
        telegram_alerts_enabled=True,
        telegram_bot_token="bot-token",
        telegram_chat_id="12345",
    )
    with slice46_db() as session:
        prefs = NotificationPreferencesService(session, AuditService(session))
        prefs.update(
            NotificationPreferencesUpdate(telegram_enabled=True),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        row = _create_alert(session, settings=settings)
        row.delivery_status = AlertDeliveryStatus.PENDING
        session.flush()
        delivery = AlertDeliveryService(session, settings, http_post=mock_post)
        result = delivery.deliver_alert(row.id, organization_id=ORG_ID, user_id=USER_ID)
        assert result.delivered is False
        assert result.alert.delivery_status == AlertDeliveryStatus.FAILED
        assert "bot-token" not in (result.alert.last_delivery_error or "")


def test_delivery_routing_respects_severity_threshold(slice46_db: sessionmaker[Session]) -> None:
    settings = _settings(alert_delivery_enabled=True, alert_webhook_enabled=True)
    with slice46_db() as session:
        prefs_service = NotificationPreferencesService(session, AuditService(session))
        prefs = prefs_service.update(
            NotificationPreferencesUpdate(
                webhook_enabled=True,
                min_severity=PaperAlertSeverity.WARNING,
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        delivery = AlertDeliveryService(session, settings)
        routing = route_alert_delivery(
            settings=settings,
            preferences=prefs,
            providers=delivery._providers,
            severity=PaperAlertSeverity.INFO,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        assert routing.should_deliver is False
        assert "below minimum" in (routing.skipped_reason or "")


def test_delivery_routing_respects_alert_type_filter(slice46_db: sessionmaker[Session]) -> None:
    settings = _settings(alert_delivery_enabled=True, alert_webhook_enabled=True)
    with slice46_db() as session:
        prefs_service = NotificationPreferencesService(session, AuditService(session))
        prefs = prefs_service.update(
            NotificationPreferencesUpdate(
                webhook_enabled=True,
                enabled_alert_types=[PaperAlertType.DATA_STALE],
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        delivery = AlertDeliveryService(session, settings)
        routing = route_alert_delivery(
            settings=settings,
            preferences=prefs,
            providers=delivery._providers,
            severity=PaperAlertSeverity.INFO,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        assert routing.should_deliver is False


def test_quiet_hours_skip(slice46_db: sessionmaker[Session]) -> None:
    settings = _settings(
        alert_delivery_enabled=True,
        alert_webhook_enabled=True,
        alert_webhook_url="https://example.com/hook",
    )
    with slice46_db() as session:
        prefs_service = NotificationPreferencesService(session, AuditService(session))
        prefs = prefs_service.update(
            NotificationPreferencesUpdate(
                webhook_enabled=True,
                quiet_hours_enabled=True,
                quiet_hours_start="00:00",
                quiet_hours_end="23:59",
                timezone="UTC",
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        delivery = AlertDeliveryService(session, settings)
        routing = route_alert_delivery(
            settings=settings,
            preferences=prefs,
            providers=delivery._providers,
            severity=PaperAlertSeverity.CRITICAL,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        assert routing.should_deliver is False
        assert "Quiet hours" in (routing.skipped_reason or "")


def test_test_notification_safe(slice46_client: TestClient) -> None:
    resp = slice46_client.post("/notifications/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_only"] is True
    assert "TEST" in body["test_label"]


def test_deliver_pending_requires_owner(slice46_db: sessionmaker[Session]) -> None:
    app = create_app(settings=_settings(alert_delivery_enabled=True))

    def _override_session() -> Iterator[Session]:
        with slice46_db() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "reader46@test.example", "password": "TestPassword123!"},
        )
        token = login.json()["tokens"]["access_token"]
        resp = client.post(
            "/alerts/deliver-pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_agent_notification_update_requires_confirmation() -> None:
    blocked = _require_mutation_confirmation(
        "notification_preferences_tool",
        {"user_message": "turn on telegram"},
        action="update notification preferences",
    )
    assert blocked is not None
    assert mutation_allowed("I confirm update notification preferences", confirm_arg=True)


def test_agent_notification_question_does_not_mutate() -> None:
    blocked = _require_mutation_confirmation(
        "notification_preferences_tool",
        {"user_message": "should I turn on Telegram alerts?"},
        action="update notification preferences",
    )
    assert blocked is not None


def test_agent_test_notification_requires_confirmation() -> None:
    blocked = _require_mutation_confirmation(
        "notification_preferences_tool",
        {"user_message": "send a test notification"},
        action="send test notification",
    )
    assert blocked is not None


def test_agent_telegram_status_read_only(slice46_db: sessionmaker[Session]) -> None:
    from app.tools.registry import _notification_preferences_execute

    with slice46_db() as session:
        out = _notification_preferences_execute(
            {
                "organization_id": str(ORG_ID),
                "user_id": str(USER_ID),
                "action": "telegram_enabled",
                "user_message": "are Telegram alerts enabled?",
            },
            session,
        )
        assert out.success is True
        assert out.result is not None
        assert out.result["effective"] is False


def test_delivery_routing_user_pref_alone_insufficient(slice46_db: sessionmaker[Session]) -> None:
    settings = _settings(alert_delivery_enabled=False, alert_webhook_enabled=True)
    with slice46_db() as session:
        prefs_service = NotificationPreferencesService(session, AuditService(session))
        prefs = prefs_service.update(
            NotificationPreferencesUpdate(webhook_enabled=True),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        delivery = AlertDeliveryService(session, settings)
        routing = route_alert_delivery(
            settings=settings,
            preferences=prefs,
            providers=delivery._providers,
            severity=PaperAlertSeverity.CRITICAL,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        assert routing.should_deliver is False
        assert "disabled globally" in (routing.skipped_reason or "").lower()


def test_delivery_routing_env_alone_insufficient(slice46_db: sessionmaker[Session]) -> None:
    settings = _settings(
        alert_delivery_enabled=True,
        alert_webhook_enabled=True,
        alert_webhook_url="https://example.com/hook",
    )
    with slice46_db() as session:
        prefs = NotificationPreferencesService(session, AuditService(session)).get(
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        delivery = AlertDeliveryService(session, settings)
        routing = route_alert_delivery(
            settings=settings,
            preferences=prefs,
            providers=delivery._providers,
            severity=PaperAlertSeverity.CRITICAL,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        assert routing.should_deliver is False
        assert "external channels" in (routing.skipped_reason or "").lower()


def test_digest_mode_skips_immediate_external(slice46_db: sessionmaker[Session]) -> None:
    from app.schemas.common import NotificationDigestMode

    settings = _settings(
        alert_delivery_enabled=True,
        alert_webhook_enabled=True,
        alert_webhook_url="https://example.com/hook",
    )
    with slice46_db() as session:
        prefs_service = NotificationPreferencesService(session, AuditService(session))
        prefs = prefs_service.update(
            NotificationPreferencesUpdate(
                webhook_enabled=True,
                digest_mode=NotificationDigestMode.DAILY_DIGEST,
            ),
            organization_id=ORG_ID,
            user_id=USER_ID,
        )
        delivery = AlertDeliveryService(session, settings)
        routing = route_alert_delivery(
            settings=settings,
            preferences=prefs,
            providers=delivery._providers,
            severity=PaperAlertSeverity.CRITICAL,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        assert routing.should_deliver is False
        assert "digest" in (routing.skipped_reason or "").lower()


def test_webhook_signed_still_works() -> None:
    captured: dict = {}

    def mock_post(url: str, **kwargs: object) -> MagicMock:
        captured["headers"] = kwargs.get("headers")
        return MagicMock(status_code=200)

    settings = _settings(
        alert_delivery_enabled=True,
        alert_webhook_enabled=True,
        alert_webhook_url="https://example.com/hook",
        alert_webhook_secret="secret",
    )
    provider = WebhookAlertDeliveryProvider(settings, http_post=mock_post)
    provider.deliver(
        AlertDeliveryPayload(
            alert_id="a",
            organization_id=str(ORG_ID),
            alert_type="setup_signal_detected",
            severity="info",
            message="test",
            idempotency_key="stable-key",
        )
    )
    assert "X-AlphaTrade-Signature" in captured["headers"]


def test_webhook_unsigned_when_secret_missing() -> None:
    captured: dict = {}

    def mock_post(url: str, **kwargs: object) -> MagicMock:
        captured["headers"] = kwargs.get("headers")
        return MagicMock(status_code=200)

    settings = _settings(
        alert_delivery_enabled=True,
        alert_webhook_enabled=True,
        alert_webhook_url="https://example.com/hook",
        alert_webhook_secret="",
    )
    provider = WebhookAlertDeliveryProvider(settings, http_post=mock_post)
    provider.deliver(
        AlertDeliveryPayload(
            alert_id="a",
            organization_id=str(ORG_ID),
            alert_type="setup_signal_detected",
            severity="info",
            message="test",
        )
    )
    assert "X-AlphaTrade-Signature" not in captured["headers"]


def test_no_real_trading_path_added(slice46_client: TestClient) -> None:
    health = slice46_client.get("/health")
    assert health.json()["real_trading_enabled"] is False


def test_notification_tool_get(slice46_db: sessionmaker[Session]) -> None:
    with slice46_db() as session:
        registry = build_default_registry(_settings(), db_session=session)
        tool = registry.get("notification_preferences_tool")
        assert tool is not None
        out = tool.execute(
            {
                "organization_id": str(ORG_ID),
                "user_id": str(USER_ID),
                "action": "get",
            }
        )
        assert out.success
        assert out.result is not None
        assert "preferences" in out.result
