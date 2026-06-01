"""ORM ↔ schema mapping for trade proposals."""

from __future__ import annotations

from decimal import Decimal

from app.db.models import TradeProposal as TradeProposalModel
from app.schemas.common import Timeframe
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposal
from app.schemas.risk import RiskCheckResult


def proposal_to_schema(row: TradeProposalModel) -> TradeProposal:
    take_profits = [
        TakeProfitLevel(price=Decimal(str(tp["price"])), size_fraction=float(tp["size_fraction"]))
        for tp in (row.take_profits or [])
    ]
    return TradeProposal(
        id=row.id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        signal_id=row.signal_id,
        strategy_id=row.strategy_id,
        symbol=row.symbol,
        timeframe=Timeframe(row.timeframe),
        direction=row.direction,
        entry_price=row.entry_price,
        entry_low=row.entry_low,
        entry_high=row.entry_high,
        position_size=row.position_size,
        leverage=row.leverage,
        exit=ExitCriteria(
            invalidation=row.invalidation,
            stop_loss=row.stop_loss,
            take_profits=take_profits,
            breakeven_trigger=row.breakeven_trigger,
            runner_enabled=row.runner_enabled,
            runner_notes=row.runner_notes,
        ),
        confidence=row.confidence,
        risk_level=row.risk_level,
        rationale=row.rationale,
        status=row.status,
        approval_required=row.approval_required,
        risk_result=RiskCheckResult.model_validate(row.risk_result) if row.risk_result else None,
        created_at=row.created_at,
    )


def exit_to_columns(exit: ExitCriteria) -> dict:
    return {
        "stop_loss": exit.stop_loss,
        "take_profits": [
            {"price": str(tp.price), "size_fraction": tp.size_fraction} for tp in exit.take_profits
        ],
        "breakeven_trigger": exit.breakeven_trigger,
        "runner_enabled": exit.runner_enabled,
        "runner_notes": exit.runner_notes,
        "invalidation": exit.invalidation,
    }
