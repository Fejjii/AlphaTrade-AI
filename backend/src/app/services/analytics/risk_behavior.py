"""Risk behavior dashboard aggregates."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.schemas.analytics import RiskBehaviorAnalytics
from app.schemas.common import ApprovalStatus, AuditEventType, RiskAction, RiskRuleId
from app.services.analytics.helpers import (
    count_approvals_by_status,
    date_range_bounds,
    load_approvals,
    load_journals,
    load_orders,
    load_proposals,
    load_risk_events,
    proposal_had_warning,
    tenant_filters,
)


class RiskBehaviorAnalyticsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compute(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RiskBehaviorAnalytics:
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
        risk_events = load_risk_events(
            self._session,
            organization_id=organization_id,
            user_id=user_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        rule_counter: Counter[str] = Counter()
        daily_loss_warnings = 0
        green_day_warnings = 0
        overtrading_warnings = 0
        revenge_warnings = 0
        risk_blocks = 0

        for proposal in proposals:
            if (
                proposal.risk_result
                and proposal.risk_result.get("action") == RiskAction.BLOCK.value
            ):
                risk_blocks += 1
            if proposal_had_warning(proposal, RiskRuleId.MAX_DAILY_LOSS):
                daily_loss_warnings += 1
            if proposal_had_warning(proposal, RiskRuleId.STRONG_GREEN_DAY):
                green_day_warnings += 1
            if proposal_had_warning(proposal, RiskRuleId.OVERTRADING):
                overtrading_warnings += 1
            if proposal_had_warning(proposal, RiskRuleId.COOLDOWN_AFTER_LOSS):
                revenge_warnings += 1
            if proposal.risk_result:
                for item in proposal.risk_result.get("triggered_rules") or []:
                    if isinstance(item, dict) and item.get("rule_id"):
                        rule_counter[str(item["rule_id"])] += 1

        for event in risk_events:
            rule_counter[event.rule_triggered.value] += 1
            if event.action_taken is RiskAction.BLOCK:
                risk_blocks += 1

        approval_counts = count_approvals_by_status(approvals)
        paper_rejected = self._count_audit_events(
            organization_id=organization_id,
            user_id=user_id,
            event_type=AuditEventType.PAPER_ORDER_REJECTED,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        executed_proposals = {o.proposal_id for o in orders if o.proposal_id}
        journaled_executed = sum(
            1
            for j in journals
            if j.linked_proposal_id in executed_proposals and (j.lessons or j.exit_rationale)
        )
        completion_rate = (
            journaled_executed / len(executed_proposals) if executed_proposals else 1.0
        )

        return RiskBehaviorAnalytics(
            risk_blocks_count=risk_blocks,
            daily_loss_warnings=daily_loss_warnings,
            green_day_warnings=green_day_warnings,
            overtrading_warnings=overtrading_warnings,
            revenge_trading_warnings=revenge_warnings,
            proposals_rejected=approval_counts.get(ApprovalStatus.REJECTED.value, 0),
            proposals_needs_more_analysis=approval_counts.get(
                ApprovalStatus.NEEDS_MORE_ANALYSIS.value, 0
            ),
            paper_orders_rejected=paper_rejected,
            approval_pending_count=approval_counts.get(ApprovalStatus.PENDING.value, 0),
            approval_approved_count=approval_counts.get(ApprovalStatus.APPROVED.value, 0),
            journal_completion_rate=min(1.0, max(0.0, completion_rate)),
            triggered_rules=dict(rule_counter),
        )

    def _count_audit_events(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: AuditEventType,
        start_dt,
        end_dt,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AuditLog)
            .where(
                *tenant_filters(AuditLog, organization_id=organization_id, user_id=user_id),
                AuditLog.action == event_type,
            )
        )
        if start_dt is not None:
            stmt = stmt.where(AuditLog.event_at >= start_dt)
        if end_dt is not None:
            stmt = stmt.where(AuditLog.event_at <= end_dt)
        return int(self._session.scalar(stmt) or 0)
