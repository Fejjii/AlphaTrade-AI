"""Pre-trade analysis schemas (Slice 33)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    PreTradeRecommendation,
    RiskPercent,
    StrategyId,
    StrictModel,
    Symbol,
    TradeDirection,
)
from app.schemas.position_sizing import PositionSizingResult


class DailyLossStateInput(StrictModel):
    realized_pnl: Decimal = Decimal("0")
    daily_loss_limit: Decimal = Decimal("100")
    locked: bool = False


class OpenPositionInput(StrictModel):
    symbol: Symbol
    direction: TradeDirection
    size: Decimal = Field(gt=0)
    entry_price: Decimal = Field(gt=0)
    leverage: Decimal = Field(gt=0, le=125)


class PreTradeAnalyzeRequest(StrictModel):
    organization_id: UUID
    user_id: UUID
    symbol: Symbol
    exchange: str = Field(default="binance", min_length=1, max_length=40)
    direction: TradeDirection | None = None
    strategy_id: UUID | None = None
    setup_type: StrategyId | None = None
    manual_level_ids: list[UUID] = Field(default_factory=list)
    account_size: Decimal = Field(gt=0)
    max_risk_per_trade: RiskPercent = Decimal("1")
    daily_loss_state: DailyLossStateInput | None = None
    open_positions: list[OpenPositionInput] = Field(default_factory=list)
    timeframe: str = Field(default="4h", min_length=2, max_length=8)


class PreTradeAnalyzeBody(StrictModel):
    """HTTP body for pre-trade analysis (tenant injected by API)."""

    symbol: Symbol
    exchange: str = Field(default="binance", min_length=1, max_length=40)
    direction: TradeDirection | None = None
    strategy_id: UUID | None = None
    setup_type: StrategyId | None = None
    manual_level_ids: list[UUID] = Field(default_factory=list)
    account_size: Decimal = Field(gt=0)
    max_risk_per_trade: RiskPercent = Decimal("1")
    daily_loss_state: DailyLossStateInput | None = None
    open_positions: list[OpenPositionInput] = Field(default_factory=list)
    timeframe: str = Field(default="4h", min_length=2, max_length=8)


class PreTradeAnalyzeResponse(StrictModel):
    symbol: Symbol
    exchange: str
    direction_considered: TradeDirection | None
    bullish_factors: list[str]
    bearish_factors: list[str]
    market_regime: str
    trend_alignment_score: float = Field(ge=0, le=100)
    volume_confirmation_score: float = Field(ge=0, le=100)
    funding_risk_score: float = Field(ge=0, le=100)
    setup_confidence_score: float = Field(ge=0, le=100)
    risk_reward: float | None = None
    suggested_entry_zone: dict[str, str] | None = None
    suggested_stop_loss: Decimal | None = None
    invalidation: list[str]
    tp_levels: list[dict[str, str]]
    runner_logic: list[str]
    position_size: PositionSizingResult | None = None
    leverage_recommendation: Decimal | None = None
    final_recommendation: PreTradeRecommendation
    limitations: list[str]
