"""HTTP models for the paper Watcher watchlist.

Configuration and runtime status are separate responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import StrictModel

MAX_WATCHLIST_SLOTS = 5


class WatcherWatchlistSlotWrite(StrictModel):
    symbol: str = Field(min_length=6, max_length=20)
    enabled: bool


class WatcherWatchlistReplace(StrictModel):
    revision: int = Field(ge=0)
    slots: list[WatcherWatchlistSlotWrite] = Field(max_length=5)


class WatcherWatchlistSlotRead(StrictModel):
    position: int
    symbol: str
    enabled: bool


class WatcherWatchlistConfigurationRead(StrictModel):
    revision: int
    updated_at: datetime
    max_enabled: int = MAX_WATCHLIST_SLOTS
    slots: list[WatcherWatchlistSlotRead]
    paper_only: bool = True


class WatcherSymbolRuntimeRead(StrictModel):
    configuration_revision: int
    observed_at: datetime | None = None
    position: int
    symbol: str
    enabled: bool
    market_source: str
    freshness: str
    last_successful_scan: datetime | None = None
    last_failed_scan: datetime | None = None
    setup_state: str
    strategy_matches: list[str] = Field(default_factory=list)
    alert_state: str
    error_state: str | None = None


class WatcherWatchlistStatusRead(StrictModel):
    configuration_revision: int
    observed_at: datetime
    stale_after_seconds: float
    paper_only: bool = True
    real_trading_enabled: bool = False
    symbols: list[WatcherSymbolRuntimeRead]
