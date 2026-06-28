"""Market watcher schemas (Slice 41 — read-only; Slice 72 — scanner)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import MarketWatcherObservationStatus, StrictModel

SCAN_CONFIRM_PHRASE = "RUN_READ_ONLY_SCAN"
CREATE_IN_APP_ALERTS_CONFIRM_PHRASE = "CREATE_IN_APP_ALERTS_ONLY"

MarketWatcherReadiness = Literal["ready", "degraded", "blocked"]
MarketWatcherScanStatus = Literal["ok", "blocked", "degraded"]


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


class MarketWatcherScanRequest(StrictModel):
    confirm: str
    create_in_app_alerts_confirm: str | None = None
    symbols: list[str] = Field(
        default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        min_length=1,
        max_length=10,
    )
    timeframes: list[str] = Field(default_factory=lambda: ["15m", "1h"], min_length=1, max_length=5)
    dry_run: bool = True


class MarketWatcherCandidate(StrictModel):
    symbol: str
    timeframe: str
    condition: str
    message: str
    severity: str
    metrics: dict[str, object] = Field(default_factory=dict)
    created_alert_id: UUID | None = None
    deduped: bool = False


class MarketWatcherSummary(StrictModel):
    scanner_enabled: bool
    manual_scan_available: bool
    worker_enabled: bool
    worker_running: bool
    symbols_supported: list[str] = Field(default_factory=list)
    timeframes_supported: list[str] = Field(default_factory=list)
    last_scan_at: datetime | None = None
    last_scan_status: MarketWatcherScanStatus | None = None
    last_scan_alerts_created: int = 0
    last_scan_error: str | None = None
    paper_only: bool = True
    readiness: MarketWatcherReadiness = "ready"
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime


class MarketWatcherScanResult(StrictModel):
    scanned_at: datetime
    env_enabled: bool
    effective_enabled: bool
    symbols_scanned: int
    observations_created: int
    setup_signals: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    paper_only: bool = True
    dry_run: bool = True
    status: MarketWatcherScanStatus = "ok"
    candidates: list[MarketWatcherCandidate] = Field(default_factory=list)
    alerts_created: int = 0
    alerts_deduped: int = 0
    error: str | None = None


class PaginatedMarketWatcherObservations(StrictModel):
    items: list[MarketWatcherObservation]
    total: int
    limit: int
    offset: int


class PaginatedMarketWatcherHistory(StrictModel):
    items: list[MarketWatcherScanResult]
    total: int


class MarketWatcherBridgeStatus(StrictModel):
    env_enabled: bool
    auto_tick_enabled: bool
    effective_enabled: bool
    last_tick_at: datetime | None = None
    last_tick_status: str | None = None
    decisions_last_tick: int = 0
    scans_triggered_last_tick: int = 0
    paper_only: bool = True
    real_trading_enabled: bool = False


class MarketWatcherBridgeDecision(StrictModel):
    id: UUID
    organization_id: UUID
    observation_id: UUID | None = None
    strategy_id: UUID | None = None
    paper_validation_run_id: UUID | None = None
    symbol: str | None = None
    exchange: str | None = None
    timeframe: str | None = None
    decision: str
    reason: str | None = None
    blockers: list[str] = Field(default_factory=list)
    triggered_scan_id: UUID | None = None
    created_alert_id: UUID | None = None
    latency_ms: int | None = None
    created_at: datetime


class MarketWatcherBridgeTickResult(StrictModel):
    ticked_at: datetime
    env_enabled: bool
    effective_enabled: bool
    observations_processed: int = 0
    scans_triggered: int = 0
    decisions: list[str] = Field(default_factory=list)
    paper_only: bool = True


class PaginatedMarketWatcherBridgeHistory(StrictModel):
    items: list[MarketWatcherBridgeDecision]
    total: int
    limit: int
    offset: int
