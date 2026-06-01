"""Strategy signal, setup definition, and setup performance schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    Confidence,
    ORMModel,
    SetupCategory,
    StrategyId,
    StrictModel,
    Symbol,
    Timeframe,
    TradeDirection,
)


class EntryZone(StrictModel):
    """Price band for a proposed entry."""

    low: Decimal
    high: Decimal

    @model_validator(mode="after")
    def _low_lte_high(self) -> EntryZone:
        if self.low > self.high:
            raise ValueError("EntryZone.low must be <= EntryZone.high")
        return self


class StrategySignal(ORMModel):
    """Structured, deterministic output of a strategy module.

    LLMs may explain a signal, but never generate it — detection is code-driven
    (Architecture §10).
    """

    id: UUID | None = None
    strategy_id: StrategyId
    setup_id: UUID | None = None
    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    confidence: Confidence
    entry_zone: EntryZone | None = None
    invalidation: str = Field(description="Condition under which the signal is void.")
    evidence: list[str] = Field(default_factory=list, description="Human-readable signal evidence.")
    risk_notes: list[str] = Field(default_factory=list)
    timestamp: datetime


class SetupDefinition(ORMModel):
    """A versioned, trackable trading setup definition (Architecture §11)."""

    id: UUID
    name: str
    strategy_id: StrategyId
    category: SetupCategory
    version: int = Field(ge=1)
    enabled: bool = True
    rules: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    created_at: datetime


class StrategyEvaluateRequest(StrictModel):
    """HTTP request to evaluate a strategy module with market context."""

    strategy_id: StrategyId
    symbol: Symbol
    timeframe: Timeframe
    close: Decimal
    volume: Decimal = Field(gt=0)
    funding_rate: Decimal | None = None
    rsi: float | None = Field(default=None, ge=0, le=100)
    ema_fast: Decimal | None = None
    ema_slow: Decimal | None = None
    htf_trend: TradeDirection | None = None
    liquidity_sweep_detected: bool = False
    momentum_exhausted: bool = False
    at_confluence_level: bool = False
    green_day_active: bool = False
    stress_score: int | None = Field(default=None, ge=0, le=10)


class StrategyEvaluateResponse(ORMModel):
    strategy_id: StrategyId
    signal: StrategySignal | None


class SetupPerformance(ORMModel):
    """Aggregated performance for a setup, separate from total account PnL."""

    setup_id: UUID
    trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    expectancy: Decimal
    avg_pnl: Decimal
    avg_stress: float | None = Field(default=None, ge=0, le=10)
    updated_at: datetime
