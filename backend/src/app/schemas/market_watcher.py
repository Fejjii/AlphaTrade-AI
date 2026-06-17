"""Market watcher schemas (Slice 41 — read-only)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import MarketWatcherObservationStatus, StrictModel


class MarketWatcherStatus(StrictModel):
    env_enabled: bool
    effective_enabled: bool
    watched_symbols: list[str] = Field(default_factory=list)
    last_scan_at: datetime | None = None
    paper_only: bool = True
    real_trading_enabled: bool = False


class MarketWatcherObservation(StrictModel):
    id: UUID
    organization_id: UUID
    symbol: str
    exchange: str
    timeframe: str
    observed_at: datetime
    price: Decimal | None = None
    volume: Decimal | None = None
    data_freshness: str | None = None
    status: MarketWatcherObservationStatus
    related_strategy_id: UUID | None = None
    related_paper_validation_run_id: UUID | None = None
    notes: str | None = None
    created_alert_id: UUID | None = None
    created_at: datetime


class MarketWatcherScanResult(StrictModel):
    scanned_at: datetime
    env_enabled: bool
    effective_enabled: bool
    symbols_scanned: int
    observations_created: int
    setup_signals: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    paper_only: bool = True


class PaginatedMarketWatcherObservations(StrictModel):
    items: list[MarketWatcherObservation]
    total: int
    limit: int
    offset: int


class PaginatedMarketWatcherHistory(StrictModel):
    items: list[MarketWatcherScanResult]
    total: int
