"""Human versus system comparison service (Slice 33 + Slice 34 deltas)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import TradeJournal, TradeProposal
from app.repositories.journal import JournalRepository
from app.repositories.proposals import ProposalRepository
from app.schemas.human_vs_system import HumanVsSystemComparison, PlanAdherenceBreakdown
from app.schemas.proposal import TradeProposal as TradeProposalSchema


class HumanVsSystemService:
    """Compare actual trade behavior to system plan."""

    def __init__(self, session: Session) -> None:
        self._proposals = ProposalRepository(session)
        self._journal = JournalRepository(session)

    def compare(
        self,
        trade_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> HumanVsSystemComparison:
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

        if proposal is None and journal is None:
            raise NotFoundError("Trade not found for comparison.")

        plan = (
            TradeProposalSchema.model_validate(proposal, from_attributes=True) if proposal else None
        )
        notes: list[str] = []
        limitations = [
            "No exact PnL simulation when position exit data is missing.",
            "Runner profit placeholder only — live runner tracking not connected.",
            "Paper mode only — comparison is educational, not execution authority.",
        ]

        entry_delta: float | None = None
        size_delta: float | None = None
        stop_note: str | None = None
        exit_note: str | None = None
        leverage_note: str | None = None
        planned_vs_actual: str | None = None
        early_exit: bool | None = None
        missed_runner = "Runner profit not calculated — insufficient exit path data."

        entry_pts = 0
        size_pts = 0
        stop_pts = 0
        tp_pts = 0
        emotion_pts = 0
        journal_pts = 0

        if plan is not None:
            entry_pts = 20
            size_pts = 20
            stop_pts = 20
            tp_pts = 10
            if journal and journal.linked_position_id:
                entry_pts = 18
                entry_delta = 0.15
                notes.append("Entry approximate — linked position used.")

            leverage_note = f"Plan leverage {plan.leverage}; journal leverage not always recorded."
            stop_note = f"Plan stop {plan.exit.stop_loss}; invalidation: {plan.exit.invalidation}."
            if journal and journal.exit_rationale:
                exit_note = journal.exit_rationale
            else:
                exit_note = "Unknown exit"

            if plan.planned_loss_amount is not None:
                actual = plan.actual_loss_amount
                if actual is not None:
                    planned_vs_actual = f"Planned loss {plan.planned_loss_amount}; actual {actual}."
                else:
                    planned_vs_actual = (
                        f"Planned loss {plan.planned_loss_amount}; actual not recorded."
                    )

            if journal and journal.result and journal.result.value in {"loss", "breakeven"}:
                early_exit = True
                notes.append("Early or suboptimal exit suspected from journal result tag.")

        if journal is not None:
            journal_pts = 10 if journal.lessons or journal.exit_rationale else 5
            emotions = journal.emotions or []
            if plan is not None:
                emotion_pts = 15 if len(emotions) <= 1 else 8 if len(emotions) <= 3 else 0
            else:
                emotion_pts = 15 if len(emotions) <= 1 else 8 if len(emotions) <= 3 else 0
            if emotions:
                notes.append(f"Emotion tags recorded: {', '.join(emotions)}.")
        elif plan is not None:
            emotion_pts = 15

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
        return HumanVsSystemComparison(
            trade_id=trade_id,
            symbol=symbol,
            entry_delta_pct=entry_delta,
            exit_delta=exit_note,
            exit_vs_system=exit_note,
            size_delta_pct=size_delta,
            size_vs_recommended_pct=size_delta,
            leverage_delta=leverage_note,
            leverage_vs_allowed=leverage_note,
            stop_behavior_delta=stop_note,
            stop_vs_invalidation=stop_note,
            planned_loss_vs_actual=planned_vs_actual,
            early_exit_flag=early_exit,
            missed_runner_profit_placeholder=missed_runner,
            pnl_vs_simulated_placeholder=(
                "Rule-based simulated PnL placeholder — backtest engine not connected."
            ),
            emotion_tags=list(journal.emotions) if journal and journal.emotions else [],
            emotion_free_baseline="Follow system plan without emotion tags.",
            plan_adherence=breakdown,
            plan_adherence_score=total,
            notes=notes or ["Comparison uses proposal/journal linkage when available."],
            limitations=limitations,
        )

    def _find_journal_for_proposal(
        self,
        proposal_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TradeJournal | None:
        from sqlalchemy import select

        stmt = select(TradeJournal).where(
            TradeJournal.linked_proposal_id == proposal_id,
            TradeJournal.organization_id == organization_id,
            TradeJournal.user_id == user_id,
        )
        return self._journal._session.scalar(stmt)
