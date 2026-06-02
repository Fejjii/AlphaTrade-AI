"""Trade review analytics across journal, proposals, and paper positions."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.analytics import TradeReviewAnalytics
from app.schemas.common import ApprovalStatus, ProposalStatus, RiskRuleId, SetupType
from app.services.analytics.helpers import (
    average_decimal,
    date_range_bounds,
    journal_result_is_loss,
    journal_result_is_win,
    load_approvals,
    load_journals,
    load_orders,
    load_proposals,
    proposal_had_warning,
    proposal_was_blocked,
)


class TradeReviewAnalyticsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compute(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradeReviewAnalytics:
        start_dt, end_dt = date_range_bounds(start_date, end_date)
        journals = load_journals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )
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
        approvals = load_approvals(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
        )
        approval_by_proposal = {a.proposal_id: a for a in approvals}

        wins = sum(1 for j in journals if journal_result_is_win(j))
        losses = sum(1 for j in journals if journal_result_is_loss(j))
        pnls = [j.pnl for j in journals if j.pnl is not None]

        setup_counter: Counter[str] = Counter()
        mistake_counter: Counter[str] = Counter()
        emotion_counter: Counter[str] = Counter()
        for entry in journals:
            if entry.strategy_id:
                setup_counter[entry.strategy_id.value] += 1
            mistake_counter.update(entry.mistakes or [])
            emotion_counter.update(entry.emotions or [])

        trades_after_daily_loss = 0
        trades_after_green_day = 0
        blocked_by_risk = 0
        for proposal in proposals:
            if proposal_was_blocked(proposal):
                blocked_by_risk += 1
            had_daily = proposal_had_warning(proposal, RiskRuleId.MAX_DAILY_LOSS)
            had_green = proposal_had_warning(proposal, RiskRuleId.STRONG_GREEN_DAY)
            if had_daily and proposal.id in {o.proposal_id for o in orders}:
                trades_after_daily_loss += 1
            if had_green and proposal.id in {o.proposal_id for o in orders}:
                trades_after_green_day += 1

        rejected = sum(1 for p in proposals if p.status is ProposalStatus.REJECTED)
        needs_more = sum(
            1
            for p in proposals
            if (a := approval_by_proposal.get(p.id))
            and a.status is ApprovalStatus.NEEDS_MORE_ANALYSIS
        )

        most_setup = None
        if setup_counter:
            most_setup = SetupType(setup_counter.most_common(1)[0][0])

        return TradeReviewAnalytics(
            total_journaled_trades=len(journals),
            win_count=wins,
            loss_count=losses,
            average_pnl=average_decimal([Decimal(str(p)) for p in pnls if p is not None]),
            most_frequent_setup_type=most_setup,
            most_frequent_mistake_tag=(
                mistake_counter.most_common(1)[0][0] if mistake_counter else None
            ),
            most_frequent_emotion_tag=(
                emotion_counter.most_common(1)[0][0] if emotion_counter else None
            ),
            trades_after_daily_loss_warning=trades_after_daily_loss,
            trades_after_green_day_warning=trades_after_green_day,
            trades_blocked_by_risk_engine=blocked_by_risk,
            proposals_rejected_by_user=rejected,
            proposals_needing_more_analysis=needs_more,
        )
