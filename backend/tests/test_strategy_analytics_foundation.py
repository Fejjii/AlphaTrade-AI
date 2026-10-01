"""Focused record-only analytics: arithmetic, lineage, coverage and read isolation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.db.base import Base
from app.db.models import JournalTrade, Organization, User, UserStrategy, UserStrategyVersion
from app.db.strategy_brain import BrainSetupEventRow, BrainSetupRow
from app.schemas.common import (
    JournalTradeSource,
    JournalTradeStatus,
    MarketRegime,
    StrategyId,
    TradeDirection,
    TradeResult,
)
from app.schemas.journal_statistics import JournalStatsFilters, JournalStatsGroupBy
from app.schemas.strategy_analytics import (
    NestedMaturityStage,
    StrategyAnalyticsFilters,
    StrategyAnalyticsReport,
)
from app.schemas.strategy_analytics import (
    StrategyAnalyticsDimension as Dimension,
)
from app.services.journal_statistics_service import JournalStatisticsService
from app.services.strategy_analytics_service import StrategyAnalyticsService

ORG = UUID(int=101)
OTHER_ORG = UUID(int=102)
USER = UUID(int=201)
OTHER_USER = UUID(int=202)
START = datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Organization(id=ORG, name="Analytics"),
                Organization(id=OTHER_ORG, name="Other tenant"),
                User(id=USER, email="analytics@example.test", hashed_password="unused"),
                User(id=OTHER_USER, email="other@example.test", hashed_password="unused"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def trade(db: Session, **values: object) -> JournalTrade:
    fields = {
        "id": uuid4(),
        "organization_id": ORG,
        "user_id": USER,
        "source": JournalTradeSource.PAPER_EXECUTION,
        "status": JournalTradeStatus.CLOSED,
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": TradeDirection.LONG,
        "market_regime": MarketRegime.UNKNOWN,
        "result": TradeResult.OPEN,
        "net_pnl": Decimal("100"),
        "gross_pnl": Decimal("110"),
        "fees": Decimal("3"),
        "funding": Decimal("2"),
        "slippage": Decimal("5"),
        "planned_risk_amount": Decimal("10"),
        "mae_amount": Decimal("4"),
        "mfe_amount": Decimal("20"),
        "entry_time": START,
        "exit_time": START + timedelta(hours=1),
        **values,
    }
    row = JournalTrade(**fields)
    db.add(row)
    db.commit()
    return row


def strategy(db: Session, **values: object) -> tuple[UserStrategy, UserStrategyVersion]:
    row = UserStrategy(
        id=uuid4(),
        organization_id=ORG,
        user_id=USER,
        name=str(uuid4()),
        setup_type=StrategyId.NESTED_CONTINUATION,
        **values,
    )
    version = UserStrategyVersion(
        id=uuid4(),
        strategy_id=row.id,
        version=1,
        card={},
        content_hash="a" * 64,
    )
    db.add_all([row, version])
    db.commit()
    return row, version


def brain(
    db: Session,
    journal: JournalTrade,
    *,
    stage: str | None = "N2",
    owner: UserStrategy | None = None,
    version: UserStrategyVersion | None = None,
    organization_id: UUID = ORG,
    opened_event: bool = True,
) -> BrainSetupRow:
    if owner is None:
        owner, version = strategy(db)
    assert version is not None
    row = BrainSetupRow(
        id=uuid4(),
        organization_id=organization_id,
        strategy_id=owner.id,
        strategy_version_id=version.id,
        symbol=journal.symbol,
        state="COMPLETED",
        observed_at=START,
        expires_at=START + timedelta(days=1),
        journal_trade_id=journal.id,
        payload={"stage": "N4_PLUS"},
    )
    db.add(row)
    if opened_event:
        db.add(
            BrainSetupEventRow(
                id=uuid4(),
                organization_id=organization_id,
                setup_id=row.id,
                kind="paper_trade_opened",
                occurred_at=START,
                payload={"journal_trade_id": str(journal.id), "stage": stage},
            )
        )
    db.commit()
    return row


def report(db: Session, **values: object) -> StrategyAnalyticsReport:
    return StrategyAnalyticsService(db).compute(organization_id=ORG, user_id=USER, **values)


def test_golden_metrics_reuse_journal_semantics_and_include_pnl_missing_duration(
    db: Session,
) -> None:
    trade(db)
    trade(
        db,
        net_pnl=Decimal("-50"),
        gross_pnl=Decimal("-40"),
        planned_risk_amount=Decimal("20"),
        exit_time=START + timedelta(hours=2),
    )
    trade(db, net_pnl=Decimal("0"), gross_pnl=Decimal("10"), exit_time=START + timedelta(hours=3))
    trade(
        db,
        net_pnl=None,
        gross_pnl=None,
        planned_risk_amount=None,
        mae_amount=None,
        mfe_amount=None,
        exit_time=START + timedelta(hours=4),
    )
    result = report(db, min_sample_size=3)
    metrics = result.overall
    canonical = (
        JournalStatisticsService(db, max_rows=10_000)
        .compute(
            organization_id=ORG,
            user_id=USER,
            filters=JournalStatsFilters(),
            group_by=JournalStatsGroupBy.OVERALL,
        )
        .overall
    )
    assert metrics.model_dump(include=set(type(canonical).model_fields)) == (canonical.model_dump())
    assert metrics.trade_count == 4
    assert metrics.win_rate == 0.5  # breakeven and undecided excluded
    assert metrics.expectancy == Decimal("50") / 3
    assert metrics.net_pnl_total == Decimal("50")
    assert metrics.average_r == 2.5
    assert metrics.median_r == 0
    assert metrics.profit_factor == 2
    assert metrics.maximum_drawdown == Decimal("50")
    assert metrics.average_mae_amount == Decimal("4")
    assert metrics.average_mfe_amount == Decimal("20")
    assert metrics.average_holding_period_seconds == 9000
    assert metrics.cost_reconciled_net_pnl_total == Decimal("50")
    assert metrics.cost_reconciled_expectancy == Decimal("50") / 3
    assert metrics.cost_complete_sample_count == 3
    assert metrics.metric_samples["win_rate"].sample_count == 2
    assert metrics.metric_samples["win_rate"].insufficient_history
    assert not metrics.insufficient_history
    assert metrics.metric_samples["average_holding_period_seconds"].sample_count == 4
    assert metrics.missing_fields["net_pnl"] == 1
    assert metrics.missing_fields["result"] == 1
    assert StrategyAnalyticsReport.model_validate_json(result.model_dump_json()) == result


def test_empty_sample_keeps_unavailable_metrics_null(db: Session) -> None:
    result = report(db)
    metrics = result.overall
    assert metrics.trade_count == result.scanned_trade_count == 0
    assert result.buckets == []
    assert metrics.net_pnl_total is None
    assert metrics.win_rate is None
    assert metrics.expectancy is None
    assert metrics.average_r is metrics.median_r is None
    assert metrics.maximum_drawdown is metrics.average_holding_period_seconds is None
    assert metrics.average_mae_amount is metrics.average_mfe_amount is None
    assert metrics.cost_reconciled_net_pnl_total is None
    assert metrics.insufficient_history
    assert all(
        sample.sample_count == 0 and not sample.available
        for sample in metrics.metric_samples.values()
    )


def test_populated_trade_does_not_impute_absent_fields_from_labels_or_creation_time(
    db: Session,
) -> None:
    trade(
        db,
        fees=None,
        funding=None,
        slippage=None,
        planned_risk_amount=None,
        mae_amount=None,
        mfe_amount=None,
        entry_time=None,
        exit_time=None,
        strategy_label="Nested N3 BTCUSDT 15m",
        created_at=START,
    )
    metrics = report(db).overall
    assert metrics.trade_count == 1 and metrics.net_pnl_total == 100
    assert metrics.fees_total is metrics.funding_total is metrics.slippage_total is None
    assert metrics.average_r is metrics.median_r is None
    assert metrics.average_mae_amount is metrics.average_mfe_amount is None
    assert metrics.maximum_drawdown is metrics.average_holding_period_seconds is None
    assert metrics.cost_reconciled_net_pnl_total is None
    for field in (
        "fees",
        "funding",
        "slippage",
        "entry_time",
        "exit_time",
        "planned_risk_amount",
        "mae_amount",
        "mfe_amount",
        "strategy",
        "strategy_version",
        "nested_maturity_stage",
    ):
        assert metrics.missing_fields[field] == 1


def test_partial_history_excludes_unknown_risk_and_bad_timing_without_estimation(
    db: Session,
) -> None:
    trade(
        db,
        id=UUID(int=1001),
        planned_risk_amount=Decimal("0"),
        exit_time=None,
        fees=None,
        funding=None,
        slippage=None,
        mae_amount=None,
        mfe_amount=None,
    )
    trade(
        db,
        id=UUID(int=1002),
        net_pnl=Decimal("-40"),
        planned_risk_amount=Decimal("-2"),
        entry_time=START + timedelta(hours=2),
        exit_time=START + timedelta(hours=1),
    )
    trade(
        db,
        id=UUID(int=1003),
        planned_risk_amount=None,
        entry_time=None,
        exit_time=START + timedelta(hours=3),
    )
    metrics = report(db).overall
    assert metrics.average_r is metrics.median_r is None
    assert metrics.average_holding_period_seconds is None
    assert metrics.maximum_drawdown == Decimal("40")  # missing exit cannot be ordered
    assert metrics.metric_samples["maximum_drawdown"].sample_count == 2
    assert metrics.invalid_fields == {"planned_risk_amount": 2, "holding_period": 1}
    assert metrics.missing_fields["fees"] == metrics.missing_fields["slippage"] == 1
    assert metrics.missing_fields["entry_time"] == metrics.missing_fields["exit_time"] == 1
    assert metrics.missing_fields["planned_risk_amount"] == 1
    assert metrics.average_mae_amount == Decimal("4")
    assert metrics.metric_samples["average_mae_amount"].sample_count == 2


@pytest.mark.parametrize(
    "pnls,win_rate,factor",
    [
        (["10", "20"], 1, None),
        (["0", "0"], None, None),
        (["-10", "-20"], 0, 0),
    ],
)
def test_undefined_ratios_have_actual_sample_counts(
    db: Session, pnls: list[str], win_rate: float | None, factor: float | None
) -> None:
    for pnl in pnls:
        trade(db, net_pnl=Decimal(pnl), gross_pnl=Decimal(pnl) + 10)
    metrics = report(db).overall
    assert metrics.win_rate == win_rate
    assert metrics.profit_factor == factor
    assert metrics.metric_samples["profit_factor"].sample_count == 2
    assert metrics.metric_samples["profit_factor"].available == (factor is not None)


def test_costs_use_recorded_net_once_and_expose_inconsistent_or_missing_inputs(db: Session) -> None:
    trade(
        db,
        net_pnl=Decimal("0"),
        gross_pnl=Decimal("0"),
        fees=Decimal("0"),
        funding=Decimal("0"),
        slippage=Decimal("0"),
    )
    trade(db, net_pnl=Decimal("100"), gross_pnl=Decimal("999"))
    trade(db, net_pnl=None, gross_pnl=Decimal("50"))
    trade(db, fees=None, slippage=None)
    metrics = report(db).overall
    assert metrics.net_pnl_total == 200  # never recomputed or costs subtracted twice
    assert metrics.cost_reconciled_net_pnl_total == 0  # recorded zero is available
    assert metrics.metric_samples["cost_reconciled_net_pnl_total"].sample_count == 1
    assert metrics.metric_samples["cost_reconciled_net_pnl_total"].available
    assert metrics.cost_complete_sample_count == 2
    assert metrics.cost_inconsistent_sample_count == 1
    assert metrics.missing_fields["net_pnl"] == metrics.missing_fields["fees"] == 1
    assert {warning.code for warning in metrics.analytics_warnings} >= {
        "costs_unverified",
        "costs_inconsistent",
        "missing_fields",
    }


def test_median_r_even_sample_and_close_order_drawdown(db: Session) -> None:
    trade(
        db,
        net_pnl=Decimal("-30"),
        planned_risk_amount=Decimal("10"),
        exit_time=START + timedelta(hours=3),
    )
    trade(
        db,
        net_pnl=Decimal("100"),
        planned_risk_amount=Decimal("10"),
        exit_time=START + timedelta(hours=1),
    )
    trade(
        db,
        net_pnl=Decimal("-20"),
        planned_risk_amount=Decimal("10"),
        exit_time=START + timedelta(hours=2),
    )
    trade(
        db,
        net_pnl=Decimal("40"),
        planned_risk_amount=Decimal("10"),
        exit_time=START + timedelta(hours=4),
    )
    metrics = report(db).overall
    assert metrics.median_r == 1  # median of -3, -2, 4, 10
    assert metrics.maximum_drawdown == 50  # cumulative 100, 80, 50, 90


def test_nested_attribution_uses_first_open_event_not_mutable_or_later_stage(db: Session) -> None:
    journal = trade(db)
    setup = brain(db, journal)
    db.add_all(
        [
            BrainSetupEventRow(
                id=uuid4(),
                organization_id=ORG,
                setup_id=setup.id,
                kind="paper_trade_opened",
                occurred_at=START + timedelta(minutes=5),
                payload={"journal_trade_id": str(journal.id), "stage": "N3"},
            ),
            BrainSetupEventRow(
                id=uuid4(),
                organization_id=ORG,
                setup_id=setup.id,
                kind="system_observation",
                occurred_at=START - timedelta(minutes=5),
                payload={"stage": "N1"},
            ),
        ]
    )
    db.commit()
    result = report(db, group_by=tuple(Dimension))
    dimensions = result.buckets[0].dimensions
    assert dimensions[Dimension.STRATEGY] == str(setup.strategy_id)
    assert dimensions[Dimension.STRATEGY_VERSION] == str(setup.strategy_version_id)
    assert dimensions[Dimension.NESTED_MATURITY_STAGE] == "N2"
    assert dimensions[Dimension.SYMBOL] == "BTCUSDT"
    assert dimensions[Dimension.TIMEFRAME] == "15m"
    assert dimensions[Dimension.MARKET_REGIME] is None
    assert "strategy" not in result.overall.missing_fields
    assert result.overall.missing_fields["market_regime"] == 1
    selected = report(
        db,
        filters=StrategyAnalyticsFilters(
            strategy_id=setup.strategy_id,
            strategy_version_id=setup.strategy_version_id,
            nested_maturity_stage=NestedMaturityStage.N2,
        ),
    )
    assert selected.overall.trade_count == 1
    assert (
        report(
            db,
            filters=StrategyAnalyticsFilters(
                nested_maturity_stage=NestedMaturityStage.N4_PLUS,
            ),
        ).overall.trade_count
        == 0
    )


@pytest.mark.parametrize("stage,opened_event", [(None, True), ("N99", True), ("N2", False)])
def test_missing_or_invalid_stage_stays_unassigned(
    db: Session, stage: str | None, opened_event: bool
) -> None:
    brain(db, trade(db), stage=stage, opened_event=opened_event)
    result = report(db, group_by=(Dimension.NESTED_MATURITY_STAGE,))
    assert result.buckets[0].dimensions[Dimension.NESTED_MATURITY_STAGE] is None
    assert result.overall.missing_fields["nested_maturity_stage"] == 1


def test_all_nested_stages_form_distinct_recorded_buckets(db: Session) -> None:
    owner, version = strategy(db)
    for stage in NestedMaturityStage:
        brain(db, trade(db), stage=stage, owner=owner, version=version)
    result = report(db, group_by=(Dimension.NESTED_MATURITY_STAGE,))
    assert result.total_buckets == 4 and result.overall.trade_count == 4
    assert {bucket.dimensions[Dimension.NESTED_MATURITY_STAGE] for bucket in result.buckets} == {
        "N1",
        "N2",
        "N3",
        "N4_PLUS",
    }
    assert all(
        bucket.metrics.trade_count == 1 and bucket.metrics.insufficient_history
        for bucket in result.buckets
    )


def test_stage_snapshot_missing_or_wrong_journal_reference_is_not_replaced(db: Session) -> None:
    journal = trade(db)
    setup = brain(db, journal, stage=None)
    db.add_all(
        [
            BrainSetupEventRow(
                id=uuid4(),
                organization_id=ORG,
                setup_id=setup.id,
                kind="paper_trade_opened",
                occurred_at=START - timedelta(minutes=1),
                payload={"journal_trade_id": str(uuid4()), "stage": "N1"},
            ),
            BrainSetupEventRow(
                id=uuid4(),
                organization_id=ORG,
                setup_id=setup.id,
                kind="paper_trade_opened",
                occurred_at=START + timedelta(minutes=1),
                payload={"journal_trade_id": str(journal.id), "stage": "N3"},
            ),
        ]
    )
    db.commit()
    result = report(db, group_by=(Dimension.NESTED_MATURITY_STAGE,))
    assert result.buckets[0].dimensions[Dimension.NESTED_MATURITY_STAGE] is None


def test_ambiguous_brain_links_do_not_duplicate_outcomes_or_impute_attribution(db: Session) -> None:
    journal = trade(db)
    brain(db, journal)
    brain(db, journal)
    result = report(db, group_by=(Dimension.STRATEGY, Dimension.NESTED_MATURITY_STAGE))
    assert result.overall.trade_count == 1
    assert result.overall.net_pnl_total == 100
    assert set(result.buckets[0].dimensions.values()) == {None}
    assert "ambiguous_brain_link" in {w.code for w in result.overall.analytics_warnings}


def test_conflicting_brain_link_retains_explicit_journal_ids_without_stage(db: Session) -> None:
    owner, version = strategy(db)
    journal = trade(db, user_strategy_id=owner.id, strategy_version_id=version.id)
    brain(db, journal)
    result = report(db, group_by=(Dimension.STRATEGY_VERSION, Dimension.NESTED_MATURITY_STAGE))
    assert result.buckets[0].dimensions[Dimension.STRATEGY_VERSION] == str(version.id)
    assert result.buckets[0].dimensions[Dimension.NESTED_MATURITY_STAGE] is None
    assert "conflicting_brain_link" in {w.code for w in result.overall.analytics_warnings}


def test_tenant_and_user_scope_apply_to_journal_brain_and_event_reads(db: Session) -> None:
    trade(db, organization_id=OTHER_ORG, net_pnl=Decimal("-999"))
    trade(db, user_id=OTHER_USER, net_pnl=Decimal("-888"))
    journal = trade(db)
    brain(db, journal, organization_id=OTHER_ORG)
    result = report(db, group_by=(Dimension.STRATEGY, Dimension.NESTED_MATURITY_STAGE))
    assert result.overall.trade_count == 1
    assert result.overall.net_pnl_total == 100
    assert set(result.buckets[0].dimensions.values()) == {None}
    # A same-tenant Brain row cannot use another user's strategy for attribution.
    owner, version = strategy(db)
    owner.user_id = OTHER_USER
    db.commit()
    setup = brain(db, journal, owner=owner, version=version)
    assert report(db).overall.missing_fields["strategy"] == 1
    # A cross-tenant event cannot enrich an otherwise valid same-tenant setup.
    owner.user_id = USER
    db.query(BrainSetupEventRow).filter_by(setup_id=setup.id).delete()
    db.add(
        BrainSetupEventRow(
            id=uuid4(),
            organization_id=OTHER_ORG,
            setup_id=setup.id,
            kind="paper_trade_opened",
            occurred_at=START,
            payload={"journal_trade_id": str(journal.id), "stage": "N1"},
        )
    )
    db.commit()
    assert report(db).overall.missing_fields["nested_maturity_stage"] == 1


def test_segmentation_versions_missing_dimensions_and_pagination(db: Session) -> None:
    owner, first = strategy(db)
    second = UserStrategyVersion(
        id=uuid4(),
        strategy_id=owner.id,
        version=2,
        card={},
        content_hash="b" * 64,
    )
    db.add(second)
    db.commit()
    trade(
        db,
        user_strategy_id=owner.id,
        strategy_version_id=first.id,
        market_regime=MarketRegime.TRENDING_UP,
    )
    trade(
        db,
        user_strategy_id=owner.id,
        strategy_version_id=second.id,
        symbol="ETHUSDT",
        timeframe="1h",
        net_pnl=Decimal("-10"),
    )
    trade(db, symbol="", timeframe="")
    result = report(db, group_by=(Dimension.STRATEGY_VERSION,), limit=2)
    assert result.total_buckets == 3
    assert result.buckets[0].dimensions[Dimension.STRATEGY_VERSION] is None
    assert sum(bucket.metrics.trade_count for bucket in result.buckets) == 2
    page = report(db, group_by=(Dimension.STRATEGY_VERSION,), limit=2, offset=2)
    assert len(page.buckets) == 1
    assert page.overall.trade_count == 3
    all_dimensions = report(db, group_by=tuple(Dimension))
    assert sum(bucket.metrics.trade_count for bucket in all_dimensions.buckets) == 3
    assert all_dimensions.overall.missing_fields["symbol"] == 1
    assert all_dimensions.overall.missing_fields["timeframe"] == 1
    by_strategy = report(db, group_by=(Dimension.STRATEGY,))
    assert (
        next(
            bucket.metrics.trade_count
            for bucket in by_strategy.buckets
            if bucket.dimensions[Dimension.STRATEGY] == str(owner.id)
        )
        == 2
    )


def test_closed_trade_filters_keep_existing_inclusive_date_semantics(db: Session) -> None:
    trade(db)
    trade(db, status=JournalTradeStatus.OPEN)
    trade(db, status=JournalTradeStatus.PLANNED)
    trade(db, status=JournalTradeStatus.CANCELLED)
    trade(db, source=JournalTradeSource.IMPORTED)
    trade(db, symbol="ETHUSDT")
    trade(db, exit_time=START + timedelta(hours=2))
    filters = StrategyAnalyticsFilters(
        source=JournalTradeSource.PAPER_EXECUTION,
        symbol="BTCUSDT",
        timeframe="15m",
        market_regime=MarketRegime.UNKNOWN,
        date_from=START + timedelta(hours=1),
        date_to=START + timedelta(hours=1),
    )
    assert report(db, filters=filters).overall.trade_count == 1


def test_capped_scan_warns_all_buckets_and_does_not_claim_later_filter_matches(db: Session) -> None:
    trade(db, id=UUID(int=3001), symbol="BTCUSDT")
    trade(db, id=UUID(int=3002), symbol="ETHUSDT")
    later = trade(db, id=UUID(int=3003), exit_time=START + timedelta(hours=2))
    setup = brain(db, later)
    service = StrategyAnalyticsService(db, max_rows=2)
    result = service.compute(
        organization_id=ORG,
        user_id=USER,
        group_by=(Dimension.SYMBOL,),
        limit=1,
    )
    assert result.scanned_trade_count == result.overall.trade_count == 2
    assert result.truncated and result.total_buckets == 2
    assert result.buckets[0].dimensions[Dimension.SYMBOL] == "BTCUSDT"
    assert all(
        "result_truncated" in {w.code for w in metrics.warnings}
        for metrics in [result.overall, result.buckets[0].metrics]
    )
    selected = service.compute(
        organization_id=ORG,
        user_id=USER,
        filters=StrategyAnalyticsFilters(strategy_id=setup.strategy_id),
    )
    assert selected.truncated and selected.scanned_trade_count == 2
    assert selected.overall.trade_count == 0 and selected.overall.insufficient_history


def test_read_only_service_does_not_autoflush_pending_mutations(db: Session) -> None:
    journal = trade(db)
    brain(db, journal)
    journal.notes = "pending caller change"
    pending = Organization(id=uuid4(), name="pending caller insert")
    db.add(pending)
    engine = db.get_bind()
    statements: list[str] = []

    def capture(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = report(db)
        assert result.overall.trade_count == 1
        assert statements and all(
            statement.lstrip().upper().startswith("SELECT") for statement in statements
        )
        assert pending in db.new and journal in db.dirty
        with db.no_autoflush:
            assert (
                db.scalar(select(JournalTrade.notes).where(JournalTrade.id == journal.id)) is None
            )
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.mark.parametrize(
    "options",
    [
        {"min_sample_size": 0},
        {"limit": 0},
        {"offset": -1},
        {"group_by": ()},
        {"group_by": (Dimension.SYMBOL, Dimension.SYMBOL)},
        {"group_by": ("invented",)},
    ],
)
def test_invalid_report_options_rejected(db: Session, options: dict[str, object]) -> None:
    with pytest.raises(ValidationAppError):
        report(db, **options)


def test_invalid_cap_and_date_filters_rejected(db: Session) -> None:
    with pytest.raises(ValidationAppError):
        StrategyAnalyticsService(db, max_rows=0)
    with pytest.raises(ValidationError):
        StrategyAnalyticsFilters(date_from=START + timedelta(days=1), date_to=START)
    with pytest.raises(ValidationError):
        StrategyAnalyticsFilters(date_from=datetime(2026, 9, 1))
