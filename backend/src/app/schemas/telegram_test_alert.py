"""Owner-gated Telegram manual test alert schemas (Slice 69)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import StrictModel

TelegramTestAlertStatus = Literal[
    "sent",
    "skipped_not_configured",
    "blocked",
    "failed_redacted",
]

TELEGRAM_TEST_CONFIRM_PHRASE = "SEND_TEST_TELEGRAM"


class TelegramTestAlertRequest(StrictModel):
    confirm: str = Field(min_length=1, max_length=64)
    message: str | None = Field(default=None, max_length=200)


class TelegramTestAlertResponse(StrictModel):
    status: TelegramTestAlertStatus
    telegram_configured: bool
    chat_configured: bool
    paper_only: bool = True
    external_delivery_enabled: bool
    sent_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
