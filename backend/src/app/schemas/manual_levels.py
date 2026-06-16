"""Manual chart level schemas (Slice 33)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    ManualLevelType,
    ORMModel,
    StrictModel,
    Symbol,
    Timeframe,
)


class ManualChartLevel(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    symbol: Symbol
    exchange: str
    timeframe: Timeframe | None = None
    level_type: ManualLevelType
    price: Decimal | None = None
    price_low: Decimal | None = None
    price_high: Decimal | None = None
    label: str | None = None
    notes: str | None = None
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class ManualChartLevelCreate(StrictModel):
    organization_id: UUID
    user_id: UUID
    symbol: Symbol
    exchange: str = Field(min_length=1, max_length=40)
    timeframe: Timeframe | None = None
    level_type: ManualLevelType
    price: Decimal | None = None
    price_low: Decimal | None = None
    price_high: Decimal | None = None
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_prices(self) -> ManualChartLevelCreate:
        if self.price is None and self.price_low is None and self.price_high is None:
            raise ValueError("Provide price or price_low/price_high for the level.")
        if (
            self.price_low is not None
            and self.price_high is not None
            and self.price_low > self.price_high
        ):
            raise ValueError("price_low must be <= price_high")
        return self


class ManualLevelCreate(StrictModel):
    """HTTP body for manual level create (tenant injected by API)."""

    symbol: Symbol
    exchange: str = Field(min_length=1, max_length=40)
    timeframe: Timeframe | None = None
    level_type: ManualLevelType
    price: Decimal | None = None
    price_low: Decimal | None = None
    price_high: Decimal | None = None
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_prices(self) -> ManualLevelCreate:
        if self.price is None and self.price_low is None and self.price_high is None:
            raise ValueError("Provide price or price_low/price_high for the level.")
        if (
            self.price_low is not None
            and self.price_high is not None
            and self.price_low > self.price_high
        ):
            raise ValueError("price_low must be <= price_high")
        return self


class ManualChartLevelUpdate(StrictModel):
    symbol: Symbol | None = None
    exchange: str | None = Field(default=None, min_length=1, max_length=40)
    timeframe: Timeframe | None = None
    level_type: ManualLevelType | None = None
    price: Decimal | None = None
    price_low: Decimal | None = None
    price_high: Decimal | None = None
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None


class PaginatedManualChartLevels(StrictModel):
    items: list[ManualChartLevel]
    total: int
    limit: int
    offset: int
