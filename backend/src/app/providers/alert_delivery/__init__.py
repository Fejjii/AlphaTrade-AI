"""Alert delivery provider registry (Slice 41)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.core.config import Settings, get_settings
from app.providers.alert_delivery.base import AlertDeliveryProvider
from app.providers.alert_delivery.in_app import InAppAlertDeliveryProvider
from app.providers.alert_delivery.stubs import (
    EmailAlertDeliveryProvider,
    PushAlertDeliveryProvider,
)
from app.providers.alert_delivery.telegram import TelegramAlertDeliveryProvider
from app.providers.alert_delivery.webhook import WebhookAlertDeliveryProvider


def build_alert_delivery_providers(
    settings: Settings | None = None,
    *,
    http_post: Callable[..., httpx.Response] | None = None,
) -> list[AlertDeliveryProvider]:
    cfg = settings or get_settings()
    return [
        InAppAlertDeliveryProvider(),
        WebhookAlertDeliveryProvider(cfg, http_post=http_post),
        TelegramAlertDeliveryProvider(cfg, http_post=http_post),
        EmailAlertDeliveryProvider(cfg),
        PushAlertDeliveryProvider(cfg),
    ]
