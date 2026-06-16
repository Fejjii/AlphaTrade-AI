"""User strategy library and strategy card schemas (Slice 33)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    BacktestStatus,
    MarketType,
    ORMModel,
    PaperValidationStatus,
    StrategyId,
    StrategyValidationStatus,
    StrictModel,
    Timeframe,
)


class StrategyCard(StrictModel):
    """Structured strategy card per v5 brief."""

    strategy_name: str = Field(min_length=1, max_length=120)
    market_type: MarketType = MarketType.CRYPTO_PERP
    asset_universe: list[str] = Field(default_factory=list)
    timeframes: list[Timeframe] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    confirmation_conditions: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    stop_loss: list[str] = Field(default_factory=list)
    take_profit_plan: list[str] = Field(default_factory=list)
    runner_plan: list[str] = Field(default_factory=list)
    position_sizing: list[str] = Field(default_factory=list)
    add_rules: list[str] = Field(default_factory=list)
    no_trade_rules: list[str] = Field(default_factory=list)
    backtest_rules: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    validation_status: StrategyValidationStatus = StrategyValidationStatus.DRAFT

    @model_validator(mode="after")
    def _require_core_fields(self) -> StrategyCard:
        if not self.entry_conditions:
            raise ValueError("entry_conditions must not be empty")
        if not self.invalidation:
            raise ValueError("invalidation must not be empty")
        if not self.stop_loss:
            raise ValueError("stop_loss must not be empty")
        return self


class UserStrategyVersion(ORMModel):
    id: UUID
    strategy_id: UUID
    version: int = Field(ge=1)
    card: StrategyCard
    validation_status: StrategyValidationStatus
    backtest_status: BacktestStatus
    paper_validation_status: PaperValidationStatus
    created_at: datetime


class UserStrategy(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    name: str
    setup_type: StrategyId
    current_version: int = Field(ge=1)
    enabled: bool = True
    notes: str | None = None
    latest_card: StrategyCard | None = None
    validation_status: StrategyValidationStatus | None = None
    backtest_status: BacktestStatus | None = None
    paper_validation_status: PaperValidationStatus | None = None
    created_at: datetime
    updated_at: datetime


class UserStrategyCreate(StrictModel):
    organization_id: UUID
    user_id: UUID
    name: str = Field(min_length=1, max_length=120)
    setup_type: StrategyId
    card: StrategyCard
    notes: str | None = Field(default=None, max_length=4000)


class StrategyLibraryCreate(StrictModel):
    """HTTP body for creating a user strategy (tenant injected by API)."""

    name: str = Field(min_length=1, max_length=120)
    setup_type: StrategyId
    card: StrategyCard
    notes: str | None = Field(default=None, max_length=4000)


class UserStrategyUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    setup_type: StrategyId | None = None
    enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)
    card: StrategyCard | None = None


class UserStrategyVersionCreate(StrictModel):
    card: StrategyCard
    validation_status: StrategyValidationStatus | None = None


class PaginatedUserStrategies(StrictModel):
    items: list[UserStrategy]
    total: int
    limit: int
    offset: int


class PaginatedUserStrategyVersions(StrictModel):
    items: list[UserStrategyVersion]
    total: int
    limit: int
    offset: int
