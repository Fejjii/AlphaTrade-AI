"""Position sizing v2 schemas (Slice 33)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.schemas.common import (
    PreTradeRecommendation,
    RiskPercent,
    StrictModel,
    TradeDirection,
)


class PositionSizingRequest(StrictModel):
    entry_price: Decimal = Field(gt=0)
    invalidation_level: Decimal = Field(gt=0)
    account_balance: Decimal = Field(gt=0)
    max_risk_percent: RiskPercent = Decimal("1")
    leverage_limit: Decimal = Field(default=Decimal("10"), gt=0, le=125)
    confidence_score: float = Field(default=70.0, ge=0, le=100)
    direction: TradeDirection = TradeDirection.LONG
    take_profit_price: Decimal | None = Field(default=None, gt=0)


class PositionSizingResult(StrictModel):
    entry_price: Decimal
    invalidation_level: Decimal
    stop_loss_distance: Decimal
    account_balance: Decimal
    max_risk_percent: RiskPercent
    maximum_acceptable_loss: Decimal
    notional_position_size: Decimal
    leverage_limit: Decimal
    leverage_recommendation: Decimal
    risk_reward_ratio: float | None = None
    required_breakeven_win_rate: float | None = None
    confidence_score: float = Field(ge=0, le=100)
    confidence_adjusted_size: Decimal
    worst_case_scenario: str
    final_recommendation: PreTradeRecommendation
    planned_loss_amount: Decimal


class LossAcceptanceRequest(StrictModel):
    planned_loss_amount: Decimal = Field(gt=0)
    accepted: bool


class LossAcceptanceResult(StrictModel):
    planned_loss_amount: Decimal
    accepted: bool
    status: str
    recommendation: str
    can_execute_paper: bool


class PaperPositionSizingRequest(StrictModel):
    """Server-bound cash budget and instrument policy; never accepted from chat."""

    approved_risk_amount: Decimal = Field(gt=0)
    maximum_notional: Decimal = Field(gt=0)
    entry: Decimal = Field(gt=0)
    stop: Decimal = Field(gt=0)
    lot_size: Decimal = Field(gt=0)
    minimum_quantity: Decimal = Field(gt=0)
    minimum_notional: Decimal = Field(ge=0)
    fee_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    funding_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    slippage_allowance: Decimal = Field(default=Decimal("0"), ge=0)


class PaperPositionSizingResult(StrictModel):
    raw_quantity: Decimal
    quantity: Decimal
    maximum_loss: Decimal
    conservative_remainder: Decimal
