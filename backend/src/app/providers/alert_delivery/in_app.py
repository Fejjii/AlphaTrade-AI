"""In-app alert delivery — storage only, no external send (Slice 41)."""

from __future__ import annotations

from app.providers.alert_delivery.base import (
    AlertDeliveryPayload,
    AlertDeliveryResult,
)
from app.schemas.common import AlertDeliveryChannel


class InAppAlertDeliveryProvider:
    channel = AlertDeliveryChannel.IN_APP

    def is_enabled(self) -> bool:
        return True

    def deliver(self, payload: AlertDeliveryPayload) -> AlertDeliveryResult:
        return AlertDeliveryResult(
            success=True,
            channel=self.channel,
            skipped=True,
        )
