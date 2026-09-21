"""Read-only journal MFE/MAE and rule-compliance facts for paper evaluation."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import JournalTrade, JournalTradeRuleCheck
from app.paper_evaluation.ports import JournalTradeMeasurement
from app.schemas.common import JournalTradeStatus, RuleComplianceStatus
from app.schemas.journal_statistics import TradeRuleCompliance

_WORST = {
    RuleComplianceStatus.VIOLATED: 3,
    RuleComplianceStatus.PARTIAL: 2,
    RuleComplianceStatus.FOLLOWED: 1,
    RuleComplianceStatus.NOT_APPLICABLE: 0,
    RuleComplianceStatus.UNASSESSED: 0,
}


class SqlAlchemyJournalExcursionPort:
    """Copies recorded journal values. Never writes JournalTrade or calls markets."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def facts_for(
        self,
        *,
        organization_id: UUID,
        journal_trade_ids: tuple[UUID, ...],
    ) -> dict[UUID, JournalTradeMeasurement]:
        if not journal_trade_ids:
            return {}
        trades = self._session.scalars(
            select(JournalTrade).where(
                JournalTrade.organization_id == organization_id,
                JournalTrade.id.in_(journal_trade_ids),
            )
        ).all()
        compliance = _compliance_by_trade(
            self._session,
            organization_id=organization_id,
            trade_ids=tuple(row.id for row in trades),
        )
        out: dict[UUID, JournalTradeMeasurement] = {}
        for row in trades:
            capture = None
            if row.realized_vs_available_pct is not None:
                capture = Decimal(str(row.realized_vs_available_pct))
            out[row.id] = JournalTradeMeasurement(
                journal_trade_id=row.id,
                mfe_amount=row.mfe_amount,
                mae_amount=row.mae_amount,
                capture_pct=capture,
                planned_risk_amount=row.planned_risk_amount,
                net_pnl=row.net_pnl,
                result=row.result,
                rule_compliance=compliance.get(row.id, TradeRuleCompliance.UNASSESSED),
                closed_at=row.exit_time if row.status is JournalTradeStatus.CLOSED else None,
            )
        return out


def _compliance_by_trade(
    session: Session,
    *,
    organization_id: UUID,
    trade_ids: tuple[UUID, ...],
) -> dict[UUID, TradeRuleCompliance]:
    if not trade_ids:
        return {}
    rows = session.execute(
        select(JournalTradeRuleCheck.journal_trade_id, JournalTradeRuleCheck.status).where(
            JournalTradeRuleCheck.organization_id == organization_id,
            JournalTradeRuleCheck.journal_trade_id.in_(trade_ids),
        )
    ).all()
    worst: dict[UUID, TradeRuleCompliance] = {}
    rank: dict[UUID, int] = {}
    mapping = {
        RuleComplianceStatus.VIOLATED: TradeRuleCompliance.VIOLATED,
        RuleComplianceStatus.PARTIAL: TradeRuleCompliance.PARTIAL,
        RuleComplianceStatus.FOLLOWED: TradeRuleCompliance.COMPLIANT,
    }
    for trade_id, status in rows:
        mapped = mapping.get(status, TradeRuleCompliance.UNASSESSED)
        score = _WORST.get(status, 0)
        if score > rank.get(trade_id, -1):
            rank[trade_id] = score
            worst[trade_id] = mapped
    return worst
