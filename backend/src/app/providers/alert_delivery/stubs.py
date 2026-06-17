"""Placeholder alert delivery providers (Slice 41)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.alert_delivery.base import (
    AlertDeliveryPayload,
    AlertDeliveryResult,
)
from app.schemas.common import AlertDeliveryChannel


class _StubAlertDeliveryProvider:
    channel: AlertDeliveryChannel

    def __init__(self, settings: Settings, *, channel: AlertDeliveryChannel, enabled: bool) -> None:
        self._settings = settings
        self.channel = channel
        self._provider_enabled = enabled

    def is_enabled(self) -> bool:
        return self._settings.alert_delivery_enabled and self._provider_enabled

    def deliver(self, payload: AlertDeliveryPayload) -> AlertDeliveryResult:
        return AlertDeliveryResult(
            success=False,
            channel=self.channel,
            error=f"{self.channel.value} delivery not implemented.",
            skipped=True,
        )


class TelegramAlertDeliveryProvider(_StubAlertDeliveryProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            settings,
            channel=AlertDeliveryChannel.TELEGRAM,
            enabled=settings.telegram_alerts_enabled,
        )


class EmailAlertDeliveryProvider(_StubAlertDeliveryProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            settings,
            channel=AlertDeliveryChannel.EMAIL,
            enabled=settings.email_alerts_enabled,
        )


class PushAlertDeliveryProvider(_StubAlertDeliveryProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, channel=AlertDeliveryChannel.PUSH, enabled=False)
