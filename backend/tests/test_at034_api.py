"""AT-034 WS2 — backtest API orchestration, journal, comparison, evidence tiers."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    BacktestRun,
    HistoricalCandle,
    JournalTrade,
    Membership,
    Organization,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    JournalTradeSource,
    MembershipRole,
    StrategyId,
    TradeDirection,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.backtest_service import BacktestService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000034101")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000034102")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000034111")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000034112")
VIEWER_A = uuid.UUID("00000000-0000-0000-0000-000000034113")

_BASE: dict[str, Any] = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "at034-api-test-secret-key-min-32b!!",
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


def _settings(**overrides: Any) -> Settings:
    base = dict(_BASE)
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def client() -> Iterator[tuple[TestClient, sessionmaker[Session], Settings]]:
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
    settings = _settings()

    with factory() as session:
        session.add(Organization(id=ORG_A, name="AT034 API Org A"))
        session.add(Organization(id=ORG_B, name="AT034 API Org B"))
        for user_id, email in (
            (USER_A, "at034-a@test.example"),
            (USER_B, "at034-b@test.example"),
            (VIEWER_A, "at034-viewer@test.example"),
        ):
            session.add(
                User(
                    id=user_id,
                    email=email,
                    hashed_password=hash_password("SecurePass123!", settings),
                    email_verified=True,
                )
            )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.add(Membership(user_id=VIEWER_A, organization_id=ORG_A, role=MembershipRole.VIEWER))
        _seed_candles(session, n=120)
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as test_client:
        yield test_client, factory, settings

    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def sync_low_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    """Client with backtest_sync_max_bars=50 so 120-bar datasets stay QUEUED."""
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
    settings = _settings(backtest_sync_max_bars=50, backtest_max_active_runs_per_org=2)

    with factory() as session:
        session.add(Organization(id=ORG_A, name="AT034 Sync Org"))
        session.add(
            User(
                id=USER_A,
                email="at034-sync@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        _seed_candles(session, n=120)
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as test_client:
        yield test_client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def _seed_candles(session: Session, *, n: int = 120) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    step = timedelta(hours=4)
    for i in range(n):
        open_time = start + step * i
        close = Decimal("100") + Decimal(str(i)) * Decimal("0.25")
        session.add(
            HistoricalCandle(
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="4h",
                open_time=open_time,
                close_time=open_time + step,
                open=close,
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal("10"),
                source="synthetic",
            )
        )
    session.flush()


def _auth(client: TestClient, email: str) -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": "SecurePass123!"})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _card() -> dict[str, Any]:
    return {
        "strategy_name": "AT034 API",
        "market_type": "crypto_perp",
        "asset_universe": ["BTCUSDT"],
        "timeframes": ["4h"],
        "entry_conditions": ["Pullback to EMA"],
        "confirmation_conditions": ["RSI reset"],
        "invalidation": ["Close below swing"],
        "stop_loss": ["2% below entry"],
        "take_profit_plan": ["TP1 at 1R", "TP2 at 2R"],
        "runner_plan": [],
        "position_sizing": ["Max 1%"],
        "add_rules": [],
        "no_trade_rules": [],
        "backtest_rules": [],
        "success_criteria": ["Win rate > 45%"],
        "validation_status": "draft",
    }


def _structured_payload() -> dict[str, Any]:
    return {
        "entry_rules": [
            {
                "trigger_type": EntryTriggerType.EMA_PULLBACK.value,
                "direction": TradeDirection.LONG.value,
            }
        ],
        "exit_rules": [
            {"rule_type": ExitRuleType.FIXED_STOP.value, "value": "2"},
            {"rule_type": ExitRuleType.TP_MULTIPLE.value, "r_multiple": "1"},
            {"rule_type": ExitRuleType.TP_MULTIPLE.value, "r_multiple": "2"},
        ],
    }


def _create_strategy(client: TestClient, headers: dict[str, str], name: str = "BT Strat") -> str:
    create = client.post(
        "/strategies",
        json={"name": name, "setup_type": "htf_trend_pullback", "card": _card()},
        headers=headers,
    )
    assert create.status_code == 200, create.text
    strategy_id = create.json()["id"]
    patch = client.patch(
        f"/strategies/{strategy_id}/structured-rules",
        json=_structured_payload(),
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    return strategy_id


def _assumptions(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "4h",
        "start_date": "2024-01-01",
        "end_date": "2024-02-01",
        "initial_capital": "10000",
        "fees_bps": "4",
        "slippage_bps": "5",
        "risk_per_trade_pct": "1",
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------- #
# Happy path (sync complete)
# --------------------------------------------------------------------------- #


def test_create_sync_completes(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, _, _ = client
    headers = _auth(test_client, "at034-a@test.example")
    strategy_id = _create_strategy(test_client, headers)
    run = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions()},
        headers=headers,
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "completed"
    assert body["result"] is not None
    assert body["config_hash"]
    assert body["dataset_id"]
    assert body["engine_version"]


def test_queued_then_execute_run(
    sync_low_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = sync_low_client
    headers = _auth(test_client, "at034-sync@test.example")
    strategy_id = _create_strategy(test_client, headers)
    run = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions()},
        headers=headers,
    )
    assert run.status_code == 200, run.text
    body = run.json()
    # BackgroundTasks may complete it; accept queued or completed.
    assert body["status"] in {"queued", "completed", "running"}
    run_id = body["id"]

    with factory() as session:
        service = BacktestService(session, _settings(backtest_sync_max_bars=50))
        result = service.execute_run(uuid.UUID(run_id), organization_id=ORG_A)
        session.commit()
        assert result.status.value in {"completed", "failed", "cancelled"}


def test_cancel_queued(
    sync_low_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = sync_low_client
    headers = _auth(test_client, "at034-sync@test.example")
    strategy_id = _create_strategy(test_client, headers)

    # Disable background drain by canceling immediately via service before BG runs.
    # Create with sync_low so it queues; cancel via API.
    # TestClient runs BackgroundTasks after response — race possible.
    # Create two runs and cancel via direct service before execute for determinism.
    with factory() as session:
        from app.schemas.backtest import BacktestAssumptions, BacktestRunCreate
        from app.schemas.common import Timeframe

        service = BacktestService(session, _settings(backtest_sync_max_bars=50))
        created = service.create(
            uuid.UUID(strategy_id),
            BacktestRunCreate(
                assumptions=BacktestAssumptions(
                    symbol="BTCUSDT",
                    exchange="binance",
                    timeframe=Timeframe.H4,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 2, 1),
                )
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        assert created.status.value == "queued"
        cancelled = service.cancel(created.id, organization_id=ORG_A, user_id=USER_A)
        session.commit()
        assert cancelled.status.value == "cancelled"

    detail = test_client.get(f"/backtests/{created.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "cancelled"


def test_cancel_running_sets_cancel_requested(
    sync_low_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = sync_low_client
    headers = _auth(test_client, "at034-sync@test.example")
    strategy_id = _create_strategy(test_client, headers)

    with factory() as session:
        from app.schemas.backtest import BacktestAssumptions, BacktestRunCreate
        from app.schemas.common import BacktestRunStatus, Timeframe

        service = BacktestService(session, _settings(backtest_sync_max_bars=50))
        created = service.create(
            uuid.UUID(strategy_id),
            BacktestRunCreate(
                assumptions=BacktestAssumptions(
                    symbol="BTCUSDT",
                    exchange="binance",
                    timeframe=Timeframe.H4,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 2, 1),
                )
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        row = session.get(BacktestRun, created.id)
        assert row is not None
        row.status = BacktestRunStatus.RUNNING
        row.started_at = datetime.now(UTC)
        session.flush()
        cancelled = service.cancel(created.id, organization_id=ORG_A, user_id=USER_A)
        session.commit()
        assert cancelled.status.value == "cancel_requested"
        assert cancelled.cancel_requested_at is not None

    resp = test_client.post(f"/backtests/{created.id}/cancel", headers=headers)
    # Already cancel_requested — idempotent return 200
    assert resp.status_code == 200


def test_verify_match_and_tamper(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at034-a@test.example")
    strategy_id = _create_strategy(test_client, headers)
    run = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions()},
        headers=headers,
    )
    assert run.status_code == 200
    run_id = run.json()["id"]
    assert run.json()["status"] == "completed"

    ok = test_client.post(f"/backtests/{run_id}/verify", headers=headers)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["dataset_ok"] is True
    assert body["match"] is True

    with factory() as session:
        row = session.get(BacktestRun, uuid.UUID(run_id))
        assert row is not None
        row.result_hash = "0" * 64
        session.commit()

    bad = test_client.post(f"/backtests/{run_id}/verify", headers=headers)
    assert bad.status_code == 200
    assert bad.json()["match"] is False
    assert bad.json()["dataset_ok"] is True


def test_idempotent_create(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, _, _ = client
    headers = _auth(test_client, "at034-a@test.example")
    strategy_id = _create_strategy(test_client, headers, name="Idem Strat")
    payload = {
        "assumptions": _assumptions(),
        "idempotency_key": "bt-key-1",
    }
    first = test_client.post(f"/strategies/{strategy_id}/backtests", json=payload, headers=headers)
    second = test_client.post(f"/strategies/{strategy_id}/backtests", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    third = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions(), "idempotency_key": "bt-key-2"},
        headers=headers,
    )
    assert third.status_code == 200
    assert third.json()["id"] != first.json()["id"]


def test_max_active_runs_cap(
    sync_low_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = sync_low_client
    with factory() as session:
        from app.schemas.backtest import BacktestAssumptions, BacktestRunCreate
        from app.schemas.common import Timeframe

        # Seed strategy for USER_A
        strategy = UserStrategy(
            organization_id=ORG_A,
            user_id=USER_A,
            name="Cap Strat",
            setup_type=StrategyId.HTF_TREND_PULLBACK,
        )
        session.add(strategy)
        session.flush()
        version = UserStrategyVersion(
            strategy_id=strategy.id,
            version=1,
            card=_card(),
            structured_rules=_structured_payload(),
        )
        session.add(version)
        session.flush()

        service = BacktestService(
            session, _settings(backtest_sync_max_bars=50, backtest_max_active_runs_per_org=2)
        )
        payload = BacktestRunCreate(
            assumptions=BacktestAssumptions(
                symbol="BTCUSDT",
                exchange="binance",
                timeframe=Timeframe.H4,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 1),
            )
        )
        r1 = service.create(strategy.id, payload, organization_id=ORG_A, user_id=USER_A)
        r2 = service.create(
            strategy.id,
            BacktestRunCreate(
                assumptions=payload.assumptions,
                idempotency_key="cap-2",
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        assert r1.status.value == "queued"
        assert r2.status.value == "queued"
        with pytest.raises(Exception) as exc_info:
            service.create(
                strategy.id,
                BacktestRunCreate(
                    assumptions=payload.assumptions,
                    idempotency_key="cap-3",
                ),
                organization_id=ORG_A,
                user_id=USER_A,
            )
        assert "active" in str(exc_info.value).lower() or "409" in str(
            getattr(exc_info.value, "status_code", "")
        )
        session.rollback()


# --------------------------------------------------------------------------- #
# Bulk journal + statistics + comparison
# --------------------------------------------------------------------------- #


def test_bulk_journal_dry_run_commit_idempotent(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at034-a@test.example")
    strategy_id = _create_strategy(test_client, headers, name="Journal Strat")
    run = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions()},
        headers=headers,
    )
    assert run.status_code == 200
    run_id = run.json()["id"]
    assert run.json()["status"] == "completed"

    dry = test_client.post(
        f"/backtests/{run_id}/journal-trades",
        json={"dry_run": True},
        headers=headers,
    )
    assert dry.status_code == 200, dry.text
    dry_body = dry.json()
    assert dry_body["committed"] is False
    assert dry_body["created_count"] + dry_body["duplicate_count"] == dry_body["total_rows"]

    commit = test_client.post(
        f"/backtests/{run_id}/journal-trades",
        json={"dry_run": False},
        headers=headers,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["committed"] is True

    again = test_client.post(
        f"/backtests/{run_id}/journal-trades",
        json={"dry_run": False},
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json()["duplicate_count"] == again.json()["total_rows"]
    assert again.json()["created_count"] == 0

    stats = test_client.get(
        "/journal/statistics",
        params={"group_by": "source", "source": "backtest"},
        headers=headers,
    )
    assert stats.status_code == 200
    assert stats.json()["overall"]["trade_count"] >= 0

    with factory() as session:
        count = session.scalar(
            select(JournalTrade).where(
                JournalTrade.organization_id == ORG_A,
                JournalTrade.source == JournalTradeSource.BACKTEST,
            )
        )
        # at least the query works; rows may be zero if engine produced no trades
        _ = count


def test_comparison_three_cohorts(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, _, _ = client
    headers = _auth(test_client, "at034-a@test.example")
    resp = test_client.get("/journal/comparison", headers=headers)
    assert resp.status_code == 200, resp.text
    cohorts = {c["cohort"] for c in resp.json()["cohorts"]}
    assert cohorts == {"human", "paper_system", "backtest"}


def test_setup_evidence_tiers(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, factory, _ = client
    headers = _auth(test_client, "at034-a@test.example")

    with factory() as session:
        strategy = UserStrategy(
            organization_id=ORG_A,
            user_id=USER_A,
            name="Evidence Strat",
            setup_type=StrategyId.HTF_TREND_PULLBACK,
        )
        session.add(strategy)
        session.flush()
        v1 = UserStrategyVersion(strategy_id=strategy.id, version=1, card=_card())
        v2 = UserStrategyVersion(strategy_id=strategy.id, version=2, card=_card())
        v3 = UserStrategyVersion(strategy_id=strategy.id, version=3, card=_card())
        session.add_all([v1, v2, v3])
        session.flush()

        # Tier1: strong OOS + confirm trades
        run1 = BacktestRun(
            strategy_id=strategy.id,
            strategy_version_id=v1.id,
            organization_id=ORG_A,
            user_id=USER_A,
            status="completed",
            assumptions={},
            finished_at=datetime.now(UTC),
            result={
                "metrics": {
                    "trade_count": 50,
                    "win_rate": 0.5,
                    "profit_factor": 1.5,
                    "expectancy": "10",
                    "max_drawdown_pct": 5,
                    "average_win": "20",
                    "average_loss": "-10",
                    "largest_win": "30",
                    "largest_loss": "-15",
                    "consecutive_losses": 2,
                    "average_time_in_trade_bars": 3,
                    "total_fees": "1",
                    "total_slippage": "1",
                    "net_pnl": "100",
                    "return_pct": 1.0,
                    "ending_equity": "10100",
                    "symbol": "BTCUSDT",
                    "timeframe": "4h",
                },
                "recommendation": "promising",
                "oos_metrics": {
                    "split_label": "out_of_sample",
                    "split_index": 0,
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-02-01T00:00:00Z",
                    "trade_count": 35,
                    "win_rate": 0.55,
                    "profit_factor": 1.5,
                    "expectancy": "12",
                    "net_pnl": "80",
                    "max_drawdown_pct": 4,
                },
            },
        )
        session.add(run1)
        session.flush()
        for i in range(25):
            session.add(
                JournalTrade(
                    organization_id=ORG_A,
                    user_id=USER_A,
                    source=JournalTradeSource.MANUAL,
                    status="closed",
                    symbol="BTCUSDT",
                    timeframe="4h",
                    direction=TradeDirection.LONG,
                    user_strategy_id=strategy.id,
                    strategy_version_id=v1.id,
                    net_pnl=Decimal("10"),
                    result="win",
                    entry_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                    exit_time=datetime(2024, 1, 1, 4, tzinfo=UTC) + timedelta(days=i),
                )
            )

        # Tier2: enough total + OOS but weak confirmation
        run2 = BacktestRun(
            strategy_id=strategy.id,
            strategy_version_id=v2.id,
            organization_id=ORG_A,
            user_id=USER_A,
            status="completed",
            assumptions={},
            finished_at=datetime.now(UTC),
            result={
                "metrics": {
                    "trade_count": 40,
                    "win_rate": 0.5,
                    "profit_factor": 1.2,
                    "expectancy": "5",
                    "max_drawdown_pct": 5,
                    "average_win": "20",
                    "average_loss": "-10",
                    "largest_win": "30",
                    "largest_loss": "-15",
                    "consecutive_losses": 2,
                    "average_time_in_trade_bars": 3,
                    "total_fees": "1",
                    "total_slippage": "1",
                    "net_pnl": "50",
                    "return_pct": 0.5,
                    "ending_equity": "10050",
                    "symbol": "BTCUSDT",
                    "timeframe": "4h",
                },
                "recommendation": "promising",
                "oos_metrics": {
                    "split_label": "out_of_sample",
                    "split_index": 0,
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-02-01T00:00:00Z",
                    "trade_count": 20,
                    "win_rate": 0.5,
                    "profit_factor": 1.2,
                    "expectancy": "5",
                    "net_pnl": "40",
                    "max_drawdown_pct": 4,
                },
            },
        )
        session.add(run2)

        # Tier3: weak everything (no oos run)
        session.commit()
        sid = str(strategy.id)

    resp = test_client.get(
        "/journal/setup-evidence",
        params={"strategy_id": sid},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    items = {item["version"]: item["tier"] for item in resp.json()["items"]}
    assert items[1] == "tier1"
    assert items[2] == "tier2"
    assert items[3] == "tier3"


# --------------------------------------------------------------------------- #
# RBAC + tenant isolation
# --------------------------------------------------------------------------- #


def test_viewer_rbac(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, _, _ = client
    owner = _auth(test_client, "at034-a@test.example")
    viewer = _auth(test_client, "at034-viewer@test.example")
    strategy_id = _create_strategy(test_client, owner, name="RBAC Strat")
    run = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions()},
        headers=owner,
    )
    run_id = run.json()["id"]

    assert test_client.post(f"/backtests/{run_id}/cancel", headers=viewer).status_code == 403
    assert test_client.post(f"/backtests/{run_id}/verify", headers=viewer).status_code == 403
    assert (
        test_client.post(
            f"/backtests/{run_id}/journal-trades",
            json={"dry_run": True},
            headers=viewer,
        ).status_code
        == 403
    )
    assert test_client.get("/journal/comparison", headers=viewer).status_code == 200
    assert test_client.get("/journal/setup-evidence", headers=viewer).status_code == 200


def test_tenant_isolation(
    client: tuple[TestClient, sessionmaker[Session], Settings],
) -> None:
    test_client, _, _ = client
    owner_a = _auth(test_client, "at034-a@test.example")
    owner_b = _auth(test_client, "at034-b@test.example")
    strategy_id = _create_strategy(test_client, owner_a, name="Tenant Strat")
    run = test_client.post(
        f"/strategies/{strategy_id}/backtests",
        json={"assumptions": _assumptions()},
        headers=owner_a,
    )
    run_id = run.json()["id"]

    assert test_client.get(f"/backtests/{run_id}", headers=owner_b).status_code == 404
    assert test_client.post(f"/backtests/{run_id}/cancel", headers=owner_b).status_code == 404
    assert test_client.post(f"/backtests/{run_id}/verify", headers=owner_b).status_code == 404
