"""AT-034 WS1 — deterministic backtest engine v2, hashing, datasets."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    BacktestDataset,
    BacktestRun,
    HistoricalCandle,
    Membership,
    Organization,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.models import User as UserModel
from app.providers.market_data import MockMarketDataProvider
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestSplitConfig,
    BacktestSplitMode,
)
from app.schemas.common import (
    BacktestSplitLabel,
    EntryTriggerType,
    ExitRuleType,
    MembershipRole,
    StrategyId,
    Timeframe,
    TradeDirection,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import EntryRuleBlock, ExitRuleBlock, StructuredRules
from app.security.passwords import hash_password
from app.services.backtest_dataset_service import BacktestDatasetService
from app.services.backtest_engine_service import ENGINE_VERSION, BacktestEngineService
from app.services.backtest_hashing import canonical_json_hash, dataset_content_hash
from app.services.historical_candle_service import HistoricalCandleService
from app.services.strategy_rule_adapter import ParsedStrategyRules

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000034")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000035")


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
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
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="at034-test-secret-key-min-32b",
        rate_limit_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
    )
    with factory() as session:
        session.add(Organization(id=ORG_ID, name="AT034 Org"))
        session.add(
            UserModel(
                id=USER_ID,
                email="at034@test.example",
                hashed_password=hash_password("TestPassword123!", settings),
                email_verified=True,
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.commit()
    yield factory


def _settings(**overrides: Any) -> Settings:
    base = {
        "environment": "local",
        "log_json": False,
        "execution_mode": "paper",
        "enable_real_trading": False,
        "database_url": "sqlite+pysqlite:///:memory:",
        "jwt_secret": "at034-test-secret-key-min-32b",
        "rate_limit_use_redis": False,
        "provider_mode": "mock",
        "market_data_provider": "mock",
    }
    base.update(overrides)
    return Settings(**base)


def _card() -> StrategyCard:
    return StrategyCard.model_validate(
        {
            "strategy_name": "AT034",
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
    )


def _structured(
    *,
    direction: TradeDirection,
    trigger: EntryTriggerType,
    use_runner: bool = False,
) -> StructuredRules:
    exits = [
        ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1")),
        ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("2")),
    ]
    if use_runner:
        exits.append(ExitRuleBlock(rule_type=ExitRuleType.RUNNER_STRUCTURE_BREAK))
    return StructuredRules(
        entry_rules=[
            EntryRuleBlock(trigger_type=trigger, direction=direction),
        ],
        exit_rules=exits,
    )


def _make_candles(
    session: Session,
    *,
    n: int,
    start: datetime | None = None,
    price_fn: Any | None = None,
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    timeframe: str = "4h",
    gap_after: int | None = None,
) -> list[HistoricalCandle]:
    start = start or datetime(2024, 1, 1, tzinfo=UTC)
    step = timedelta(hours=4)
    rows: list[HistoricalCandle] = []
    for i in range(n):
        open_time = start + step * i
        if gap_after is not None and i > gap_after:
            open_time = start + step * (i + 2)  # skip 2 bars once
        if price_fn is None:
            close = Decimal("100") + Decimal(str(i)) * Decimal("0.1")
        else:
            close = Decimal(str(price_fn(i)))
        high = close + Decimal("1")
        low = close - Decimal("1")
        row = HistoricalCandle(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            open_time=open_time,
            close_time=open_time + step,
            open=close,
            high=high,
            low=low,
            close=close,
            volume=Decimal("10"),
            source="synthetic",
            is_stale=(i % 17 == 0),
        )
        rows.append(row)
        session.add(row)
    session.flush()
    return rows


def _seed_strategy(session: Session) -> tuple[UserStrategy, UserStrategyVersion]:
    strategy = UserStrategy(
        organization_id=ORG_ID,
        user_id=USER_ID,
        name="AT034 Strategy",
        setup_type=StrategyId.HTF_TREND_PULLBACK,
    )
    session.add(strategy)
    session.flush()
    version = UserStrategyVersion(
        strategy_id=strategy.id,
        version=1,
        card=_card().model_dump(mode="json"),
    )
    session.add(version)
    session.flush()
    return strategy, version


def _run_model(
    session: Session,
    strategy: UserStrategy,
    version: UserStrategyVersion,
    assumptions: BacktestAssumptions,
) -> BacktestRun:
    run = BacktestRun(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        organization_id=ORG_ID,
        user_id=USER_ID,
        status="running",
        assumptions=assumptions.model_dump(mode="json"),
    )
    session.add(run)
    session.flush()
    return run


def _engine(session: Session, settings: Settings | None = None) -> BacktestEngineService:
    settings = settings or _settings()
    provider = MockMarketDataProvider()
    candles = HistoricalCandleService(session, provider, settings)
    return BacktestEngineService(session, candles, settings)


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #


def test_canonical_json_hash_stable() -> None:
    payload = {
        "b": Decimal("1.50"),
        "a": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        "e": TradeDirection.LONG,
        "nested": {"z": Decimal("0.1"), "y": 2},
    }
    h1 = canonical_json_hash(payload)
    h2 = canonical_json_hash(
        {
            "nested": {"y": 2, "z": Decimal("0.1")},
            "e": TradeDirection.LONG,
            "a": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            "b": Decimal("1.50"),
        }
    )
    assert h1 == h2
    assert len(h1) == 64


def test_dataset_content_hash_stable(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        rows = _make_candles(session, n=5)
        h1 = dataset_content_hash(rows)
        h2 = dataset_content_hash(rows)
        assert h1 == h2
        rows[0].close = Decimal("999")
        assert dataset_content_hash(rows) != h1


# --------------------------------------------------------------------------- #
# Dataset service
# --------------------------------------------------------------------------- #


def test_dataset_gap_count_and_hash_reuse(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        settings = _settings()
        provider = MockMarketDataProvider()
        candle_svc = HistoricalCandleService(session, provider, settings)
        # Pre-seed enough candles so ensure_candles does not re-ingest a different set.
        _make_candles(session, n=60, gap_after=10)
        ds_svc = BacktestDatasetService(session, candle_svc)
        ds1, rows1, _ = ds_svc.ensure_dataset(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
        )
        assert ds1.gap_count >= 1
        assert ds1.candle_count == len(rows1)
        assert ds1.stale_count >= 1
        assert "synthetic" in ds1.source_counts

        ds2, rows2, _ = ds_svc.ensure_dataset(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
        )
        assert ds2.id == ds1.id
        assert ds2.dataset_hash == ds1.dataset_hash
        assert len(rows2) == len(rows1)
        count = session.scalar(select(BacktestDataset))
        assert count is not None
        # Only one immutable row
        assert len(list(session.scalars(select(BacktestDataset)).all())) == 1


# --------------------------------------------------------------------------- #
# Engine — determinism & long semantics
# --------------------------------------------------------------------------- #


def test_identical_inputs_same_result_hash(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        _make_candles(session, n=80)
        strategy, version = _seed_strategy(session)
        assumptions = BacktestAssumptions(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 20),
            fees_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        engine = _engine(session)
        structured = _structured(
            direction=TradeDirection.LONG,
            trigger=EntryTriggerType.EMA_PULLBACK,
        )
        run1 = _run_model(session, strategy, version, assumptions)
        r1 = engine.run(
            run=run1,
            card=_card(),
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            structured_rules=structured,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 20),
        )
        run2 = _run_model(session, strategy, version, assumptions)
        r2 = engine.run(
            run=run2,
            card=_card(),
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            structured_rules=structured,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 20),
        )
        assert r1.result_hash is not None
        assert r1.result_hash == r2.result_hash
        assert r1.engine_version == ENGINE_VERSION
        assert run1.result_hash == r1.result_hash


def test_long_pullback_entry_stop_math(session_factory: sessionmaker[Session]) -> None:
    """Long pullback_ema stop = close * (1 - stop_pct) — v1 semantics."""
    with session_factory() as session:
        # Build a series that dips below EMA20 then reclaims.
        def prices(i: int) -> float:
            if i < 30:
                return 100 + i * 0.5  # uptrend so EMA rises
            if i == 30:
                return 110.0
            if i == 31:
                return 100.0  # sharp dip (prev low below ema)
            return 112.0  # reclaim above ema

        rows = _make_candles(session, n=50, price_fn=prices)
        # Ensure bar 31 dips: set lows/highs explicitly around reclaim
        for i, row in enumerate(rows):
            if i == 30:
                row.low = Decimal("100")
                row.close = Decimal("110")
                row.high = Decimal("111")
            if i == 31:
                row.low = Decimal("95")  # below EMA
                row.close = Decimal("112")
                row.high = Decimal("113")
                row.open = Decimal("100")
        session.flush()

        _strategy, _version = _seed_strategy(session)
        BacktestAssumptions(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            fees_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            max_trades=1,
        )
        engine = _engine(session)
        rules = ParsedStrategyRules(
            machine_readable=True,
            limitation=None,
            direction=TradeDirection.LONG,
            entry_mode="pullback_ema",
            stop_pct=Decimal("0.02"),
            tp_r_multiples=(Decimal("10"),),  # far TP so stop/entry inspectable
            use_runner=False,
            matched_tokens=("test",),
        )
        # Direct entry-signal unit check
        ema = engine._ema([r.close for r in rows], 20)
        signal = engine._entry_signal(rules, rows, 31, ema)
        assert signal is not None
        entry, stop, notes = signal
        assert "reclaim" in notes
        assert stop == entry * (Decimal("1") - Decimal("0.02"))


def test_short_entries_all_modes(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        engine = _engine(session)
        n = 40
        start = datetime(2024, 1, 1, tzinfo=UTC)
        rows: list[HistoricalCandle] = []
        for i in range(n):
            close = Decimal("100")
            open_time = start + timedelta(hours=4) * i
            row = HistoricalCandle(
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4),
                open=close,
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal("1"),
                source="synthetic",
            )
            rows.append(row)

        # pullback_ema SHORT: poke above EMA then reject
        for i, row in enumerate(rows):
            row.close = Decimal("100") + Decimal(str(i)) * Decimal("0.01")
        ema = engine._ema([r.close for r in rows], 20)
        idx = 30
        rows[idx - 1].high = ema[idx - 1] + Decimal("5")
        rows[idx - 1].close = ema[idx - 1] + Decimal("1")
        rows[idx].high = ema[idx] + Decimal("5")
        rows[idx].close = ema[idx] - Decimal("1")
        rules = ParsedStrategyRules(
            machine_readable=True,
            limitation=None,
            direction=TradeDirection.SHORT,
            entry_mode="pullback_ema",
            stop_pct=Decimal("0.02"),
            tp_r_multiples=(Decimal("1"),),
            use_runner=False,
            matched_tokens=("t",),
        )
        sig = engine._entry_signal(rules, rows, idx, ema)
        assert sig is not None
        entry, stop, _ = sig
        assert stop == entry * (Decimal("1") + Decimal("0.02"))

        # breakout SHORT
        rules2 = ParsedStrategyRules(
            machine_readable=True,
            limitation=None,
            direction=TradeDirection.SHORT,
            entry_mode="breakout",
            stop_pct=Decimal("0.02"),
            tp_r_multiples=(Decimal("1"),),
            use_runner=False,
            matched_tokens=("t",),
        )
        lookback = rows[max(0, idx - 20) : idx]
        prior_low = min(r.low for r in lookback)
        rows[idx].close = prior_low - Decimal("1")
        rows[idx].low = prior_low - Decimal("2")
        sig2 = engine._entry_signal(rules2, rows, idx, ema)
        assert sig2 is not None
        entry2, stop2, note2 = sig2
        assert "below 20-bar low" in note2
        assert stop2 == entry2 * (Decimal("1") + Decimal("0.02"))

        # liquidity_sweep SHORT
        rules3 = ParsedStrategyRules(
            machine_readable=True,
            limitation=None,
            direction=TradeDirection.SHORT,
            entry_mode="liquidity_sweep",
            stop_pct=Decimal("0.02"),
            tp_r_multiples=(Decimal("1"),),
            use_runner=False,
            matched_tokens=("t",),
        )
        look15 = rows[max(0, idx - 15) : idx]
        swing_high = max(r.high for r in look15)
        rows[idx].high = swing_high + Decimal("3")
        rows[idx].close = swing_high - Decimal("1")
        sig3 = engine._entry_signal(rules3, rows, idx, ema)
        assert sig3 is not None
        entry3, stop3, note3 = sig3
        assert "sweep high" in note3
        assert stop3 == rows[idx].high * (Decimal("1") + Decimal("0.02") / Decimal("2"))
        assert entry3 == rows[idx].close


# --------------------------------------------------------------------------- #
# Funding & excursions
# --------------------------------------------------------------------------- #


def test_funding_long_pays_short_receives() -> None:
    from app.services.backtest_engine_service import _OpenTrade

    long_trade = _OpenTrade(
        direction=TradeDirection.LONG,
        entry_time=datetime(2024, 1, 1, tzinfo=UTC),
        entry_price=Decimal("100"),
        stop_loss=Decimal("98"),
        size=Decimal("1"),
        risk_per_unit=Decimal("2"),
        tp_levels=[],
        tp_hit=0,
        use_runner=False,
        rule_notes="",
        entry_fees=Decimal("0"),
        entry_slippage=Decimal("0"),
        entry_idx=0,
    )
    short_trade = _OpenTrade(
        direction=TradeDirection.SHORT,
        entry_time=datetime(2024, 1, 1, tzinfo=UTC),
        entry_price=Decimal("100"),
        stop_loss=Decimal("102"),
        size=Decimal("1"),
        risk_per_unit=Decimal("2"),
        tp_levels=[],
        tp_hit=0,
        use_runner=False,
        rule_notes="",
        entry_fees=Decimal("0"),
        entry_slippage=Decimal("0"),
        entry_idx=0,
    )
    # H4 = 14400s; fraction of 8h = 14400/28800 = 0.5
    # cost = 100 * 1 * (10/10000) * 0.5 = 0.05
    BacktestEngineService._accrue_funding(long_trade, Decimal("10"), Decimal("14400"))
    BacktestEngineService._accrue_funding(short_trade, Decimal("10"), Decimal("14400"))
    assert long_trade.funding_cost == Decimal("0.05")
    assert short_trade.funding_cost == Decimal("-0.05")

    zero_trade = _OpenTrade(
        direction=TradeDirection.LONG,
        entry_time=datetime(2024, 1, 1, tzinfo=UTC),
        entry_price=Decimal("100"),
        stop_loss=Decimal("98"),
        size=Decimal("1"),
        risk_per_unit=Decimal("2"),
        tp_levels=[],
        tp_hit=0,
        use_runner=False,
        rule_notes="",
        entry_fees=Decimal("0"),
        entry_slippage=Decimal("0"),
        entry_idx=0,
    )
    BacktestEngineService._accrue_funding(zero_trade, Decimal("0"), Decimal("14400"))
    assert zero_trade.funding_cost == Decimal("0")


def test_excursion_math_long_and_short() -> None:
    from app.services.backtest_engine_service import _OpenTrade

    long_trade = _OpenTrade(
        direction=TradeDirection.LONG,
        entry_time=datetime(2024, 1, 1, tzinfo=UTC),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        size=Decimal("2"),
        risk_per_unit=Decimal("5"),
        tp_levels=[Decimal("110")],
        tp_hit=0,
        use_runner=False,
        rule_notes="",
        entry_fees=Decimal("0"),
        entry_slippage=Decimal("0"),
        entry_idx=0,
        mfe_price=Decimal("100"),
        mae_price=Decimal("100"),
    )
    bar_up = HistoricalCandle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="4h",
        open_time=datetime(2024, 1, 1, tzinfo=UTC),
        close_time=datetime(2024, 1, 1, 4, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("97"),
        close=Decimal("105"),
        volume=Decimal("1"),
        source="t",
    )
    BacktestEngineService._update_excursions(long_trade, bar_up)
    assert long_trade.mfe_price == Decimal("110")
    assert long_trade.mae_price == Decimal("97")

    engine = BacktestEngineService.__new__(BacktestEngineService)
    record, _ = BacktestEngineService._build_trade_record(
        engine,
        long_trade,
        exit_time=bar_up.close_time,
        exit_price=Decimal("105"),
        exit_reason="end_of_data",
        tp_status="none",
        fee_rate=Decimal("0"),
        slip_rate=Decimal("0"),
        split_label=BacktestSplitLabel.IN_SAMPLE,
        split_index=0,
        sequence=0,
    )
    assert record.mfe_amount == (Decimal("110") - Decimal("100")) * Decimal("2")
    assert record.mae_amount == (Decimal("97") - Decimal("100")) * Decimal("2")
    assert record.available_profit == record.mfe_amount
    assert record.capture_pct is not None

    short_trade = _OpenTrade(
        direction=TradeDirection.SHORT,
        entry_time=datetime(2024, 1, 1, tzinfo=UTC),
        entry_price=Decimal("100"),
        stop_loss=Decimal("105"),
        size=Decimal("2"),
        risk_per_unit=Decimal("5"),
        tp_levels=[Decimal("90")],
        tp_hit=0,
        use_runner=False,
        rule_notes="",
        entry_fees=Decimal("0"),
        entry_slippage=Decimal("0"),
        entry_idx=0,
        mfe_price=Decimal("100"),
        mae_price=Decimal("100"),
    )
    bar_down = HistoricalCandle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="4h",
        open_time=datetime(2024, 1, 1, tzinfo=UTC),
        close_time=datetime(2024, 1, 1, 4, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("103"),
        low=Decimal("90"),
        close=Decimal("95"),
        volume=Decimal("1"),
        source="t",
    )
    BacktestEngineService._update_excursions(short_trade, bar_down)
    assert short_trade.mfe_price == Decimal("90")
    assert short_trade.mae_price == Decimal("103")
    record_s, _ = BacktestEngineService._build_trade_record(
        engine,
        short_trade,
        exit_time=bar_down.close_time,
        exit_price=Decimal("95"),
        exit_reason="end_of_data",
        tp_status="none",
        fee_rate=Decimal("0"),
        slip_rate=Decimal("0"),
        split_label=BacktestSplitLabel.IN_SAMPLE,
        split_index=0,
        sequence=0,
    )
    assert record_s.mfe_amount == (Decimal("100") - Decimal("90")) * Decimal("2")
    assert record_s.mae_amount == (Decimal("100") - Decimal("103")) * Decimal("2")


# --------------------------------------------------------------------------- #
# Splits, cancel, max bars
# --------------------------------------------------------------------------- #


def test_holdout_and_rolling_splits(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        _make_candles(session, n=120)
        strategy, version = _seed_strategy(session)
        engine = _engine(session)
        structured = _structured(
            direction=TradeDirection.LONG,
            trigger=EntryTriggerType.BREAKOUT,
        )

        holdout = BacktestAssumptions(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
            fees_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            split_config=BacktestSplitConfig(mode=BacktestSplitMode.HOLDOUT, oos_fraction=0.3),
        )
        run_h = _run_model(session, strategy, version, holdout)
        result_h = engine.run(
            run=run_h,
            card=_card(),
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            structured_rules=structured,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
        )
        assert result_h.split_metrics is not None
        labels = {(m.split_label, m.split_index) for m in result_h.split_metrics}
        assert (BacktestSplitLabel.IN_SAMPLE, 0) in labels
        assert (BacktestSplitLabel.OUT_OF_SAMPLE, 1) in labels
        for t in result_h.trades:
            assert t.sequence is not None
            assert t.split_label in (
                BacktestSplitLabel.IN_SAMPLE,
                BacktestSplitLabel.OUT_OF_SAMPLE,
            )
        if any(t.split_label == BacktestSplitLabel.OUT_OF_SAMPLE for t in result_h.trades):
            assert result_h.oos_metrics is not None
            assert result_h.oos_metrics.split_label == BacktestSplitLabel.OUT_OF_SAMPLE

        rolling = BacktestAssumptions(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
            fees_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            split_config=BacktestSplitConfig(
                mode=BacktestSplitMode.ROLLING,
                oos_fraction=0.3,
                window_bars=100,
                step_bars=50,
            ),
        )
        run_r = _run_model(session, strategy, version, rolling)
        result_r = engine.run(
            run=run_r,
            card=_card(),
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            structured_rules=structured,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
        )
        assert result_r.split_metrics is not None
        # Independent segments: both IS and OOS labels present when windows fit
        assert any(m.split_label == BacktestSplitLabel.IN_SAMPLE for m in result_r.split_metrics)


def test_cancellation_flags_result(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        _make_candles(session, n=80)
        strategy, version = _seed_strategy(session)
        assumptions = BacktestAssumptions(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 20),
            split_config=BacktestSplitConfig(mode=BacktestSplitMode.HOLDOUT, oos_fraction=0.3),
        )
        engine = _engine(session)
        run = _run_model(session, strategy, version, assumptions)
        result = engine.run(
            run=run,
            card=_card(),
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            structured_rules=_structured(
                direction=TradeDirection.LONG,
                trigger=EntryTriggerType.EMA_PULLBACK,
            ),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 20),
            should_cancel=lambda: True,
        )
        assert result.cancelled is True
        assert result.processed_bars is not None


def test_backtest_max_bars_refusal(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        _make_candles(session, n=120)
        strategy, version = _seed_strategy(session)
        settings = _settings(backtest_max_bars=100)
        engine = _engine(session, settings)
        assumptions = BacktestAssumptions(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
        )
        run = _run_model(session, strategy, version, assumptions)
        result = engine.run(
            run=run,
            card=_card(),
            setup_type=StrategyId.HTF_TREND_PULLBACK,
            structured_rules=_structured(
                direction=TradeDirection.LONG,
                trigger=EntryTriggerType.EMA_PULLBACK,
            ),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
        )
        assert result.recommendation.value == "unreliable_data"
        assert any("backtest_max_bars" in lim for lim in result.limitations)
        assert result.trades == []


def test_assumptions_backward_compatible_defaults() -> None:
    legacy = {
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "4h",
        "initial_capital": "10000",
        "fees_bps": "4",
        "slippage_bps": "5",
        "funding_assumption": "neutral",
        "risk_per_trade_pct": "1",
        "sample_size": 500,
    }
    a = BacktestAssumptions.model_validate(legacy)
    assert a.funding_rate_bps_per_8h == Decimal("0")
    assert a.runner_trail_pct == Decimal("1.5")
    assert a.split_config is None
