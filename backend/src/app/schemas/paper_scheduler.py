"""Paper validation scheduler and runtime history schemas (Slice 40)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ORMModel,
    PaperRuntimeCycleMode,
    PaperRuntimeCycleStatus,
    StrictModel,
)


class PaperSchedulerConfig(StrictModel):
    enabled: bool = False
    interval_seconds: int = Field(default=300, ge=60, le=86400)
    max_runs_per_cycle: int = Field(default=5, ge=1, le=50)
    max_scans_per_minute: int = Field(default=10, ge=1, le=120)


class PaperSchedulerConfigUpdate(StrictModel):
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=60, le=86400)
    max_runs_per_cycle: int | None = Field(default=None, ge=1, le=50)
    max_scans_per_minute: int | None = Field(default=None, ge=1, le=120)


class PaperSchedulerStatus(StrictModel):
    env_enabled: bool
    tenant_enabled: bool
    effective_enabled: bool
    config: PaperSchedulerConfig
    last_tick_at: datetime | None = None
    last_tick_status: str | None = None
    real_trading_enabled: bool = False
    limitation: str = (
        "Paper validation scheduler is optional and disabled by default. "
        "All execution remains paper only — no exchange orders."
    )


class PaperRuntimeHistoryRecord(ORMModel):
    id: UUID
    organization_id: UUID
    run_id: UUID | None = None
    strategy_id: UUID | None = None
    symbol: str | None = None
    mode: PaperRuntimeCycleMode
    started_at: datetime
    completed_at: datetime | None = None
    status: PaperRuntimeCycleStatus
    reason: str | None = None
    signals_created: int = 0
    trades_opened: int = 0
    trades_closed: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data_freshness: str | None = None
    latency_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedPaperRuntimeHistory(StrictModel):
    items: list[PaperRuntimeHistoryRecord]
    total: int
    limit: int
    offset: int


class PaperSchedulerTickResult(StrictModel):
    ticked_at: datetime
    env_enabled: bool
    effective_enabled: bool
    runs_processed: int = 0
    runs_skipped: int = 0
    scans_executed: int = 0
    ticks_executed: int = 0
    alerts_created: int = 0
    decisions: list[str] = Field(default_factory=list)
    limitation: str = "Manual scheduler tick — paper only, no real trading."


class PaperValidationSampleWindow(ORMModel):
    id: UUID
    paper_validation_run_id: UUID
    organization_id: UUID
    window_start: datetime
    window_end: datetime
    trades_count: int
    win_rate: float
    net_pnl: str
    max_drawdown: float
    expectancy: str
    recommendation: str | None = None
    data_quality: str | None = None
    created_at: datetime
    updated_at: datetime
