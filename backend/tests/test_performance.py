"""Tests for Slice 62 performance analytics.

Covers the pure :class:`PerformanceCalculator` (golden vectors) and the
:class:`PerformanceService` end-to-end against an in-memory SQLite database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    Membership,
    Organization,
    PerformanceSnapshot,
    Position,
    StrategyPerformanceDaily,
    User,
)
from app.schemas.common import MembershipRole, PositionStatus, StrategyId, TradeDirection
from app.services.performance.calculator import PerformanceCalculator
from app.services.performance.types import TradeRecord, TradeSource
from app.services.performance_service import PerformanceService

ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a0")
USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _trade(
    pnl: str,
    *,
    symbol: str = "BTCUSDT",
    strategy_id: str | None = "htf_trend_pullback",
    timeframe: str | None = "4h",
    risk: str | None = None,
    opened: datetime | None = None,
    closed: datetime | None = None,
    source: TradeSource = TradeSource.SYSTEM,
    violation: bool = False,
) -> TradeRecord:
    return TradeRecord(
        realized_pnl=Decimal(pnl),
        symbol=symbol,
        strategy_id=strategy_id,
        timeframe=timeframe,
        risk_amount=Decimal(risk) if risk is not None else None,
        opened_at=opened,
        closed_at=closed,
        source=source,
        had_violation=violation,
    )


# --- calculator: golden vectors -------------------------------------------


def test_empty_metrics() -> None:
    metrics = PerformanceCalculator().calculate([])
    assert metrics.trade_count == 0
    assert metrics.net_pnl == Decimal("0")
    assert metrics.profit_factor is None
    assert metrics.max_drawdown_pct is None
    assert metrics.equity_curve == ()


def test_basic_win_loss_metrics() -> None:
    calc = PerformanceCalculator()
    metrics = calc.calculate([_trade("100"), _trade("-50"), _trade("50"), _trade("0")])
    assert metrics.trade_count == 4
    assert metrics.wins == 2
    assert metrics.losses == 1
    assert metrics.breakeven == 1
    assert metrics.win_rate == 0.5
    assert metrics.net_pnl == Decimal("100")
    assert metrics.gross_profit == Decimal("150")
    assert metrics.gross_loss == Decimal("-50")
    assert metrics.avg_win == Decimal("75")
    assert metrics.avg_loss == Decimal("-50")
    assert metrics.expectancy == Decimal("25")
    assert metrics.profit_factor == 3.0


def test_profit_factor_none_without_losses() -> None:
    metrics = PerformanceCalculator().calculate([_trade("10"), _trade("20")])
    assert metrics.profit_factor is None


def test_drawdown_from_equity_curve() -> None:
    # Cumulative: 100 -> 50 -> 100. Peak 100, trough 50 => DD 50 (50%).
    metrics = PerformanceCalculator().calculate([_trade("100"), _trade("-50"), _trade("50")])
    assert metrics.max_drawdown == Decimal("50")
    assert metrics.max_drawdown_pct == 0.5
    assert [p.cumulative_pnl for p in metrics.equity_curve] == [
        Decimal("100"),
        Decimal("50"),
        Decimal("100"),
    ]


def test_avg_r_multiple() -> None:
    # pnl/risk: 200/100=2.0 and -50/100=-0.5 -> mean 0.75
    metrics = PerformanceCalculator().calculate(
        [_trade("200", risk="100"), _trade("-50", risk="100")]
    )
    assert metrics.avg_r_multiple == pytest.approx(0.75)


def test_avg_duration_seconds() -> None:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    metrics = PerformanceCalculator().calculate(
        [_trade("10", opened=opened, closed=opened + timedelta(hours=2))]
    )
    assert metrics.avg_duration_seconds == 7200.0


def test_equity_curve_orders_by_close_time() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    # Provide out-of-order; calculator must sort by close time.
    later = _trade("50", closed=t0 + timedelta(days=2))
    earlier = _trade("100", closed=t0 + timedelta(days=1))
    metrics = PerformanceCalculator().calculate([later, earlier])
    assert [p.cumulative_pnl for p in metrics.equity_curve] == [
        Decimal("100"),
        Decimal("150"),
    ]


def test_breakdowns_group_correctly() -> None:
    calc = PerformanceCalculator()
    trades = [
        _trade("100", symbol="BTCUSDT", strategy_id="htf_trend_pullback"),
        _trade("-20", symbol="ETHUSDT", strategy_id="liquidity_sweep_reversal"),
        _trade("30", symbol="BTCUSDT", strategy_id="htf_trend_pullback"),
    ]
    by_symbol = {g.key: g.metrics for g in calc.breakdown_by_symbol(trades)}
    assert by_symbol["BTCUSDT"].trade_count == 2
    assert by_symbol["BTCUSDT"].net_pnl == Decimal("130")
    assert by_symbol["ETHUSDT"].net_pnl == Decimal("-20")

    by_strategy = {g.key: g.metrics for g in calc.breakdown_by_strategy(trades)}
    assert set(by_strategy) == {"htf_trend_pullback", "liquidity_sweep_reversal"}


def test_human_vs_system_breakdown() -> None:
    calc = PerformanceCalculator()
    trades = [
        _trade("100", source=TradeSource.SYSTEM),
        _trade("-40", source=TradeSource.HUMAN),
    ]
    by_source = {g.key: g.metrics for g in calc.breakdown_by_source(trades)}
    assert by_source["system"].net_pnl == Decimal("100")
    assert by_source["human"].net_pnl == Decimal("-40")


def test_unknown_group_key_for_missing_dimension() -> None:
    metrics_groups = PerformanceCalculator().breakdown_by_timeframe([_trade("10", timeframe=None)])
    assert metrics_groups[0].key == "unknown"


# --- service: end-to-end ---------------------------------------------------


@pytest.fixture
def db() -> Iterator[sessionmaker[Session]]:
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
    with factory() as session:
        session.add(Organization(id=ORG_ID, name="Perf Org"))
        session.add(User(id=USER_ID, email="perf@test.example", hashed_password="x"))
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.commit()
    yield factory
    engine.dispose()


def _closed_position(
    *,
    pnl: str,
    symbol: str = "BTCUSDT",
    strategy: StrategyId = StrategyId.HTF_TREND_PULLBACK,
    entry: str = "100",
    stop: str | None = "90",
    closed_at: datetime,
) -> Position:
    return Position(
        organization_id=ORG_ID,
        user_id=USER_ID,
        strategy_id=strategy,
        symbol=symbol,
        direction=TradeDirection.LONG,
        size=Decimal("1"),
        entry_price=Decimal(entry),
        leverage=Decimal("1"),
        stop_loss=Decimal(stop) if stop is not None else None,
        realized_pnl=Decimal(pnl),
        status=PositionStatus.CLOSED,
        opened_at=closed_at - timedelta(hours=1),
        closed_at=closed_at,
    )


def test_service_build_report_from_positions(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 2, 1, 12, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_position(pnl="-40", symbol="ETHUSDT", closed_at=day))
        # Open position must be excluded from analytics.
        session.add(
            Position(
                organization_id=ORG_ID,
                user_id=USER_ID,
                symbol="SOLUSDT",
                direction=TradeDirection.LONG,
                size=Decimal("1"),
                entry_price=Decimal("100"),
                leverage=Decimal("1"),
                realized_pnl=Decimal("0"),
                status=PositionStatus.OPEN,
                opened_at=day,
            )
        )
        session.commit()

        report = PerformanceService(session).build_report(organization_id=ORG_ID)
        assert report.account.trade_count == 2
        assert report.account.net_pnl == Decimal("60")
        symbols = {g.key for g in report.by_symbol}
        assert symbols == {"BTCUSDT", "ETHUSDT"}


def test_service_snapshot_persists_row(db: sessionmaker[Session]) -> None:
    day = datetime(2026, 2, 2, 9, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day))
        session.add(_closed_position(pnl="-30", closed_at=day + timedelta(minutes=5)))
        session.commit()

        snapshot = PerformanceService(session).snapshot_account(organization_id=ORG_ID)
        session.commit()

        assert snapshot.trade_count == 2
        assert snapshot.net_pnl == Decimal("70")
        rows = session.query(PerformanceSnapshot).all()
        assert len(rows) == 1
        assert "account" in rows[0].metrics


def test_service_rollup_strategy_daily_is_idempotent(db: sessionmaker[Session]) -> None:
    day_dt = datetime(2026, 2, 3, 10, tzinfo=UTC)
    with db() as session:
        session.add(_closed_position(pnl="100", closed_at=day_dt))
        session.add(
            _closed_position(
                pnl="-25",
                strategy=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
                closed_at=day_dt,
            )
        )
        session.commit()

        service = PerformanceService(session)
        service.rollup_strategy_daily(day=day_dt.date(), organization_id=ORG_ID)
        session.commit()
        # Running again must upsert (not duplicate).
        service.rollup_strategy_daily(day=day_dt.date(), organization_id=ORG_ID)
        session.commit()

        rows = session.query(StrategyPerformanceDaily).all()
        assert len(rows) == 2
        by_strategy = {r.strategy_id: r for r in rows}
        assert by_strategy["htf_trend_pullback"].net_pnl == Decimal("100")
        assert by_strategy["liquidity_sweep_reversal"].net_pnl == Decimal("-25")
