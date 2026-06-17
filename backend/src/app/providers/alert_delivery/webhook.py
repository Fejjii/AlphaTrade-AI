"""Webhook alert delivery provider (Slice 41 — disabled by default)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.core.config import Settings
from app.guardrails.redaction import redact_text
from app.providers.alert_delivery.base import (
    AlertDeliveryPayload,
    AlertDeliveryResult,
)
from app.schemas.common import AlertDeliveryChannel


class WebhookAlertDeliveryProvider:
    channel = AlertDeliveryChannel.WEBHOOK

    def __init__(
        self,
        settings: Settings,
        *,
        http_post: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self._settings = settings
        self._http_post = http_post or httpx.post

    def is_enabled(self) -> bool:
        return (
            self._settings.alert_delivery_enabled
            and self._settings.alert_webhook_enabled
            and bool(self._settings.alert_webhook_url.strip())
        )

    def deliver(self, payload: AlertDeliveryPayload) -> AlertDeliveryResult:
        if not self.is_enabled():
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error="Webhook delivery disabled.",
                skipped=True,
            )
        body = {
            "alert_id": payload.alert_id,
            "organization_id": payload.organization_id,
            "alert_type": payload.alert_type,
            "severity": payload.severity,
            "message": payload.message,
            "strategy_id": payload.strategy_id,
            "paper_validation_run_id": payload.paper_validation_run_id,
            "paper_trade_id": payload.paper_trade_id,
            "dedup_key": payload.dedup_key,
            "metadata": payload.metadata,
            "paper_only": True,
        }
        try:
            response = self._http_post(
                self._settings.alert_webhook_url.strip(),
                json=body,
                timeout=self._settings.alert_webhook_timeout_seconds,
            )
            if response.status_code >= 400:
                return AlertDeliveryResult(
                    success=False,
                    channel=self.channel,
                    error=redact_text(f"Webhook HTTP {response.status_code}"),
                )
            return AlertDeliveryResult(success=True, channel=self.channel)
        except Exception as exc:
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error=redact_text(str(exc)),
            )
