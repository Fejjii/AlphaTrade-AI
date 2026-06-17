"""Delivery routing for external alert channels (Slice 46)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.providers.alert_delivery.base import AlertDeliveryProvider
from app.schemas.common import AlertDeliveryChannel, PaperAlertSeverity, PaperAlertType
from app.schemas.notifications import NotificationPreferencesResponse

_SEVERITY_RANK: dict[PaperAlertSeverity, int] = {
    PaperAlertSeverity.INFO: 0,
    PaperAlertSeverity.WARNING: 1,
    PaperAlertSeverity.CRITICAL: 2,
}


@dataclass(frozen=True)
class DeliveryRoutingResult:
    should_deliver: bool
    selected_channels: list[AlertDeliveryChannel]
    skipped_reason: str | None
    limitations: list[str] = field(default_factory=list)


def _in_quiet_hours(
    *,
    now: datetime,
    timezone_name: str,
    start: str | None,
    end: str | None,
) -> bool:
    if not start or not end:
        return False
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    local = now.astimezone(tz)
    start_parts = [int(p) for p in start.split(":")]
    end_parts = [int(p) for p in end.split(":")]
    start_minutes = start_parts[0] * 60 + start_parts[1]
    end_minutes = end_parts[0] * 60 + end_parts[1]
    current_minutes = local.hour * 60 + local.minute
    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def _provider_configured(channel: AlertDeliveryChannel, settings: Settings) -> bool:
    if channel == AlertDeliveryChannel.WEBHOOK:
        return bool(settings.alert_webhook_url.strip())
    if channel == AlertDeliveryChannel.TELEGRAM:
        return bool(settings.telegram_bot_token.strip())
    return False


def _provider_env_enabled(channel: AlertDeliveryChannel, settings: Settings) -> bool:
    if channel == AlertDeliveryChannel.WEBHOOK:
        return settings.alert_webhook_enabled
    if channel == AlertDeliveryChannel.TELEGRAM:
        return settings.telegram_alerts_enabled
    if channel == AlertDeliveryChannel.EMAIL:
        return settings.email_alerts_enabled
    return False


def route_alert_delivery(
    *,
    settings: Settings,
    preferences: NotificationPreferencesResponse,
    providers: list[AlertDeliveryProvider],
    severity: PaperAlertSeverity,
    alert_type: PaperAlertType,
    now: datetime,
) -> DeliveryRoutingResult:
    limitations: list[str] = []
    if not settings.alert_delivery_enabled:
        return DeliveryRoutingResult(
            should_deliver=False,
            selected_channels=[AlertDeliveryChannel.IN_APP],
            skipped_reason="External delivery disabled globally.",
            limitations=["ALERT_DELIVERY_ENABLED=false"],
        )

    if preferences.digest_mode.value == "disabled":
        return DeliveryRoutingResult(
            should_deliver=False,
            selected_channels=[AlertDeliveryChannel.IN_APP],
            skipped_reason="External delivery disabled in user preferences.",
        )

    if preferences.digest_mode.value == "daily_digest":
        limitations.append("Daily digest mode — external delivery deferred to digest.")
        return DeliveryRoutingResult(
            should_deliver=False,
            selected_channels=[AlertDeliveryChannel.IN_APP],
            skipped_reason="Daily digest mode — immediate external delivery skipped.",
            limitations=limitations,
        )

    min_rank = _SEVERITY_RANK.get(preferences.min_severity, 0)
    alert_rank = _SEVERITY_RANK.get(severity, 0)
    if alert_rank < min_rank:
        return DeliveryRoutingResult(
            should_deliver=False,
            selected_channels=[AlertDeliveryChannel.IN_APP],
            skipped_reason=(
                f"Alert severity {severity.value} below minimum {preferences.min_severity.value}."
            ),
        )

    if preferences.enabled_alert_types:
        allowed = {t.value for t in preferences.enabled_alert_types}
        if alert_type.value not in allowed:
            return DeliveryRoutingResult(
                should_deliver=False,
                selected_channels=[AlertDeliveryChannel.IN_APP],
                skipped_reason=f"Alert type {alert_type.value} not in enabled filters.",
            )

    if preferences.quiet_hours_enabled and _in_quiet_hours(
        now=now,
        timezone_name=preferences.timezone,
        start=preferences.quiet_hours_start,
        end=preferences.quiet_hours_end,
    ):
        return DeliveryRoutingResult(
            should_deliver=False,
            selected_channels=[AlertDeliveryChannel.IN_APP],
            skipped_reason="Quiet hours active — external delivery skipped.",
        )

    selected: list[AlertDeliveryChannel] = [AlertDeliveryChannel.IN_APP]
    for channel in (AlertDeliveryChannel.WEBHOOK, AlertDeliveryChannel.TELEGRAM):
        user_enabled = (
            preferences.webhook_enabled
            if channel == AlertDeliveryChannel.WEBHOOK
            else preferences.telegram_enabled
        )
        if not user_enabled:
            continue
        if not _provider_env_enabled(channel, settings):
            limitations.append(f"{channel.value} disabled in environment.")
            continue
        if not _provider_configured(channel, settings):
            limitations.append(f"{channel.value} not configured in environment.")
            continue
        provider = next((p for p in providers if p.channel == channel), None)
        if provider is None or not provider.is_enabled():
            limitations.append(f"{channel.value} provider unavailable.")
            continue
        selected.append(channel)

    external = [c for c in selected if c is not AlertDeliveryChannel.IN_APP]
    if not external:
        reason = "No external channels enabled or configured."
        if limitations:
            reason = f"{reason} ({'; '.join(limitations)})"
        return DeliveryRoutingResult(
            should_deliver=False,
            selected_channels=selected,
            skipped_reason=reason,
            limitations=limitations,
        )

    return DeliveryRoutingResult(
        should_deliver=True,
        selected_channels=selected,
        skipped_reason=None,
        limitations=limitations,
    )
