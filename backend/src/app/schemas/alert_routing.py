"""Alert routing and market watcher bridge diagnostics schemas (Slice 68)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.telegram_automatic_delivery import DeliveryLimits


class QuietHoursSummary(StrictModel):
    """Operator-safe quiet hours posture."""

    enabled: bool = False
    start: str | None = None
    end: str | None = None
    timezone: str = "UTC"
    source: str = Field(
        default="none",
        description="worker | user | both | none",
    )


class AlertRoutingSummaryResponse(StrictModel):
    """Redacted operator summary of alert routing and bridge readiness."""

    alerts_enabled: bool
    telegram_enabled: bool
    telegram_configured: bool = False
    telegram_chat_configured: bool = False
    manual_test_available: bool = False
    last_test_alert_at: datetime | None = None
    last_test_alert_status: str | None = None
    telegram_alert_delivery_available: bool = False
    telegram_delivered_count: int = 0
    telegram_failed_count: int = 0
    telegram_last_delivery_at: datetime | None = None
    telegram_last_delivery_status: str | None = None
    webhook_enabled: bool
    external_delivery_enabled: bool
    paper_only: bool = True
    quiet_hours: QuietHoursSummary
    severity_filters: list[str] = Field(default_factory=list)
    last_alert_created_at: datetime | None = None
    last_alert_status: str | None = None
    pending_alerts_count: int = 0
    delivered_alerts_count: int = 0
    failed_alerts_count: int = 0
    market_watcher_configured: bool
    market_watcher_running: bool
    bridge_enabled: bool
    bridge_running: bool
    bridge_last_tick_at: datetime | None = None
    bridge_last_decision: str | None = None
    bridge_last_error: str | None = None
    worker_enabled: bool
    worker_running: bool
    readiness: str
    automatic_telegram_delivery_ready: bool = False
    automatic_delivery_blockers: list[str] = Field(default_factory=list)
    eligible_pending_telegram_count: int = 0
    already_delivered_telegram_count: int = 0
    next_delivery_preview_count: int = 0
    delivery_limits: DeliveryLimits = Field(default_factory=DeliveryLimits)
    dry_run_supported: bool = True
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
