"""Tests for persisted market watcher scan summaries (Slice 75)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import ExecutionMode, Settings, get_settings
from app.db.base import Base
from app.db.models import MarketWatcherScanRecord, Membership, Organization, User
from app.db.session import get_session
from app.main import create_app
from app.providers.market_data import MockMarketDataProvider
from app.schemas.market_watcher import (
    CREATE_IN_APP_ALERTS_CONFIRM_PHRASE,
    SCAN_CONFIRM_PHRASE,
    MarketWatcherScanRequest,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.market_data_service import MarketDataService
from app.services.market_watcher_service import MarketWatcherService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000007501")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000007502")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000007503")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000007504")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "slice75-scanner-secret-minimum-32",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
}


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def slice75_db() -> Iterator[sessionmaker[Session]]:
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
    settings = Settings(**_BASE)
    with factory() as session:
        org_a = Organization(id=ORG_A, name="Slice75 Org A")
        org_b = Organization(id=ORG_B, name="Slice75 Org B")
        owner_a = User(
            id=USER_A,
            email="owner75a@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        owner_b = User(
            id=USER_B,
            email="owner75b@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        session.add(org_a)
        session.add(org_b)
        session.add(owner_a)
        session.add(owner_b)
        session.flush()
        from app.schemas.common import MembershipRole

        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _client(slice75_db: sessionmaker[Session], email: str = "owner75a@test.example") -> TestClient:
    settings = Settings(**_BASE)
    get_settings.cache_clear()
    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with slice75_db() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    client = TestClient(app)
    login = client.post("/auth/login", json={"email": email, "password": "TestPassword123!"})
    token = login.json()["tokens"]["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _market_data_service() -> MarketDataService:
    return MarketDataService(MockMarketDataProvider())


def _scan(client: TestClient, *, dry_run: bool = True) -> dict:
    body: dict = {
        "confirm": SCAN_CONFIRM_PHRASE,
        "symbols": ["BTCUSDT"],
        "timeframes": ["15m"],
        "dry_run": dry_run,
    }
    if not dry_run:
        body["create_in_app_alerts_confirm"] = CREATE_IN_APP_ALERTS_CONFIRM_PHRASE
    resp = client.post("/market-watcher/scan", json=body)
    assert resp.status_code == 200
    return resp.json()


def test_summary_reads_persisted_scan_state(slice75_db: sessionmaker[Session]) -> None:
    client = _client(slice75_db)
    before = client.get("/market-watcher/summary").json()
    assert before["last_scan_at"] is None
    assert before["last_scan_conditions_found"] == []

    scan = _scan(client, dry_run=True)
    assert scan["status"] == "ok"
    assert scan["alerts_created"] == 0

    after = client.get("/market-watcher/summary").json()
    assert after["last_scan_at"] is not None
    assert after["last_scan_status"] == "ok"
    assert after["last_scan_dry_run"] is True
    assert after["last_scan_candidate_count"] >= 0
    if scan["candidates"]:
        assert set(after["last_scan_conditions_found"]) == {
            c["condition"] for c in scan["candidates"]
        }


def test_persisted_state_survives_new_service_instance(slice75_db: sessionmaker[Session]) -> None:
    with slice75_db() as session:
        settings = Settings(**_BASE)
        provider = MockMarketDataProvider()
        market_data = MarketDataService(provider)
        svc = MarketWatcherService(session, settings, market_data=market_data)
        result = svc.scan(
            organization_id=ORG_A,
            user_id=USER_A,
            request=MarketWatcherScanRequest(
                confirm=SCAN_CONFIRM_PHRASE,
                symbols=["BTCUSDT"],
                timeframes=["15m"],
                dry_run=True,
            ),
        )
        session.commit()
        assert result.status == "ok"

    with slice75_db() as session:
        settings = Settings(**_BASE)
        svc2 = MarketWatcherService(session, settings, market_data=_market_data_service())
        summary = svc2.get_summary(organization_id=ORG_A, user_id=USER_A)
        assert summary.last_scan_at is not None
        assert summary.last_scan_status == "ok"
        assert summary.last_scan_dry_run is True


def test_scan_writes_persisted_state_on_non_dry_run(slice75_db: sessionmaker[Session]) -> None:
    client = _client(slice75_db)
    _scan(client, dry_run=False)
    with slice75_db() as session:
        row = session.scalar(
            select(MarketWatcherScanRecord)
            .where(MarketWatcherScanRecord.organization_id == ORG_A)
            .order_by(MarketWatcherScanRecord.scanned_at.desc())
        )
        assert row is not None
        assert row.dry_run is False


def test_scan_writes_blocked_status(slice75_db: sessionmaker[Session]) -> None:
    client = _client(slice75_db)
    resp = client.post(
        "/market-watcher/scan",
        json={
            "confirm": "WRONG",
            "symbols": ["BTCUSDT"],
            "timeframes": ["15m"],
            "dry_run": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"
    summary = client.get("/market-watcher/summary").json()
    assert summary["last_scan_status"] == "blocked"
    assert summary["last_scan_error"] == "confirmation_required"


def test_scan_writes_degraded_status(slice75_db: sessionmaker[Session]) -> None:
    provider = MagicMock()
    provider.name = "mock"
    provider.get_ohlcv.side_effect = RuntimeError("provider unavailable")
    with slice75_db() as session:
        settings = Settings(**_BASE)
        svc = MarketWatcherService(session, settings, market_data=MarketDataService(provider))
        result = svc.scan(
            organization_id=ORG_A,
            user_id=USER_A,
            request=MarketWatcherScanRequest(
                confirm=SCAN_CONFIRM_PHRASE,
                symbols=["BTCUSDT"],
                timeframes=["15m"],
                dry_run=True,
            ),
        )
        session.commit()
        assert result.status == "degraded"
        summary = svc.get_summary(organization_id=ORG_A, user_id=USER_A)
        assert summary.last_scan_status == "degraded"


def test_tenant_isolation(slice75_db: sessionmaker[Session]) -> None:
    client_a = _client(slice75_db, email="owner75a@test.example")
    client_b = _client(slice75_db, email="owner75b@test.example")
    _scan(client_a, dry_run=True)
    summary_b = client_b.get("/market-watcher/summary").json()
    assert summary_b["last_scan_at"] is None


def test_recent_scans_endpoint(slice75_db: sessionmaker[Session]) -> None:
    client = _client(slice75_db)
    _scan(client, dry_run=True)
    _scan(client, dry_run=True)
    recent = client.get("/market-watcher/scans/recent?limit=5").json()
    assert recent["total"] >= 2
    assert len(recent["items"]) >= 2
    assert "conditions_found" in recent["items"][0]


def test_errors_are_redacted(slice75_db: sessionmaker[Session]) -> None:
    with slice75_db() as session:
        settings = Settings(**_BASE)
        svc = MarketWatcherService(session, settings, market_data=_market_data_service())
        now = datetime.now(UTC)
        result = svc._blocked_result(
            now,
            decisions=["blocked"],
            error="postgresql+psycopg://secret:password@host/db",
            dry_run=True,
        )
        svc._persist_scan(ORG_A, result, symbols=["BTCUSDT"], timeframes=["15m"])
        session.commit()
        row = session.scalar(select(MarketWatcherScanRecord))
        assert row is not None
        assert "password" not in (row.error or "").lower()
        assert "secret" not in (row.error or "").lower()


def test_no_secrets_in_summary_or_history(slice75_db: sessionmaker[Session]) -> None:
    client = _client(slice75_db)
    _scan(client, dry_run=True)
    summary_raw = client.get("/market-watcher/summary").text
    recent_raw = client.get("/market-watcher/scans/recent").text
    for raw in (summary_raw, recent_raw):
        assert "TELEGRAM_BOT_TOKEN" not in raw
        assert "postgresql+psycopg://" not in raw


def test_no_telegram_service_called(slice75_db: sessionmaker[Session]) -> None:
    with slice75_db() as session:
        settings = Settings(**_BASE)
        svc = MarketWatcherService(session, settings, market_data=_market_data_service())
        with patch(
            "app.services.telegram_alert_delivery_service.TelegramAlertDeliveryService.deliver_alert"
        ) as deliver:
            svc.scan(
                organization_id=ORG_A,
                user_id=USER_A,
                request=MarketWatcherScanRequest(
                    confirm=SCAN_CONFIRM_PHRASE,
                    create_in_app_alerts_confirm=CREATE_IN_APP_ALERTS_CONFIRM_PHRASE,
                    symbols=["BTCUSDT"],
                    timeframes=["15m"],
                    dry_run=False,
                ),
            )
        deliver.assert_not_called()


def test_no_execution_service_called(slice75_db: sessionmaker[Session]) -> None:
    with slice75_db() as session:
        settings = Settings(**_BASE)
        svc = MarketWatcherService(session, settings, market_data=_market_data_service())
        with patch(
            "app.services.execution_service.ExecutionService.place_paper_order",
        ) as place_order:
            svc.scan(
                organization_id=ORG_A,
                user_id=USER_A,
                request=MarketWatcherScanRequest(
                    confirm=SCAN_CONFIRM_PHRASE,
                    symbols=["BTCUSDT"],
                    timeframes=["15m"],
                    dry_run=True,
                ),
            )
        place_order.assert_not_called()


def test_real_trading_blocks_and_persists_blocked(slice75_db: sessionmaker[Session]) -> None:
    settings = Settings(
        **{
            **_BASE,
            "execution_mode": ExecutionMode.TRADE.value,
            "enable_real_trading": True,
        }
    )
    get_settings.cache_clear()
    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with slice75_db() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        json={"email": "owner75a@test.example", "password": "TestPassword123!"},
    )
    client.headers.update({"Authorization": f"Bearer {login.json()['tokens']['access_token']}"})
    resp = client.post(
        "/market-watcher/scan",
        json={
            "confirm": SCAN_CONFIRM_PHRASE,
            "symbols": ["BTCUSDT"],
            "timeframes": ["15m"],
            "dry_run": True,
        },
    )
    assert resp.json()["status"] == "blocked"
    summary = client.get("/market-watcher/summary").json()
    assert summary["last_scan_status"] == "blocked"
    with slice75_db() as session:
        count = session.scalar(select(func.count()).select_from(MarketWatcherScanRecord))
        assert count == 1
