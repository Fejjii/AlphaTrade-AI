"""Outbound-only worker system notifier (Telegram/webhook).

Sends system-level alerts (setup detected, worker error, daily summary) to the
configured channels. It is strictly one-directional: there is no inbound command
path, and notifications can never trigger trades. Severity thresholds and quiet
hours are enforced with pure helpers so behavior is deterministic and testable.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from app.core.config import Settings
from app.providers.alert_delivery import build_alert_delivery_providers
from app.providers.alert_delivery.base import AlertDeliveryPayload, AlertDeliveryProvider
from app.schemas.common import AlertDeliveryChannel, PaperAlertSeverity, PaperAlertType
from app.workers.summary import DailySummary

logger = structlog.get_logger(__name__)

_SEVERITY_RANK = {
    PaperAlertSeverity.INFO: 0,
    PaperAlertSeverity.WARNING: 1,
    PaperAlertSeverity.CRITICAL: 2,
}


def passes_min_severity(severity: PaperAlertSeverity, minimum: str) -> bool:
    """True when ``severity`` meets or exceeds the configured minimum."""
    try:
        floor = PaperAlertSeverity(minimum.strip().lower())
    except ValueError:
        floor = PaperAlertSeverity.INFO
    return _SEVERITY_RANK[severity] >= _SEVERITY_RANK[floor]


def _parse_hhmm(value: str) -> int | None:
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        return None
    return hours * 60 + minutes


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    """True when ``now`` (UTC) falls inside the quiet-hours window.

    Supports windows that wrap past midnight (e.g. 22:00-06:00). Empty/invalid
    bounds disable quiet hours.
    """
    start_min = _parse_hhmm(start)
    end_min = _parse_hhmm(end)
    if start_min is None or end_min is None or start_min == end_min:
        return False
    now_min = now.hour * 60 + now.minute
    if start_min < end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min  # wraps midnight


class WorkerNotifier:
    """Delivers system alerts to enabled external channels (no inbound path)."""

    def __init__(
        self,
        settings: Settings,
        *,
        providers: list[AlertDeliveryProvider] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._providers = providers or build_alert_delivery_providers(settings)
        self._clock = clock

    def notify(
        self,
        *,
        alert_type: PaperAlertType,
        severity: PaperAlertSeverity,
        message: str,
        metadata: dict | None = None,
    ) -> bool:
        """Deliver one alert; returns True if any channel delivered it."""
        if not (self._settings.worker_alerts_enabled and self._settings.alert_delivery_enabled):
            return False
        if not passes_min_severity(severity, self._settings.worker_alert_min_severity):
            return False
        # Critical alerts bypass quiet hours; everything else respects them.
        if severity is not PaperAlertSeverity.CRITICAL and in_quiet_hours(
            self._clock(),
            self._settings.worker_quiet_hours_start,
            self._settings.worker_quiet_hours_end,
        ):
            return False

        payload = AlertDeliveryPayload(
            alert_id=f"worker:{uuid.uuid4().hex}",
            organization_id="system",
            alert_type=alert_type.value,
            severity=severity.value,
            message=message,
            metadata=metadata or {"paper_only": True},
            event_id=str(uuid.uuid4()),
            idempotency_key=f"worker-alert:{alert_type.value}:{self._clock().isoformat()}",
            timestamp=self._clock().isoformat(),
            telegram_chat_id=self._settings.telegram_chat_id or None,
        )

        delivered = False
        for provider in self._providers:
            if provider.channel is AlertDeliveryChannel.IN_APP or not provider.is_enabled():
                continue
            try:
                outcome = provider.deliver(payload)
            except Exception:  # a notifier must never break the worker loop
                logger.warning("worker_notify_failed", channel=provider.channel.value)
                continue
            delivered = delivered or outcome.success
        return delivered

    def notify_setup_detected(self, *, count: int, detail: str | None = None) -> bool:
        message = f"{count} setup(s) detected in the latest scan. Paper only — no trade executed."
        if detail:
            message = f"{message}\n{detail}"
        return self.notify(
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            severity=PaperAlertSeverity.INFO,
            message=message,
        )

    def notify_worker_error(self, error: str) -> bool:
        return self.notify(
            alert_type=PaperAlertType.STRATEGY_BLOCKED,
            severity=PaperAlertSeverity.WARNING,
            message=f"Worker scan cycle failed: {error}",
        )

    def notify_daily_summary(self, summary: DailySummary) -> bool:
        return self.notify(
            alert_type=PaperAlertType.PROMOTION_STATUS_CHANGED,
            severity=PaperAlertSeverity.INFO,
            message=summary.to_message(),
        )
