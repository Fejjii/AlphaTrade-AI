"""Tests for POST /alerts/test-telegram (Slice 69 — owner-gated, paper only)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Membership
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import MembershipRole
from app.schemas.telegram_test_alert import TELEGRAM_TEST_CONFIRM_PHRASE
from app.security.rate_limit import reset_rate_limiter
from app.services.telegram_test_alert_service import manual_test_available

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "telegram-test-alert-secret-min-32-chars",
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
def telegram_token_only_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    settings = {
        **_BASE,
        "telegram_bot_token": "bot123456789:TESTTOKEN_secret_value",
        "telegram_chat_id": "",
    }
    yield from _build_client(Settings(**settings))


@pytest.fixture
def real_trading_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    settings = {
        **_BASE,
        "execution_mode": "trade",
        "enable_real_trading": True,
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
            "organization_name": "Telegram Test Org",
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


def _set_membership_role(
    factory: sessionmaker[Session],
    *,
    user_id: uuid.UUID,
    role: MembershipRole,
) -> None:
    with factory() as session:
        membership = session.query(Membership).filter(Membership.user_id == user_id).one()
        membership.role = role
        session.commit()


def _post_test(
    client: TestClient,
    headers: dict[str, str],
    *,
    confirm: str = TELEGRAM_TEST_CONFIRM_PHRASE,
    message: str | None = None,
):
    body: dict[str, str] = {"confirm": confirm}
    if message is not None:
        body["message"] = message
    return client.post("/alerts/test-telegram", headers=headers, json=body)


def test_test_telegram_requires_owner(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    response = test_client.post(
        "/alerts/test-telegram",
        json={"confirm": TELEGRAM_TEST_CONFIRM_PHRASE},
    )
    assert response.status_code == 401


def test_test_telegram_non_owner_forbidden(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers, _, user_id = _register_owner(test_client, email="owner-forbidden@example.com")
    _set_membership_role(factory, user_id=user_id, role=MembershipRole.TRADER)
    response = _post_test(test_client, headers)
    assert response.status_code == 403


def test_test_telegram_missing_confirmation_blocked(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers, _, _ = _register_owner(test_client, email="bad-confirm@example.com")
    response = _post_test(test_client, headers, confirm="WRONG")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "blocked"
    assert body["error_code"] == "confirmation_required"


def test_test_telegram_real_trading_blocked(
    real_trading_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = real_trading_client
    headers, _, _ = _register_owner(test_client, email="real-trading@example.com")
    response = _post_test(test_client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "blocked"
    assert body["error_code"] == "real_trading_enabled"


def test_test_telegram_missing_token_skipped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers, _, _ = _register_owner(test_client, email="missing-token@example.com")
    response = _post_test(test_client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "skipped_not_configured"
    assert body["telegram_configured"] is False
    raw = json.dumps(body).lower()
    assert "bot123456789" not in raw
    assert "testtoken" not in raw


def test_test_telegram_missing_chat_skipped(
    telegram_token_only_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = telegram_token_only_client
    headers, _, _ = _register_owner(test_client, email="missing-chat@example.com")
    response = _post_test(test_client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "skipped_not_configured"
    assert body["telegram_configured"] is True
    assert body["chat_configured"] is False
    raw = json.dumps(body)
    assert "999888777" not in raw
    assert "TESTTOKEN" not in raw


def test_test_telegram_success_mocked(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = telegram_configured_client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("app.providers.alert_delivery.telegram.httpx.post", mock_post)

    headers, _, _ = _register_owner(test_client, email="success@example.com")
    response = _post_test(test_client, headers, message="Staging check")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "sent"
    assert body["paper_only"] is True
    assert body["sent_at"] is not None
    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args.kwargs
    assert "json" in call_kwargs
    raw = json.dumps(body).lower()
    assert "testtoken" not in raw
    assert "999888777" not in raw


def test_test_telegram_api_error_redacted(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = telegram_configured_client
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("app.providers.alert_delivery.telegram.httpx.post", mock_post)

    headers, _, _ = _register_owner(test_client, email="api-error@example.com")
    response = _post_test(test_client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed_redacted"
    assert body["error_code"] == "telegram_delivery_failed"
    assert body["error_message"] is not None
    raw = json.dumps(body).lower()
    assert "testtoken" not in raw
    assert "999888777" not in raw


def test_test_telegram_does_not_call_execution(
    telegram_configured_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _ = telegram_configured_client
    mock_response = MagicMock()
    mock_response.status_code = 200
    monkeypatch.setattr(
        "app.providers.alert_delivery.telegram.httpx.post",
        MagicMock(return_value=mock_response),
    )

    headers, _, _ = _register_owner(test_client, email="no-exec@example.com")
    blocked = test_client.post(
        "/execution/paper",
        headers=headers,
        json={
            "proposal_id": str(uuid.uuid4()),
            "approval_id": str(uuid.uuid4()),
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "market",
            "size": "1",
            "idempotency_key": "should-not-be-used-12345678",
        },
    )
    assert blocked.status_code in {403, 404, 422}
    _post_test(test_client, headers)


def test_routing_summary_manual_test_available(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers, _, _ = _register_owner(test_client, email="routing-manual@example.com")
    response = test_client.get("/alerts/routing/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["manual_test_available"] is True
    assert body["telegram_configured"] is False
    assert body["telegram_chat_configured"] is False
    assert body["last_test_alert_at"] is None
    assert body["last_test_alert_status"] is None


def test_routing_summary_records_last_test(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers, _, _ = _register_owner(test_client, email="routing-last@example.com")
    _post_test(test_client, headers, confirm="WRONG")
    summary = test_client.get("/alerts/routing/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["last_test_alert_status"] == "blocked"
    assert body["last_test_alert_at"] is not None


def test_manual_test_available_helper() -> None:
    settings = Settings(**_BASE)
    assert manual_test_available(settings, paper_only=True) is True
    unsafe = Settings(**{**_BASE, "execution_mode": "trade", "enable_real_trading": True})
    assert manual_test_available(unsafe, paper_only=True) is False


def test_paper_only_false_blocked(
    monkeypatch: pytest.MonkeyPatch,
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    from app.services import telegram_test_alert_service as svc

    def _fake_context(*_args: object, **_kwargs: object) -> svc.TelegramTestSafetyContext:
        return svc.TelegramTestSafetyContext(
            execution_mode=Settings(**_BASE).execution_mode,
            real_trading_enabled=False,
            paper_only=False,
            external_delivery_enabled=False,
            telegram_configured=True,
            chat_configured=True,
        )

    monkeypatch.setattr(svc, "_safety_context", _fake_context)
    headers, _, _ = _register_owner(test_client, email="paper-only-false@example.com")
    response = _post_test(test_client, headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "blocked"
    assert response.json()["error_code"] == "paper_only_required"
