"""HTTP schemas for the paper-only Watcher runtime status endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

WATCHER_PAPER_ACTIVATION_REQUIREMENTS: tuple[str, ...] = (
    "WATCHER_ORCHESTRATION_ENABLED remains false in staging and production",
    "Local paper enablement only (ENVIRONMENT=local, EXECUTION_MODE=paper)",
    "ENABLE_REAL_TRADING stays false; no real exchange credentials",
    "At least one tenant-scoped APPROVED or ACTIVE compiled strategy",
    "Read-only perpetual evidence (replay default, or binance_usdm)",
    "Dedicated paper Watcher process or local autostart",
    "Telegram stays disabled; Watcher never places orders",
)


class WatcherPaperScopeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_scope: str
    symbol: str
    health_state: str
    lease_owner: str | None = None
    last_reason_code: str
    candidate_ids: list[str] = Field(default_factory=list)


class WatcherPaperRuntimeStatus(BaseModel):
    """Operator/tenant visibility for paper Watcher monitoring. No secrets."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    running: bool
    worker_id: str | None = None
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT"])
    poll_interval_seconds: float
    max_scopes_per_cycle: int
    paper_only: bool = True
    real_trading_enabled: bool = False
    telegram_enabled: bool = False
    kill_switch_active: bool = False
    last_cycle_at: datetime | None = None
    last_reason_code: str = "idle"
    cycles_completed: int = 0
    scans_succeeded: int = 0
    scans_failed: int = 0
    scans_skipped: int = 0
    scans_blocked: int = 0
    candidates_created: int = 0
    scopes: list[WatcherPaperScopeStatus] = Field(default_factory=list)
    remaining_activation_requirements: list[str] = Field(
        default_factory=lambda: list(WATCHER_PAPER_ACTIVATION_REQUIREMENTS)
    )
