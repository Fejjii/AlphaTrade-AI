"""Telegram alert delivery provider (Slice 46 — disabled by default, paper only)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.core.config import Settings
from app.guardrails.redaction import redact_text
from app.providers.alert_delivery.base import AlertDeliveryPayload, AlertDeliveryResult
from app.schemas.common import AlertDeliveryChannel


def _mask_chat_id(chat_id: str) -> str:
    if len(chat_id) <= 4:
        return "***"
    return f"***{chat_id[-4:]}"


class TelegramAlertDeliveryProvider:
    channel = AlertDeliveryChannel.TELEGRAM

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
            and self._settings.telegram_alerts_enabled
            and bool(self._settings.telegram_bot_token.strip())
        )

    def is_configured(self) -> bool:
        return bool(self._settings.telegram_bot_token.strip())

    def deliver(
        self,
        payload: AlertDeliveryPayload,
        *,
        bypass_enable_check: bool = False,
    ) -> AlertDeliveryResult:
        if not bypass_enable_check and not self.is_enabled():
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error="Telegram delivery disabled.",
                skipped=True,
            )
        if bypass_enable_check and not self.is_configured():
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error="Telegram bot token not configured.",
                skipped=True,
            )

        chat_id = (payload.telegram_chat_id or self._settings.telegram_chat_id or "").strip()
        if not chat_id:
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error="Telegram chat id not configured.",
                skipped=True,
            )

        token = self._settings.telegram_bot_token.strip()
        prefix = "[TEST] " if payload.is_test else ""
        text = (
            f"{prefix}AlphaTrade alert ({payload.severity})\n"
            f"Type: {payload.alert_type}\n"
            f"{payload.message}\n"
            f"Paper only — no trade executed."
        )
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = {"chat_id": chat_id, "text": text}
        try:
            response = self._http_post(
                url,
                json=body,
                timeout=self._settings.telegram_timeout_seconds,
            )
            if response.status_code >= 400:
                masked = _mask_chat_id(chat_id)
                return AlertDeliveryResult(
                    success=False,
                    channel=self.channel,
                    error=redact_text(f"Telegram HTTP {response.status_code} for chat {masked}"),
                )
            return AlertDeliveryResult(success=True, channel=self.channel)
        except Exception as exc:
            error = redact_text(str(exc))
            if token and token in error:
                error = error.replace(token, "***REDACTED***")
            if chat_id in error:
                error = error.replace(chat_id, _mask_chat_id(chat_id))
            return AlertDeliveryResult(
                success=False,
                channel=self.channel,
                error=error,
            )
