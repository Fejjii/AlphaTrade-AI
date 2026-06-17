"""Paper validation alert schemas (Slice 40)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    ORMModel,
    PaperAlertSeverity,
    PaperAlertSource,
    PaperAlertType,
    StrictModel,
)


class PaperAlert(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID | None = None
    alert_type: PaperAlertType
    severity: PaperAlertSeverity
    strategy_id: UUID | None = None
    paper_validation_run_id: UUID | None = None
    paper_trade_id: UUID | None = None
    message: str
    read_at: datetime | None = None
    metadata: dict | None = None
    alert_source: PaperAlertSource = PaperAlertSource.PAPER_VALIDATION_RUNTIME
    delivery_status: AlertDeliveryStatus = AlertDeliveryStatus.DISABLED
    delivery_channel: AlertDeliveryChannel = AlertDeliveryChannel.IN_APP
    delivery_attempts: int = 0
    last_delivery_error: str | None = None
    delivered_at: datetime | None = None
    next_retry_at: datetime | None = None
    delivery_skipped_reason: str | None = None
    retry_exhausted: bool = False
    created_at: datetime
    updated_at: datetime


class PaperAlertSummary(StrictModel):
    total: int
    unread: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)


class PaginatedPaperAlerts(StrictModel):
    items: list[PaperAlert]
    total: int
    limit: int
    offset: int
