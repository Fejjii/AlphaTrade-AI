"""Trade proposal schema including the mandatory exit strategy (PRD §6.5).

Every proposal must carry invalidation, a stop loss, take-profit levels, and
exit criteria — these are product hard requirements, not optional fields.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    Confidence,
    Leverage,
    LossAcceptanceStatus,
    ORMModel,
    PositiveDecimal,
    ProposalStatus,
    RiskSeverity,
    StrategyId,
    StrictModel,
    Symbol,
    Timeframe,
    TradeDirection,
)
from app.schemas.risk import RiskCheckResult


class TakeProfitLevel(StrictModel):
    """A single take-profit target with the fraction of position to close."""

    price: PositiveDecimal
    size_fraction: float = Field(gt=0, le=1, description="Fraction of position to close here.")


class ExitCriteria(StrictModel):
    """Structured exit plan. Required on every proposal."""

    invalidation: str = Field(description="Thesis-broken condition forcing an exit.")
    stop_loss: PositiveDecimal
    take_profits: list[TakeProfitLevel] = Field(min_length=1)
    breakeven_trigger: Decimal | None = Field(
        default=None, description="Price at which stop moves to entry."
    )
    runner_enabled: bool = False
    runner_notes: str | None = None

    @model_validator(mode="after")
    def _validate_tp_fractions(self) -> ExitCriteria:
        total = sum(tp.size_fraction for tp in self.take_profits)
        if total > 1.0 + 1e-9:
            raise ValueError("Sum of take-profit size fractions cannot exceed 1.0")
        return self


class TradeProposal(ORMModel):
    """A complete, human-reviewable trade plan."""

    id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    signal_id: UUID | None = None
    strategy_id: StrategyId
    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    entry_price: PositiveDecimal
    entry_low: PositiveDecimal | None = None
    entry_high: PositiveDecimal | None = None
    position_size: PositiveDecimal
    leverage: Leverage
    exit: ExitCriteria
    confidence: Confidence
    risk_level: RiskSeverity
    rationale: str = Field(description="Why the plan is valid.")
    status: ProposalStatus = ProposalStatus.DRAFT
    approval_required: bool = False
    risk_result: RiskCheckResult | None = None
    user_strategy_id: UUID | None = None
    planned_loss_amount: Decimal | None = None
    loss_acceptance_required: bool = False
    loss_acceptance_status: LossAcceptanceStatus = LossAcceptanceStatus.NOT_REQUIRED
    actual_loss_amount: Decimal | None = None
    created_at: datetime


class TradeProposalCreate(StrictModel):
    """API request to persist a trade proposal."""

    organization_id: UUID
    user_id: UUID
    signal_id: UUID | None = None
    strategy_id: StrategyId
    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    entry_price: PositiveDecimal
    entry_low: PositiveDecimal | None = None
    entry_high: PositiveDecimal | None = None
    position_size: PositiveDecimal
    leverage: Leverage
    exit: ExitCriteria
    confidence: Confidence
    risk_level: RiskSeverity
    rationale: str = Field(min_length=1, max_length=4000)
    approval_required: bool = False
    risk_result: RiskCheckResult | None = None
    user_strategy_id: UUID | None = None
    planned_loss_amount: Decimal | None = None
    loss_acceptance_required: bool = False
    loss_acceptance_status: LossAcceptanceStatus = LossAcceptanceStatus.NOT_REQUIRED


class LossAcceptanceUpdate(StrictModel):
    """Confirm or reject planned loss on a proposal."""

    accepted: bool
    planned_loss_amount: PositiveDecimal


class ProposalStatusUpdate(StrictModel):
    status: ProposalStatus


class PaginatedTradeProposals(StrictModel):
    items: list[TradeProposal]
    total: int
    limit: int
    offset: int
