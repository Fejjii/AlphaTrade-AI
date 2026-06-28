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
    SetupAlertReviewStatus,
    StrictModel,
)

SETUP_ALERT_REVIEW_NOTES_MAX = 4000


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


class SetupAlertReviewItem(StrictModel):
    alert_id: UUID
    created_at: datetime
    symbol: str | None = None
    timeframe: str | None = None
    condition: str | None = None
    direction: str | None = None
    confidence: float | None = None
    reason: str | None = None
    trigger_level: float | None = None
    invalidation_level: float | None = None
    latest_price: float | None = None
    delivery_channel: AlertDeliveryChannel
    delivery_status: AlertDeliveryStatus
    dedupe_key: str | None = None
    review_status: SetupAlertReviewStatus
    review_notes: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None
    metadata: dict | None = None


class PaginatedSetupAlertReview(StrictModel):
    items: list[SetupAlertReviewItem]
    total: int
    limit: int
    offset: int


class SetupAlertReviewUpdate(StrictModel):
    review_status: SetupAlertReviewStatus
    review_notes: str | None = Field(default=None, max_length=SETUP_ALERT_REVIEW_NOTES_MAX)


class SetupAlertReviewSummaryItem(StrictModel):
    alert_id: UUID
    symbol: str | None = None
    condition: str | None = None
    confidence: float | None = None
    created_at: datetime


class SetupAlertReviewSummary(StrictModel):
    total_unreviewed: int
    total_watching: int
    total_important: int
    total_ignored: int
    by_condition: dict[str, int] = Field(default_factory=dict)
    by_symbol: dict[str, int] = Field(default_factory=dict)
    latest_created_at: datetime | None = None
    highest_confidence_alerts: list[SetupAlertReviewSummaryItem] = Field(default_factory=list)
