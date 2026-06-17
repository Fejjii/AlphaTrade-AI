"""Notification preferences schemas (Slice 46)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import (
    NotificationDigestMode,
    PaperAlertSeverity,
    PaperAlertType,
    StrictModel,
)


class NotificationPreferencesResponse(StrictModel):
    organization_id: UUID
    user_id: UUID
    in_app_enabled: bool = True
    webhook_enabled: bool = False
    telegram_enabled: bool = False
    min_severity: PaperAlertSeverity = PaperAlertSeverity.INFO
    enabled_alert_types: list[PaperAlertType] | None = None
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str = "UTC"
    digest_mode: NotificationDigestMode = NotificationDigestMode.IMMEDIATE
    telegram_chat_id: str | None = None
    using_defaults: bool = False
    timezone_fallback: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationPreferencesUpdate(StrictModel):
    in_app_enabled: bool | None = None
    webhook_enabled: bool | None = None
    telegram_enabled: bool | None = None
    min_severity: PaperAlertSeverity | None = None
    enabled_alert_types: list[PaperAlertType] | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    digest_mode: NotificationDigestMode | None = None
    telegram_chat_id: str | None = None

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_quiet_hour(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = value.strip().split(":")
        if len(parts) != 2:
            raise ValueError("Quiet hours must use HH:MM format.")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Quiet hours must use HH:MM format.")
        return f"{hour:02d}:{minute:02d}"


class ChannelProviderStatus(StrictModel):
    channel: str
    env_enabled: bool
    user_enabled: bool
    configured: bool
    available: bool
    status_label: str


class NotificationTestResult(StrictModel):
    success: bool
    message: str
    channels_attempted: list[str] = Field(default_factory=list)
    channels_succeeded: list[str] = Field(default_factory=list)
    channels_skipped: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
    paper_only: bool = True
    test_label: str = "[TEST] AlphaTrade notification — no trade executed."
