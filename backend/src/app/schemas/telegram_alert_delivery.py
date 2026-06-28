"""Owner-gated manual Telegram delivery for existing in-app alerts (Slice 70)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel

TelegramAlertDeliveryStatus = Literal[
    "sent",
    "already_delivered",
    "skipped_not_configured",
    "blocked",
    "failed_redacted",
]

TELEGRAM_ALERT_DELIVERY_CONFIRM_PHRASE = "DELIVER_TELEGRAM_ALERT"


class TelegramAlertDeliveryRequest(StrictModel):
    confirm: str = Field(min_length=1, max_length=64)


class TelegramAlertDeliveryResponse(StrictModel):
    status: TelegramAlertDeliveryStatus
    alert_id: UUID
    channel: str = "telegram"
    sent_at: datetime | None = None
    delivery_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
