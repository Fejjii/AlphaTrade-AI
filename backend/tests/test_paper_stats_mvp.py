"""Paper statistics collection from a filled canonical plan through close."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ValidationAppError
from app.db.models import JournalTrade
from app.learning_attribution.adapters.rag import render_learning_facts_text
from app.learning_attribution.query import LearningQueryService
from app.paper_evaluation.journal_facts import SqlAlchemyJournalExcursionPort
from app.paper_evaluation.query import PaperEvaluationQueryService
from app.paper_evaluation.recorder import PaperEvaluationRecorder
from app.persistence.attribution_postgres import PostgresAttributionStore
from app.persistence.paper_evaluation_postgres import PostgresPaperEvaluationStore
from app.schemas.common import JournalTradeStatus, TradeDirection, TradeResult
from app.schemas.execution_protocol import ClosePaperPlanRequest
from app.schemas.journal_statistics import JournalStatsFilters, JournalStatsGroupBy
from app.services.journal_statistics_service import JournalStatisticsService
from app.services.paper_close_economics import paper_close_pnl
from app.workers.watcher_paper import watcher_measurement_is_replay
from tests.support.paper_evaluation import make_eval_command, make_eval_outcome
from tests.support.phase1_plan_fixtures import paper_settings
from tests.support.phase6_fusion import COMPILED_SETUP_ID, ORG_ID, STRATEGY_VERSION_ID, USER_ID
from tests.support.phase8_runtime import (
    EXECUTE_AT,
    build_runtime,
    canonical_execute_request,
    canonical_execution_service,
    phase8_settings,
    prepared_authorized_canonical,
)
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres
from tests.test_phase8_canonical_paper_execution import _execute

_DATABASE_URL = "postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade_test"


def test_paper_close_pnl_is_deterministic() -> None:
    win = paper_close_pnl(
        direction=TradeDirection.LONG,
        entry_price=Decimal("100000"),
        exit_price=Decimal("100010"),
        size=Decimal("1"),
        fees=Decimal("0.5"),
        funding=Decimal("0"),
        slippage=Decimal("0"),
    )
    assert win.gross_pnl == Decimal("10.00000000")
    assert win.net_pnl == Decimal("9.50000000")
    assert win.result is TradeResult.WIN

    loss = paper_close_pnl(
        direction=TradeDirection.SHORT,
        entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        size=Decimal("2"),
        fees=Decimal("1"),
        funding=Decimal("0"),
        slippage=Decimal("0"),
    )
    assert loss.gross_pnl == Decimal("-20.00000000")
    assert loss.net_pnl == Decimal("-21.00000000")
    assert loss.result is TradeResult.LOSS

    flat = paper_close_pnl(
        direction=TradeDirection.LONG,
        entry_price=Decimal("50"),
        exit_price=Decimal("50"),
        size=Decimal("1"),
        fees=Decimal("0"),
        funding=Decimal("0"),
        slippage=Decimal("0"),
    )
    assert flat.result is TradeResult.BREAKEVEN


def test_paper_close_pnl_rejects_bad_inputs() -> None:
    with pytest.raises(ValidationAppError):
        paper_close_pnl(
            direction=TradeDirection.LONG,
            entry_price=Decimal("0"),
            exit_price=Decimal("1"),
            size=Decimal("1"),
            fees=Decimal("0"),
            funding=Decimal("0"),
            slippage=Decimal("0"),
        )
    with pytest.raises(ValidationAppError):
        paper_close_pnl(
            direction=TradeDirection.LONG,
            entry_price=Decimal("1"),
            exit_price=Decimal("2"),
            size=Decimal("1"),
            fees=Decimal("-1"),
            funding=Decimal("0"),
            slippage=Decimal("0"),
        )


def test_watcher_measurement_labels_replay_source() -> None:
    settings = paper_settings(database_url=_DATABASE_URL)
    assert watcher_measurement_is_replay(None) is False
    assert watcher_measurement_is_replay(settings) is True
    live = settings.model_copy(update={"perpetual_evidence_source": "binance_usdm"})
    assert watcher_measurement_is_replay(live) is False


def _factory() -> sessionmaker[Session]:
    return phase7_plan_session_factory()


def _close_request(
    envelope: object,
    command_id: object,
    *,
    key: str,
    exit_price: Decimal = Decimal("99990"),
    exit_reason: str = "take_profit",
) -> ClosePaperPlanRequest:
    plan = envelope.plan  # type: ignore[attr-defined]
    return ClosePaperPlanRequest(
        organization_id=plan.organization_id,
        user_id=plan.user_id,
        account_id=plan.account_id,
        revision_id=plan.revision_id,
        command_id=command_id,  # type: ignore[arg-type]
        # Canonical fixture side is SELL. A lower exit is the profitable close.
        exit_price=exit_price,
        fees=Decimal("0.5"),
        funding=Decimal("0"),
        slippage=Decimal("0"),
        exit_reason=exit_reason,
        occurred_at=EXECUTE_AT + timedelta(minutes=1),
        idempotency_key=key,
    )


@requires_postgres
def test_replay_path_close_answers_paper_statistics() -> None:
    factory = _factory()
    world, envelope, authorization = prepared_authorized_canonical(factory)
    result, session, service, runtime = _execute(
        factory, envelope, authorization, key="stats-mvp-allow"
    )
    try:
        service.apply_paper_plan_fill(
            command_id=result.command_id,
            fill_quantity=Decimal("1"),
            fill_price=Decimal("100000"),
            source_identity="stats-mvp-fill",
            occurred_at=EXECUTE_AT,
        )
        session.commit()
        closed = service.close_canonical_paper_plan(
            _close_request(envelope, result.command_id, key="stats-mvp-close")
        )
        command = make_eval_command()
        outcome = make_eval_outcome(command, candidate_ids=(world.candidate.candidate_id,))
        PaperEvaluationRecorder(PostgresPaperEvaluationStore(session)).record_watcher_outcome(
            command,
            outcome,
            replayed=True,
            strategy_version_id=STRATEGY_VERSION_ID,
            setup_definition_id=COMPILED_SETUP_ID,
            occurred_at=EXECUTE_AT,
        )
        session.commit()

        trade = session.get(JournalTrade, closed.journal_trade_id)
        assert trade is not None
        assert trade.status is JournalTradeStatus.CLOSED
        assert trade.symbol == envelope.plan.execution_instrument
        assert trade.timeframe == envelope.plan.timeframe
        assert trade.direction is TradeDirection.SHORT
        assert trade.entry_price == Decimal("100000")
        assert trade.exit_price == Decimal("99990")
        assert trade.exit_reason == "take_profit"
        assert trade.fees == Decimal("0.5")
        assert trade.net_pnl == Decimal("9.5")
        assert trade.result is TradeResult.WIN
        assert trade.strategy_version_id == envelope.plan.strategy_version_id
        assert trade.thesis
        assert closed.result is TradeResult.WIN
        assert closed.live_executable is False

        stats = JournalStatisticsService(session, max_rows=1000)
        overall = stats.compute(
            organization_id=ORG_ID,
            user_id=USER_ID,
            group_by=JournalStatsGroupBy.OVERALL,
            filters=JournalStatsFilters(),
        )
        assert overall.overall.trade_count == 1
        assert overall.overall.wins == 1
        assert overall.overall.losses == 0
        assert overall.overall.win_rate == 1.0
        assert overall.overall.net_pnl_total == Decimal("9.5")
        assert overall.overall.average_winner == Decimal("9.5")
        assert overall.overall.average_loser is None
        assert overall.overall.fees_total == Decimal("0.5")
        assert overall.overall.average_r == pytest.approx(0.95)

        by_symbol = stats.compute(
            organization_id=ORG_ID,
            user_id=USER_ID,
            group_by=JournalStatsGroupBy.SYMBOL,
            filters=JournalStatsFilters(),
        )
        assert by_symbol.buckets[0].key == trade.symbol
        by_timeframe = stats.compute(
            organization_id=ORG_ID,
            user_id=USER_ID,
            group_by=JournalStatsGroupBy.TIMEFRAME,
            filters=JournalStatsFilters(),
        )
        assert by_timeframe.buckets[0].key == trade.timeframe
        by_strategy = stats.compute(
            organization_id=ORG_ID,
            user_id=USER_ID,
            group_by=JournalStatsGroupBy.STRATEGY_VERSION,
            filters=JournalStatsFilters(),
        )
        assert by_strategy.buckets[0].key == str(trade.strategy_version_id)

        learning = LearningQueryService(PostgresAttributionStore(session))
        record = learning.get_record(
            organization_id=ORG_ID, candidate_id=world.candidate.candidate_id
        )
        assert record is not None
        assert record.facts.strategy_pattern.closed is True
        assert record.facts.strategy_pattern.win is True
        assert record.facts.outcome.result is TradeResult.WIN
        assert record.facts.outcome.net_pnl == Decimal("9.5")
        assert (
            record.facts.strategy_pattern.setup_definition_id == world.candidate.setup_definition_id
        )
        facts_text = render_learning_facts_text(record)
        assert "Result: win" in facts_text
        assert "Setup definition ID:" in facts_text
        assert "Strategy version ID:" in facts_text
        snapshot = learning.strategy_pattern_stats(organization_id=ORG_ID)
        assert snapshot.patterns[0].win_count == 1
        assert snapshot.patterns[0].loss_count == 0
        assert snapshot.patterns[0].setup_definition_id == COMPILED_SETUP_ID

        summary = PaperEvaluationQueryService(
            PostgresPaperEvaluationStore(session),
            attribution_store=PostgresAttributionStore(session),
            journal=SqlAlchemyJournalExcursionPort(session),
        ).summary(
            organization_id=ORG_ID,
            eligibility=(world.evaluation,),
            generated_at=EXECUTE_AT,
        )
        assert summary.facts.watcher.replay_count == 1
        assert summary.facts.conversion.closed == 1
        assert summary.facts.strategy_overall.win_count == 1
        assert summary.facts.strategy_overall.loss_count == 0
        assert summary.facts.strategy_overall.net_pnl_total == Decimal("9.50")
        assert summary.facts.strategy_versions[0].setup_definition_id == COMPILED_SETUP_ID
        assert summary.live_executable is False

        replayed = service.close_canonical_paper_plan(
            _close_request(envelope, result.command_id, key="stats-mvp-close")
        )
        session.commit()
        assert replayed.replayed is True
        again = stats.compute(
            organization_id=ORG_ID,
            user_id=USER_ID,
            group_by=JournalStatsGroupBy.OVERALL,
            filters=JournalStatsFilters(),
        )
        assert again.overall.trade_count == 1

        with pytest.raises(ValidationAppError) as raised:
            service.close_canonical_paper_plan(
                _close_request(envelope, result.command_id, key="stats-mvp-close-again")
            )
        assert raised.value.details["reason"] == "already_closed"
        assert runtime is not None
        assert phase8_settings().enable_real_trading is False
    finally:
        session.close()


@requires_postgres
def test_losing_short_close_answers_average_loss() -> None:
    factory = _factory()
    world, envelope, authorization = prepared_authorized_canonical(factory)
    result, session, service, _runtime = _execute(
        factory, envelope, authorization, key="stats-mvp-loss"
    )
    try:
        service.apply_paper_plan_fill(
            command_id=result.command_id,
            fill_quantity=Decimal("1"),
            fill_price=Decimal("100000"),
            source_identity="stats-mvp-loss-fill",
            occurred_at=EXECUTE_AT,
        )
        session.commit()
        closed = service.close_canonical_paper_plan(
            _close_request(
                envelope,
                result.command_id,
                key="stats-mvp-loss-close",
                exit_price=Decimal("100010"),
                exit_reason="stop_loss",
            )
        )
        session.commit()
        assert closed.result is TradeResult.LOSS
        assert closed.net_pnl == Decimal("-10.5")
        assert closed.exit_reason == "stop_loss"
        stats = JournalStatisticsService(session, max_rows=1000).compute(
            organization_id=ORG_ID,
            user_id=USER_ID,
            group_by=JournalStatsGroupBy.OVERALL,
            filters=JournalStatsFilters(),
        )
        assert stats.overall.trade_count == 1
        assert stats.overall.wins == 0
        assert stats.overall.losses == 1
        assert stats.overall.win_rate == 0.0
        assert stats.overall.net_pnl_total == Decimal("-10.5")
        assert stats.overall.average_winner is None
        assert stats.overall.average_loser == Decimal("-10.5")
        assert stats.overall.average_r == pytest.approx(-1.05)
        record = LearningQueryService(PostgresAttributionStore(session)).get_record(
            organization_id=ORG_ID, candidate_id=world.candidate.candidate_id
        )
        assert record is not None
        assert record.facts.outcome.result is TradeResult.LOSS
        assert record.facts.strategy_pattern.loss is True
        assert "Result: loss" in render_learning_facts_text(record)
    finally:
        session.close()


@requires_postgres
def test_close_before_fill_is_refused() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    result, session, _service, _runtime = _execute(
        factory, envelope, authorization, key="stats-mvp-unfilled", runtime=runtime
    )
    try:
        service = canonical_execution_service(session, runtime)
        with pytest.raises(ValidationAppError) as raised:
            service.close_canonical_paper_plan(
                _close_request(envelope, result.command_id, key="stats-mvp-too-soon")
            )
        assert raised.value.details["reason"] == "not_open"
        request = canonical_execute_request(envelope, authorization, key="unused")
        assert request.organization_id == envelope.plan.organization_id
    finally:
        session.close()
