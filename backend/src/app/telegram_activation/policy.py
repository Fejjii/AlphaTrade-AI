"""Paper-activation defaults. These do not arm Telegram."""

from __future__ import annotations

from datetime import timedelta

from app.telegram_security.backoff import DeliveryBackoff

WEBHOOK_SECRET_MIN_LENGTH = 32
WEBHOOK_HEADER = "x-telegram-bot-api-secret-token"
PAPER_ACTIVATION_BACKOFF = DeliveryBackoff(
    delays=(timedelta(seconds=5), timedelta(seconds=30), timedelta(seconds=120)),
    defer=timedelta(seconds=5),
)
