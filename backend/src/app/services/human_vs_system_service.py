"""Human versus system comparison service v3 (Slice 33-36)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import BacktestRun, Position, TradeJournal, TradeProposal
from app.repositories.journal import JournalRepository
from app.repositories.proposals import ProposalRepository
from app.schemas.common import LessonSeverity, LessonSourceType, Timeframe
from app.schemas.human_vs_system import (
    DisciplineAnalysis,
    HumanVsSystemComparison,
    PlanAdherenceBreakdown,
)
from app.schemas.proposal import ExitCriteria, TakeProfitLevel
from app.schemas.proposal import TradeProposal as TradeProposalSchema
from app.services.historical_candle_service import HistoricalCandleService
from app.services.lesson_candidate_service import LessonCandidateService
from app.services.runner_missed_profit_analyzer import (
    RunnerAnalysisInput,
    RunnerAndMissedProfitAnalyzer,
)
from app.services.stop_loss_refusal_analyzer import (
    StopLossAnalysisInput,
    StopLossRefusalAnalyzer,
)


class HumanVsSystemService:
    """Compare actual trade behavior to system plan, backtest, and analyzers."""

    def __init__(
        self,
        session: Session,
        *,
        historical_candle_service: HistoricalCandleService | None = None,
    ) -> None:
        self._proposals = ProposalRepository(session)
        self._journal = JournalRepository(session)
        self._session = session
        self._runner = RunnerAndMissedProfitAnalyzer()
        self._stop = StopLossRefusalAnalyzer()
        self._lessons = LessonCandidateService(session)
        self._candles = historical_candle_service

    def compare(
        self,
        trade_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> HumanVsSystemComparison:
        journal, proposal = self._resolve_trade(trade_id, organization_id, user_id)
        if proposal is None and journal is None:
            raise NotFoundError("Trade not found for comparison.")

        plan = self._proposal_to_schema(proposal) if proposal else None
        position = self._load_position(journal, organization_id, user_id)
        backtest_note = self._backtest_context(proposal, organization_id, user_id)

        notes: list[str] = []
        limitations = [
            "Estimates are educational — not guaranteed PnL or performance.",
            "Paper mode only — comparison is coaching, not execution authority.",
            "Real trading remains disabled.",
        ]

        entry_delta: float | None = None
        size_delta: float | None = None
        leverage_note: str | None = None
        stop_note: str | None = None
        exit_note: str | None = None
        planned_vs_actual: str | None = None
        system_summary: str | None = None
        rule_violation_cost: Decimal | None = None
        emotional: list[str] = []

        entry_pts = 0
        size_pts = 0
        stop_pts = 0
        tp_pts = 0
        emotion_pts = 0
        journal_pts = 0

        actual_entry: Decimal | None = None
        direction = journal.direction if journal else (plan.direction if plan else None)

        if plan is not None:
            entry_pts = 20
            size_pts = 20
            stop_pts = 20
            tp_pts = 10
            system_summary = (
                f"System planned {plan.direction.value} {plan.symbol} entry ~{plan.entry_price}, "
                f"stop {plan.exit.stop_loss}, "
                f"TPs {[str(tp.price) for tp in plan.exit.take_profits]}."
            )
            leverage_note = f"Plan leverage {plan.leverage}."
            stop_note = f"Plan stop {plan.exit.stop_loss}; invalidation: {plan.exit.invalidation}."
            if position is not None:
                actual_entry = position.entry_price
                entry_delta = self._pct_delta(plan.entry_price, actual_entry)
                if entry_delta is not None and abs(entry_delta) > 0.5:
                    entry_pts = max(0, entry_pts - 5)
                    notes.append(f"Entry delta ~{entry_delta:.2f}% vs plan.")
                size_delta = self._pct_delta(plan.position_size, position.size)
                if size_delta is not None and abs(size_delta) > 10:
                    size_pts = max(0, size_pts - 5)
            if journal and journal.exit_rationale:
                exit_note = journal.exit_rationale
            if plan.planned_loss_amount is not None:
                journal_loss = journal.pnl if journal and journal.pnl and journal.pnl < 0 else None
                actual_loss = plan.actual_loss_amount or journal_loss
                if actual_loss is not None:
                    planned_vs_actual = (
                        f"Planned loss {plan.planned_loss_amount}; actual {abs(actual_loss)}."
                    )
                    if actual_loss < 0 and abs(actual_loss) > plan.planned_loss_amount:
                        excess = abs(actual_loss) - plan.planned_loss_amount
                        rule_violation_cost = excess.quantize(Decimal("0.01"))
                else:
                    planned_vs_actual = (
                        f"Planned loss {plan.planned_loss_amount}; actual not recorded."
                    )
                    limitations.append("Actual loss not recorded — planned vs actual is partial.")

        if position is not None and position.closed_at and position.status.value == "closed":
            notes.append("Linked position closed — using position data where available.")

        tp_prices: list[Decimal] = []
        runner_enabled = False
        planned_stop: Decimal | None = None
        planned_loss: Decimal | None = None
        if plan is not None:
            tp_prices = [tp.price for tp in plan.exit.take_profits]
            runner_enabled = plan.exit.runner_enabled
            planned_stop = plan.exit.stop_loss
            planned_loss = plan.planned_loss_amount

        exit_price = self._resolve_exit_price(journal, position, plan)
        exit_time = position.closed_at if position else None
        invalidation_price = plan.exit.stop_loss if plan else None
        post_exit_candles = self._fetch_post_exit_candles(
            symbol=(journal.symbol if journal else (plan.symbol if plan else None)),
            timeframe=(journal.timeframe if journal else (plan.timeframe if plan else None)),
            exit_time=exit_time,
        )
        runner_analysis = self._runner.analyze(
            RunnerAnalysisInput(
                entry_price=actual_entry or (plan.entry_price if plan else None),
                exit_price=exit_price,
                exit_time=exit_time,
                direction=direction,
                tp_plan_prices=tp_prices,
                runner_enabled=runner_enabled,
                invalidation_price=invalidation_price,
                candles_after_exit=post_exit_candles,
            )
        )

        journal_actual_loss = (
            abs(journal.pnl) if journal and journal.pnl and journal.pnl < 0 else None
        )
        plan_actual_loss = plan.actual_loss_amount if plan else None
        stop_analysis = self._stop.analyze(
            StopLossAnalysisInput(
                planned_stop=planned_stop,
                actual_stop=position.stop_loss if position else None,
                planned_loss=planned_loss,
                actual_loss=journal_actual_loss or plan_actual_loss,
                entry_price=actual_entry or (plan.entry_price if plan else None),
                exit_price=None,
                direction=direction,
                loss_acceptance_status=plan.loss_acceptance_status if plan else None,
                stop_was_placed=position.stop_loss is not None if position else None,
                stop_moved_away=False,
                held_for_breakeven=(
                    "breakeven" in (journal.exit_rationale or "").lower() if journal else False
                ),
                exit_after_invalidation=False,
            )
        )
        if stop_analysis.stop_violation_flag:
            stop_pts = max(0, stop_pts - 10)

        if journal is not None:
            journal_pts = 10 if journal.lessons or journal.exit_rationale else 5
            emotions = journal.emotions or []
            emotional = list(emotions)
            emotion_pts = 15 if len(emotions) <= 1 else 8 if len(emotions) <= 3 else 0
            if emotions:
                notes.append(f"Emotion tags recorded: {', '.join(emotions)}.")
                if len(emotions) > 2:
                    emotional.append("elevated_emotional_tags")
            mistakes = journal.mistakes or []
            emotional.extend(mistakes)
        elif plan is not None:
            emotion_pts = 15

        if runner_analysis.early_exit_flag:
            tp_pts = max(0, tp_pts - 5)

        breakdown = PlanAdherenceBreakdown(
            entry_followed_plan=entry_pts,
            size_respected_risk=size_pts,
            stop_loss_respected=stop_pts,
            profit_taking_followed=tp_pts,
            emotion_controlled=emotion_pts,
            journal_completed=journal_pts,
        )
        total = sum(
            (
                breakdown.entry_followed_plan,
                breakdown.size_respected_risk,
                breakdown.stop_loss_respected,
                breakdown.profit_taking_followed,
                breakdown.emotion_controlled,
                breakdown.journal_completed,
            )
        )

        symbol = plan.symbol if plan else (journal.symbol if journal else None)
        missed_placeholder = None
        if runner_analysis.missed_profit_estimate is not None:
            missed_placeholder = (
                f"Conservative missed-profit estimate: {runner_analysis.missed_profit_estimate} "
                "(not guaranteed)."
            )
        elif runner_analysis.limitations:
            missed_placeholder = runner_analysis.limitations[0]

        pnl_placeholder = backtest_note or (
            "Backtest-linked simulation unavailable for this trade." if not backtest_note else None
        )

        return HumanVsSystemComparison(
            trade_id=trade_id,
            symbol=symbol,
            entry_quality_delta_pct=entry_delta,
            exit_quality_delta=exit_note,
            size_discipline_delta_pct=size_delta,
            leverage_discipline_delta=leverage_note,
            stop_loss_discipline_delta=stop_note,
            planned_loss_vs_actual=planned_vs_actual,
            early_exit_flag=runner_analysis.early_exit_flag,
            missed_runner=runner_analysis,
            emotional_mistake_classification=emotional,
            rule_violation_cost_estimate=rule_violation_cost,
            plan_adherence=breakdown,
            plan_adherence_score=total,
            system_would_have_done=system_summary,
            backtest_context=backtest_note,
            entry_delta_pct=entry_delta,
            exit_delta=exit_note,
            exit_vs_system=exit_note,
            size_delta_pct=size_delta,
            size_vs_recommended_pct=size_delta,
            leverage_delta=leverage_note,
            leverage_vs_allowed=leverage_note,
            stop_behavior_delta=stop_note,
            stop_vs_invalidation=stop_note,
            missed_runner_profit_placeholder=missed_placeholder,
            pnl_vs_simulated_placeholder=pnl_placeholder,
            stop_loss_analysis=stop_analysis,
            emotion_tags=list(journal.emotions) if journal and journal.emotions else [],
            emotion_free_baseline="Follow system plan without emotion tags.",
            notes=notes or ["Comparison uses proposal/journal linkage when available."],
            limitations=limitations + runner_analysis.limitations + stop_analysis.limitations,
        )

    def analyze_discipline(
        self,
        journal_entry_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DisciplineAnalysis:
        _journal, proposal = self._resolve_trade(
            journal_entry_id, organization_id=organization_id, user_id=user_id
        )
        comparison = self.compare(
            journal_entry_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        lessons: list[str] = []
        candidate_ids: list[uuid.UUID] = []
        strategy_id = proposal.user_strategy_id if proposal else None
        if comparison.missed_runner and comparison.missed_runner.recommended_lesson:
            lessons.append(comparison.missed_runner.recommended_lesson)
            if comparison.missed_runner.early_exit_flag:
                cid = self._lessons.create_candidate(
                    organization_id=organization_id,
                    user_id=user_id,
                    journal_entry_id=journal_entry_id,
                    trade_id=journal_entry_id,
                    category="early_exit",
                    summary=comparison.missed_runner.recommended_lesson,
                    source_type=LessonSourceType.RUNNER_ANALYSIS,
                    related_strategy_id=strategy_id,
                    severity=LessonSeverity.MEDIUM,
                    analysis_metadata={
                        "limitations": comparison.missed_runner.limitations,
                        "confidence": comparison.missed_runner.confidence.value,
                        "missed_profit_estimate": (
                            str(comparison.missed_runner.missed_profit_estimate)
                            if comparison.missed_runner.missed_profit_estimate
                            else None
                        ),
                    },
                )
                candidate_ids.append(cid)
        if comparison.stop_loss_analysis and comparison.stop_loss_analysis.lesson:
            lessons.append(comparison.stop_loss_analysis.lesson)
            if comparison.stop_loss_analysis.stop_violation_flag:
                cid = self._lessons.create_candidate(
                    organization_id=organization_id,
                    user_id=user_id,
                    journal_entry_id=journal_entry_id,
                    trade_id=journal_entry_id,
                    category="stop_violation",
                    summary=comparison.stop_loss_analysis.lesson,
                    source_type=LessonSourceType.STOP_LOSS_REFUSAL,
                    related_strategy_id=strategy_id,
                    severity=LessonSeverity.HIGH,
                    analysis_metadata={
                        "limitations": comparison.stop_loss_analysis.limitations,
                    },
                )
                candidate_ids.append(cid)
        return DisciplineAnalysis(
            journal_entry_id=journal_entry_id,
            comparison=comparison,
            lessons_generated=lessons,
            lesson_candidate_ids=candidate_ids,
        )

    def _proposal_to_schema(self, proposal: TradeProposal) -> TradeProposalSchema:
        tps_raw = proposal.take_profits or []
        take_profits = [
            TakeProfitLevel(
                price=Decimal(str(tp.get("price", tp.get("price", "0")))),
                size_fraction=float(tp.get("size_fraction", 1.0)),
            )
            for tp in tps_raw
        ]
        if not take_profits:
            take_profits = [TakeProfitLevel(price=proposal.entry_price, size_fraction=1.0)]
        return TradeProposalSchema(
            id=proposal.id,
            organization_id=proposal.organization_id,
            user_id=proposal.user_id,
            signal_id=proposal.signal_id,
            strategy_id=proposal.strategy_id,
            symbol=proposal.symbol,
            timeframe=proposal.timeframe,
            direction=proposal.direction,
            entry_price=proposal.entry_price,
            entry_low=proposal.entry_low,
            entry_high=proposal.entry_high,
            position_size=proposal.position_size,
            leverage=proposal.leverage,
            exit=ExitCriteria(
                invalidation=proposal.invalidation,
                stop_loss=proposal.stop_loss,
                take_profits=take_profits,
                breakeven_trigger=proposal.breakeven_trigger,
                runner_enabled=proposal.runner_enabled,
                runner_notes=proposal.runner_notes,
            ),
            confidence=proposal.confidence,
            risk_level=proposal.risk_level,
            rationale=proposal.rationale,
            status=proposal.status,
            approval_required=proposal.approval_required,
            user_strategy_id=proposal.user_strategy_id,
            planned_loss_amount=proposal.planned_loss_amount,
            loss_acceptance_required=proposal.loss_acceptance_required,
            loss_acceptance_status=proposal.loss_acceptance_status,
            actual_loss_amount=proposal.actual_loss_amount,
            created_at=proposal.created_at,
        )

    def _resolve_trade(
        self,
        trade_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[TradeJournal | None, TradeProposal | None]:
        journal = self._journal.get_scoped(
            trade_id, organization_id=organization_id, user_id=user_id
        )
        proposal: TradeProposal | None = None
        if journal is not None and journal.linked_proposal_id:
            proposal = self._proposals.get_scoped(
                journal.linked_proposal_id,
                organization_id=organization_id,
            )
        if journal is None:
            proposal = self._proposals.get_scoped(trade_id, organization_id=organization_id)
            if proposal is not None:
                journal = self._find_journal_for_proposal(trade_id, organization_id, user_id)
        return journal, proposal

    def _load_position(
        self,
        journal: TradeJournal | None,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Position | None:
        if journal is None or journal.linked_position_id is None:
            return None
        stmt = select(Position).where(
            Position.id == journal.linked_position_id,
            Position.organization_id == organization_id,
            Position.user_id == user_id,
        )
        return self._session.scalar(stmt)

    def _backtest_context(
        self,
        proposal: TradeProposal | None,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        if proposal is None or proposal.user_strategy_id is None:
            return None
        runs, _ = self._list_backtest_runs(proposal.user_strategy_id, organization_id)
        if not runs:
            return None
        run = runs[0]
        if not run.result:
            return None
        metrics = run.result.get("metrics", {})
        engine = run.result.get("rule_engine_source", "unknown")
        return (
            f"Latest backtest: {metrics.get('trade_count', 0)} trades, "
            f"net PnL {metrics.get('net_pnl', 'n/a')} (simulated), engine={engine}."
        )

    def _list_backtest_runs(
        self,
        strategy_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> tuple[list[BacktestRun], int]:
        stmt = (
            select(BacktestRun)
            .where(
                BacktestRun.strategy_id == strategy_id,
                BacktestRun.organization_id == organization_id,
            )
            .order_by(BacktestRun.created_at.desc())
            .limit(1)
        )
        rows = list(self._session.scalars(stmt).all())
        return rows, len(rows)

    def _pct_delta(self, planned: Decimal, actual: Decimal) -> float | None:
        if planned == 0:
            return None
        return float((actual - planned) / planned * Decimal("100"))

    def _find_journal_for_proposal(
        self,
        proposal_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TradeJournal | None:
        stmt = select(TradeJournal).where(
            TradeJournal.linked_proposal_id == proposal_id,
            TradeJournal.organization_id == organization_id,
            TradeJournal.user_id == user_id,
        )
        return self._journal._session.scalar(stmt)

    def _resolve_exit_price(
        self,
        journal: TradeJournal | None,
        position: Position | None,
        plan: TradeProposalSchema | None,
    ) -> Decimal | None:
        if position is not None and position.status.value == "closed":
            if position.size and position.size != 0 and position.realized_pnl:
                return (position.entry_price + position.realized_pnl / position.size).quantize(
                    Decimal("0.00000001")
                )
            return position.entry_price
        if plan is not None and plan.exit.take_profits:
            return plan.exit.take_profits[0].price
        return None

    def _fetch_post_exit_candles(
        self,
        *,
        symbol: str | None,
        timeframe: str | None,
        exit_time: object | None,
    ) -> list[tuple[object, Decimal, Decimal, Decimal, Decimal]] | None:
        if self._candles is None or symbol is None or timeframe is None or exit_time is None:
            return None
        try:
            tf = Timeframe(timeframe)
        except ValueError:
            return None
        from datetime import datetime

        if not isinstance(exit_time, datetime):
            return None
        result = self._candles.get_candles(
            symbol=symbol,
            exchange="binance",
            timeframe=tf,
            start_time=exit_time,
            limit=RunnerAndMissedProfitAnalyzer.LOOKAHEAD_BARS + 2,
        )
        if not result.items:
            return None
        return [
            (c.open_time, c.open, c.high, c.low, c.close)
            for c in result.items
            if c.open_time >= exit_time
        ]
