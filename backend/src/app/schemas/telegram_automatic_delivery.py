"""Automatic Telegram delivery readiness and preview schemas (Slice 71)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import PaperAlertSeverity, PaperAlertType, StrictModel

PreviewItemStatus = Literal["eligible", "skipped", "already_delivered"]


class DeliveryLimits(StrictModel):
    """Operator-safe limits for preview and future automatic delivery."""

    max_preview_limit: int = 25
    default_preview_limit: int = 5
    max_automatic_batch_limit: int = 10


class AlertDeliveryPreviewRequest(StrictModel):
    channel: Literal["telegram"] = "telegram"
    limit: int = Field(default=5, ge=1, le=25)
    severity_min: PaperAlertSeverity = PaperAlertSeverity.INFO


class AlertDeliveryPreviewItem(StrictModel):
    alert_id: UUID
    alert_type: PaperAlertType
    severity: PaperAlertSeverity
    message_preview: str
    created_at: datetime
    status: PreviewItemStatus
    reason: str | None = None


class AlertDeliveryPreviewResponse(StrictModel):
    channel: str = "telegram"
    eligible_count: int
    skipped_count: int
    already_delivered_count: int
    items: list[AlertDeliveryPreviewItem]
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
