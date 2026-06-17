"""Slice 40D — final cleanup, hardening, and validation gate tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.mutation_policy import has_explicit_confirmation, mutation_allowed
from app.core.config import Environment, Settings
from app.db.base import Base
from app.db.models import Membership, Organization, User
from app.db.session import get_session
from app.main import create_app
from app.providers.market_data import (
    MarketDataEnvelope,
    OHLCVBar,
    OHLCVData,
)
from app.providers.market_data import (
    Timeframe as ProviderTimeframe,
)
from app.schemas.common import MembershipRole, PaperAlertType, Timeframe
from app.schemas.historical_candles import HistoricalIngestRequest
from app.security.passwords import hash_password
from app.security.token_denylist import _RedisDenylist, reset_access_token_denylist
from app.services.historical_candle_service import HistoricalCandleService
from app.services.paper_alert_service import PaperAlertService
from app.tools.registry import _require_owner_scheduler_tick
from tests.test_deployment_safety import _STAGING_BASE

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000300")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000301")
TRADER_ID = uuid.UUID("00000000-0000-0000-0000-000000000302")


def _sample_card() -> dict:
    return {
        "strategy_name": "Slice40D",
        "market_type": "crypto_perp",
        "asset_universe": ["BTCUSDT"],
        "timeframes": ["15m"],
        "entry_conditions": ["Pullback to EMA cluster"],
        "confirmation_conditions": ["RSI reset above 40"],
        "invalidation": ["Close below swing low"],
        "stop_loss": ["2% below entry"],
        "take_profit_plan": ["TP1 at 1R"],
        "runner_plan": ["Trail after TP1"],
        "position_sizing": ["Max 1% account risk"],
        "add_rules": [],
        "no_trade_rules": [],
        "backtest_rules": [],
        "success_criteria": ["Win rate > 45%"],
        "validation_status": "draft",
    }


def _prepare_strategy(client: TestClient) -> str:
    create = client.post(
        "/strategies",
        json={
            "name": "Slice40D Strategy",
            "setup_type": "htf_trend_pullback",
            "card": _sample_card(),
        },
    )
    assert create.status_code == 200, create.text
    strategy_id = create.json()["id"]
    client.patch(
        f"/strategies/{strategy_id}/structured-rules",
        json={
            "primary_timeframe": "15m",
            "entry_rules": [{"trigger_type": "ema_pullback"}],
            "exit_rules": [
                {"rule_type": "fixed_stop", "value": "2"},
                {"rule_type": "tp_multiple", "r_multiple": "1"},
            ],
            "no_trade_rules": [],
        },
    )
    client.post(
        f"/strategies/{strategy_id}/backtests",
        json={
            "assumptions": {
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "exchange": "mock",
                "initial_capital": "10000",
                "fees_bps": 10,
                "slippage_bps": 5,
                "risk_per_trade_pct": 1,
            }
        },
    )
    return strategy_id


def _start_run(client: TestClient, strategy_id: str) -> str:
    resp = client.post(
        f"/strategies/{strategy_id}/paper-validation/start",
        json={"runtime_mode": "scan_only"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class _OutOfRangeProvider:
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: ProviderTimeframe,
        *,
        exchange: str = "mock",
        limit: int = 100,
    ) -> OHLCVData:
        old_ts = datetime(2020, 1, 1, tzinfo=UTC)
        bar = OHLCVBar(
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1000"),
            timestamp=old_ts,
        )
        return OHLCVData(
            envelope=MarketDataEnvelope(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                timestamp=old_ts,
                source="test",
                is_live=False,
                is_stale=False,
                stale_reason=None,
                provider_name="test",
                fallback_used=False,
            ),
            bars=[bar],
        )


class _InRangeProvider:
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: ProviderTimeframe,
        *,
        exchange: str = "mock",
        limit: int = 100,
    ) -> OHLCVData:
        ts = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        bar = OHLCVBar(
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1000"),
            timestamp=ts,
        )
        return OHLCVData(
            envelope=MarketDataEnvelope(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                timestamp=ts,
                source="test",
                is_live=False,
                is_stale=False,
                stale_reason=None,
                provider_name="test",
                fallback_used=False,
            ),
            bars=[bar],
        )


@pytest.fixture
def slice40d_db() -> Iterator[sessionmaker[Session]]:
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
        jwt_secret="slice40d-test-secret-key-min",
    )
    with factory() as session:
        org = Organization(id=ORG_ID, name="Slice40D Org")
        owner = User(
            id=USER_ID,
            email="owner40d@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        trader = User(
            id=TRADER_ID,
            email="trader40d@test.example",
            hashed_password=hash_password("TestPassword123!", settings),
            email_verified=True,
        )
        session.add(org)
        session.add(owner)
        session.add(trader)
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.add(
            Membership(user_id=TRADER_ID, organization_id=ORG_ID, role=MembershipRole.TRADER)
        )
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def slice40d_client(slice40d_db: sessionmaker[Session]) -> Iterator[TestClient]:
    settings = Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        enable_paper_scheduler=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="slice40d-test-secret-key-min",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
    )

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with slice40d_db() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "owner40d@test.example", "password": "TestPassword123!"},
        )
        token = login.json()["tokens"]["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


# --- Confirmation keyword tightening ---


def test_bare_confirmed_does_not_allow_mutation() -> None:
    msg = "I'm confirmed it is wrong, do not accept lesson X"
    assert not has_explicit_confirmation(msg)
    assert not mutation_allowed(msg)


def test_question_does_not_allow_mutation_slice40d() -> None:
    msg = "Should I accept lesson X?"
    assert not mutation_allowed(msg)


def test_i_confirm_allows_mutation() -> None:
    msg = "I confirm, accept lesson X"
    assert mutation_allowed(msg)


def test_confirm_true_allows_mutation() -> None:
    assert mutation_allowed("accept lesson X", confirm_arg=True)


# --- Candle range alignment ---


def test_out_of_range_provider_bars_not_stored(slice40d_db: sessionmaker[Session]) -> None:
    settings = Settings(
        provider_mode="live",
        market_data_enabled=True,
        database_url="sqlite+pysqlite:///:memory:",
    )
    with slice40d_db() as session:
        svc = HistoricalCandleService(session, _OutOfRangeProvider(), settings)
        result = svc.ingest(
            HistoricalIngestRequest(
                symbol="BTCUSDT",
                exchange="mock",
                timeframe=Timeframe.H4,
                start_date=date(2024, 6, 1),
                end_date=date(2024, 6, 30),
            )
        )
        assert result.candles_stored == 0
        assert any("none stored" in note.lower() for note in result.limitations)


def test_in_range_provider_bars_accepted(slice40d_db: sessionmaker[Session]) -> None:
    settings = Settings(
        provider_mode="live",
        market_data_enabled=True,
        database_url="sqlite+pysqlite:///:memory:",
    )
    with slice40d_db() as session:
        svc = HistoricalCandleService(session, _InRangeProvider(), settings)
        result = svc.ingest(
            HistoricalIngestRequest(
                symbol="BTCUSDT",
                exchange="mock",
                timeframe=Timeframe.H4,
                start_date=date(2024, 6, 1),
                end_date=date(2024, 6, 30),
            )
        )
        assert result.candles_stored == 1
        assert not any("none stored" in note.lower() for note in result.limitations)


# --- Chat scheduler tick RBAC ---


def test_trader_cannot_run_scheduler_tick(slice40d_db: sessionmaker[Session]) -> None:
    with slice40d_db() as session:
        blocked = _require_owner_scheduler_tick(
            session,
            ORG_ID,
            TRADER_ID,
            {"user_message": "I confirm scheduler tick"},
        )
        assert blocked is not None
        assert "Owner role required" in (blocked.error or "")


def test_owner_without_confirmation_blocked_scheduler_tick(
    slice40d_db: sessionmaker[Session],
) -> None:
    with slice40d_db() as session:
        blocked = _require_owner_scheduler_tick(
            session,
            ORG_ID,
            USER_ID,
            {"user_message": "run scheduler tick now"},
        )
        assert blocked is not None
        assert "Explicit confirmation required" in (blocked.error or "")


def test_owner_with_confirmation_allowed_scheduler_tick(
    slice40d_db: sessionmaker[Session],
) -> None:
    with slice40d_db() as session:
        blocked = _require_owner_scheduler_tick(
            session,
            ORG_ID,
            USER_ID,
            {"user_message": "I confirm scheduler tick", "confirm": True},
        )
        assert blocked is None


# --- Discipline analysis GET/POST ---


def test_discipline_get_returns_no_phantom_candidates(slice40d_client: TestClient) -> None:
    journal = slice40d_client.post(
        "/journal/entries",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "4h",
            "direction": "long",
            "entry_rationale": "Test entry",
            "lessons": "Held plan",
            "emotions": ["calm"],
        },
    )
    assert journal.status_code == 200
    entry_id = journal.json()["id"]
    analysis = slice40d_client.get(f"/journal/entries/{entry_id}/discipline-analysis")
    assert analysis.status_code == 200
    body = analysis.json()
    candidate_ids = body.get("lesson_candidate_ids", [])
    for cid in candidate_ids:
        listed = slice40d_client.get("/lessons/candidates")
        assert listed.status_code == 200
        persisted = {item["id"] for item in listed.json()["items"]}
        assert cid in persisted


# --- Alert dedup lifecycle ---


def test_alert_dedup_suppresses_within_cooldown(slice40d_db: sessionmaker[Session]) -> None:
    with slice40d_db() as session:
        svc = PaperAlertService(session)
        first = svc.create(
            organization_id=ORG_ID,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message="Signal A",
        )
        second = svc.create(
            organization_id=ORG_ID,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message="Signal A duplicate",
        )
        session.commit()
        assert first is not None
        assert second is None


# --- Token denylist fail-closed ---


def test_token_denylist_non_local_fails_closed_on_redis_error() -> None:
    reset_access_token_denylist()
    settings = Settings(
        **_STAGING_BASE,
        access_token_denylist_fail_closed=True,
    )
    denylist = _RedisDenylist(settings)
    with patch.object(denylist._client, "exists", side_effect=ConnectionError("redis down")):
        assert denylist.is_denied("test-jti") is True


def test_token_denylist_local_fails_open_on_redis_error() -> None:
    reset_access_token_denylist()
    settings = Settings(
        environment=Environment.LOCAL,
        access_token_denylist_fail_closed=True,
        redis_url="redis://localhost:6379/0",
        jwt_secret="local-test-secret-key-minimum-32",
        database_url="sqlite+pysqlite:///:memory:",
    )
    denylist = _RedisDenylist(settings)
    with patch.object(denylist._client, "exists", side_effect=ConnectionError("redis down")):
        assert denylist.is_denied("test-jti") is False


# --- Audit events for Slice 40 routes ---


def test_scan_tick_stop_emit_runtime_audit(slice40d_client: TestClient) -> None:
    strategy_id = _prepare_strategy(slice40d_client)
    run_id = _start_run(slice40d_client, strategy_id)
    slice40d_client.post(f"/paper-validation/{run_id}/scan")
    slice40d_client.post(f"/paper-validation/{run_id}/tick")
    slice40d_client.post(f"/paper-validation/{run_id}/stop")

    audit = slice40d_client.get("/audit/events", params={"event_type": "paper_validation_runtime"})
    assert audit.status_code == 200
    actions = {item["redacted_metadata"].get("action") for item in audit.json()["items"]}
    assert {"scan", "tick", "stop"}.issubset(actions)


def test_alert_read_emits_audit(slice40d_client: TestClient) -> None:
    strategy_id = _prepare_strategy(slice40d_client)
    run_id = _start_run(slice40d_client, strategy_id)
    slice40d_client.post(f"/paper-validation/{run_id}/scan")
    listing = slice40d_client.get("/alerts")
    items = listing.json()["items"]
    if items:
        slice40d_client.patch(f"/alerts/{items[0]['id']}/read")
        audit = slice40d_client.get(
            "/audit/events", params={"event_type": "paper_validation_runtime"}
        )
        actions = [item["redacted_metadata"].get("action") for item in audit.json()["items"]]
        assert "alert_read" in actions
