"""Deterministic discipline scoring — no LLM authority."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.schemas.analytics import DisciplineScoreResult
from app.schemas.common import ApprovalStatus, RiskRuleId
from app.services.analytics.helpers import (
    date_range_bounds,
    load_approvals,
    load_journals,
    load_orders,
    load_proposals,
    proposal_had_warning,
    proposal_was_blocked,
)


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class DisciplineScoreService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compute(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> DisciplineScoreResult:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        proposals = load_proposals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        orders = load_orders(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        journals = load_journals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        approvals = load_approvals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
        )
        approval_by_proposal = {a.proposal_id: a for a in approvals}
        journal_by_proposal = {
            j.linked_proposal_id: j for j in journals if j.linked_proposal_id is not None
        }

        positive: list[str] = []
        negative: list[str] = []
        suggestions: list[str] = []
        points = 0
        max_points = 0

        sample = proposals[-20:] if proposals else []
        if not sample and not orders:
            return DisciplineScoreResult(
                score=100,
                grade="A",
                positive_behaviors=["No recent trades requiring discipline review."],
                negative_behaviors=[],
                improvement_suggestions=[
                    "Journal your next paper trade with lessons and improvement rules."
                ],
            )

        for proposal in sample:
            max_points += 8
            local = 0

            if proposal.stop_loss and proposal.stop_loss > 0:
                local += 1
                if "Consistent stop-loss usage" not in positive:
                    positive.append("Consistent stop-loss usage")
            else:
                negative.append("Missing stop loss on at least one proposal")
                suggestions.append("Define a stop loss before approving any paper trade.")

            if proposal.invalidation and proposal.invalidation.strip():
                local += 1
            else:
                negative.append("Missing invalidation criteria on a proposal")
                suggestions.append("Write explicit invalidation rules for each setup.")

            if not proposal_was_blocked(proposal):
                local += 1
            else:
                negative.append("Risk engine blocked a proposal — limits were breached")
                suggestions.append(
                    "Reduce size or wait for better conditions when risk blocks fire."
                )

            approval = approval_by_proposal.get(proposal.id)
            if not proposal.approval_required or (
                approval and approval.status is ApprovalStatus.APPROVED
            ):
                local += 1
            elif proposal.approval_required:
                negative.append("Approval flow not completed before execution intent")
                suggestions.append("Wait for explicit approval before paper execution.")

            journal = journal_by_proposal.get(proposal.id)
            if journal and (journal.lessons or journal.exit_rationale):
                local += 1
                if "Journal completion after trades" not in positive:
                    positive.append("Journal completion after trades")
            elif proposal.id in {o.proposal_id for o in orders}:
                negative.append("Paper trade without completed journal")
                suggestions.append("Close the loop: journal every executed paper trade.")

            if not proposal_had_warning(proposal, RiskRuleId.OVERTRADING):
                local += 1
            else:
                negative.append("Overtrading warning appeared in risk checks")
                suggestions.append("Reduce trade frequency after overtrading warnings.")

            if not proposal_had_warning(proposal, RiskRuleId.STRONG_GREEN_DAY):
                local += 1
            else:
                negative.append("Traded despite green-day protection warning")
                suggestions.append("Honor green-day guard — protect mental capital.")

            if not proposal_had_warning(proposal, RiskRuleId.MAX_DAILY_LOSS):
                local += 1
            else:
                negative.append("Activity after daily loss warning")
                suggestions.append("Stop trading for the day after daily loss limits trigger.")

            executed = any(o.proposal_id == proposal.id for o in orders)
            if executed and approval and approval.status is ApprovalStatus.APPROVED:
                local += 1
                if "Paper execution matched approved proposal" not in positive:
                    positive.append("Paper execution matched approved proposal")
            elif executed:
                negative.append("Paper execution without matching approval record")
                suggestions.append("Only execute paper orders tied to approved proposals.")

            points += local

        score = round((points / max_points) * 100) if max_points else 100
        score = max(0, min(100, score))

        if score >= 80 and not suggestions:
            suggestions.append("Maintain journaling discipline and review weakest setup weekly.")

        return DisciplineScoreResult(
            score=score,
            grade=_grade(score),
            positive_behaviors=positive[:8],
            negative_behaviors=negative[:8],
            improvement_suggestions=suggestions[:8],
        )
