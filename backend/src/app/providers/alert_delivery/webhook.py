"""Webhook alert delivery provider (Slice 41/42 — disabled by default, signed payloads)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.guardrails.redaction import redact_text
from app.providers.alert_delivery.base import (
    AlertDeliveryPayload,
    AlertDeliveryResult,
)
from app.schemas.common import AlertDeliveryChannel


def _build_signature(secret: str, timestamp: str, body: bytes) -> str:
    message = f"{timestamp}.{body.decode('utf-8')}"
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


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

    def is_configured(self) -> bool:
        return bool(self._settings.alert_webhook_url.strip())

    def deliver(self, payload: AlertDeliveryPayload) -> AlertDeliveryResult:
        if not self.is_enabled():
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error="Webhook delivery disabled.",
                skipped=True,
            )

        event_id = payload.event_id or str(uuid.uuid4())
        idempotency_key = payload.idempotency_key or payload.dedup_key or payload.alert_id
        timestamp = payload.timestamp or datetime.now(UTC).isoformat()

        body_dict = {
            "alert_id": payload.alert_id,
            "event_id": event_id,
            "idempotency_key": idempotency_key,
            "timestamp": timestamp,
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
        body_bytes = json.dumps(body_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-AlphaTrade-Alert-Id": payload.alert_id,
            "X-AlphaTrade-Event-Id": event_id,
            "X-AlphaTrade-Idempotency-Key": idempotency_key,
            "X-AlphaTrade-Timestamp": timestamp,
        }
        secret = self._settings.alert_webhook_secret.strip()
        if secret:
            headers["X-AlphaTrade-Signature"] = _build_signature(secret, timestamp, body_bytes)

        webhook_url = self._settings.alert_webhook_url.strip()
        try:
            response = self._http_post(
                webhook_url,
                content=body_bytes,
                headers=headers,
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
            error = redact_text(str(exc))
            if webhook_url in error:
                error = error.replace(webhook_url, "***REDACTED***")
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error=error,
            )
