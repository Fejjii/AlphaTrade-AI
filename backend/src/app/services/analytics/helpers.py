"""Shared helpers for trading analytics queries."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import (
    ApprovalRequest,
    Order,
    Position,
    RiskEvent,
    TradeJournal,
    TradeProposal,
)
from app.schemas.common import (
    PositionStatus,
    RiskAction,
    RiskRuleId,
    SetupType,
    StrategyId,
    TradeResult,
)

SETUP_TYPES: tuple[SetupType, ...] = tuple(SetupType)


def date_range_bounds(
    start: date | None,
    end: date | None,
) -> tuple[datetime | None, datetime | None]:
    start_dt = datetime.combine(start, time.min, tzinfo=UTC) if start else None
    end_dt = datetime.combine(end, time.max, tzinfo=UTC) if end else None
    return start_dt, end_dt


def apply_created_filter(
    stmt: Select[Any],
    model: type,
    *,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> Select[Any]:
    if start_dt is not None:
        stmt = stmt.where(model.created_at >= start_dt)
    if end_dt is not None:
        stmt = stmt.where(model.created_at <= end_dt)
    return stmt


def tenant_filters(
    model: type,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[Any]:
    filters: list[Any] = [model.organization_id == organization_id]
    if user_id is not None and hasattr(model, "user_id"):
        filters.append(model.user_id == user_id)
    return filters


def resolve_setup_type(
    *,
    strategy_id: StrategyId | None,
    risk_state: dict | None = None,
) -> SetupType | None:
    if strategy_id is not None:
        return SetupType(strategy_id.value)
    if risk_state and risk_state.get("setup_type"):
        try:
            return SetupType(str(risk_state["setup_type"]))
        except ValueError:
            return None
    return None


def top_n(counter: Counter[str], n: int = 5) -> list[str]:
    return [item for item, _ in counter.most_common(n)]


def average_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def severity_label(values: list[str]) -> str | None:
    if not values:
        return None
    counts = Counter(values)
    return counts.most_common(1)[0][0]


def load_proposals(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
    setup_type: SetupType | None = None,
) -> list[TradeProposal]:
    stmt = select(TradeProposal).where(
        *tenant_filters(TradeProposal, organization_id=organization_id, user_id=user_id)
    )
    if setup_type is not None:
        stmt = stmt.where(TradeProposal.strategy_id == StrategyId(setup_type.value))
    stmt = apply_created_filter(stmt, TradeProposal, start_dt=start_dt, end_dt=end_dt)
    return list(session.scalars(stmt).all())


def load_orders(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
    setup_type: SetupType | None = None,
) -> list[Order]:
    stmt = select(Order).where(
        *tenant_filters(Order, organization_id=organization_id, user_id=user_id)
    )
    if setup_type is not None:
        stmt = stmt.where(Order.strategy_id == StrategyId(setup_type.value))
    stmt = apply_created_filter(stmt, Order, start_dt=start_dt, end_dt=end_dt)
    return list(session.scalars(stmt).all())


def load_positions(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
    setup_type: SetupType | None = None,
) -> list[Position]:
    stmt = select(Position).where(
        *tenant_filters(Position, organization_id=organization_id, user_id=user_id)
    )
    if setup_type is not None:
        stmt = stmt.where(Position.strategy_id == StrategyId(setup_type.value))
    stmt = apply_created_filter(stmt, Position, start_dt=start_dt, end_dt=end_dt)
    return list(session.scalars(stmt).all())


def load_journals(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
    setup_type: SetupType | None = None,
) -> list[TradeJournal]:
    stmt = select(TradeJournal).where(
        *tenant_filters(TradeJournal, organization_id=organization_id, user_id=user_id)
    )
    if setup_type is not None:
        stmt = stmt.where(TradeJournal.strategy_id == StrategyId(setup_type.value))
    stmt = apply_created_filter(stmt, TradeJournal, start_dt=start_dt, end_dt=end_dt)
    return list(session.scalars(stmt).all())


def load_approvals(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(
        *tenant_filters(ApprovalRequest, organization_id=organization_id, user_id=user_id)
    )
    return list(session.scalars(stmt).all())


def load_risk_events(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> list[RiskEvent]:
    stmt = select(RiskEvent).where(
        *tenant_filters(RiskEvent, organization_id=organization_id, user_id=user_id)
    )
    if start_dt is not None:
        stmt = stmt.where(RiskEvent.event_at >= start_dt)
    if end_dt is not None:
        stmt = stmt.where(RiskEvent.event_at <= end_dt)
    return list(session.scalars(stmt).all())


def paper_pnl_for_position(row: Position) -> Decimal | None:
    """Realized PnL for a *closed* paper position; ``None`` while still open.

    Realized PnL is only meaningful once a position is closed. Open positions
    carry unrealized PnL only and must be excluded from win/loss statistics.
    """
    if row.status is PositionStatus.CLOSED:
        return row.realized_pnl
    return None


def is_win(pnl: Decimal | None) -> bool:
    return pnl is not None and pnl > 0


def is_loss(pnl: Decimal | None) -> bool:
    return pnl is not None and pnl < 0


def journal_result_is_win(entry: TradeJournal) -> bool:
    return entry.result is TradeResult.WIN


def journal_result_is_loss(entry: TradeJournal) -> bool:
    return entry.result is TradeResult.LOSS


def proposal_had_warning(proposal: TradeProposal, rule_id: RiskRuleId) -> bool:
    if not proposal.risk_result:
        return False
    triggered = proposal.risk_result.get("triggered_rules") or []
    for item in triggered:
        rid = item.get("rule_id") if isinstance(item, dict) else None
        if rid == rule_id.value:
            return True
    return False


def proposal_was_blocked(proposal: TradeProposal) -> bool:
    if not proposal.risk_result:
        return False
    return proposal.risk_result.get("action") == RiskAction.BLOCK.value


def count_approvals_by_status(approvals: list[ApprovalRequest]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in approvals:
        counts[row.status.value] += 1
    return dict(counts)
