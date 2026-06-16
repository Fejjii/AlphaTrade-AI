"""Historical candle schemas (Slice 35)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import StrictModel, Timeframe


class HistoricalCandle(StrictModel):
    symbol: str
    exchange: str
    timeframe: Timeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str
    is_stale: bool = False
    freshness_note: str | None = None


class HistoricalIngestRequest(StrictModel):
    symbol: str = Field(default="BTCUSDT", min_length=2, max_length=30)
    exchange: str = Field(default="binance", min_length=1, max_length=40)
    timeframe: Timeframe = Timeframe.H4
    start_date: date
    end_date: date


class HistoricalIngestResult(StrictModel):
    symbol: str
    exchange: str
    timeframe: Timeframe
    candles_stored: int
    gaps_detected: int
    is_complete: bool
    freshness_note: str | None = None
    limitations: list[str] = Field(default_factory=list)


class HistoricalCandleQuery(StrictModel):
    symbol: str
    exchange: str
    timeframe: Timeframe
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=500, ge=1, le=5000)


class HistoricalCandleList(StrictModel):
    items: list[HistoricalCandle]
    total: int
    gaps_detected: int = 0
    limitations: list[str] = Field(default_factory=list)
