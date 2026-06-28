"""Read-only alert routing and market watcher bridge diagnostics."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import MarketWatcherBridgeDecision, PaperValidationAlert
from app.guardrails.redaction import redact_text
from app.repositories.market_watcher_bridge import MarketWatcherBridgeRepository
from app.repositories.paper_scheduler import PaperAlertRepository
from app.schemas.alert_routing import AlertRoutingSummaryResponse, QuietHoursSummary
from app.schemas.common import MarketWatcherBridgeDecisionType
from app.schemas.market_watcher import MarketWatcherBridgeStatus, MarketWatcherStatus
from app.services.alert_delivery_service import AlertDeliveryService
from app.services.audit_service import AuditService
from app.services.market_watcher_bridge_service import MarketWatcherBridgeService
from app.services.market_watcher_service import MarketWatcherService
from app.services.notifications.preferences_service import NotificationPreferencesService
from app.services.telegram_test_alert_service import (
    TelegramTestAlertService,
    manual_test_available,
)
from app.workers.repository import WorkerHeartbeatRepository

ReadinessLevel = Literal["ready", "degraded", "blocked"]

_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"bot[0-9]{8,}:[A-Za-z0-9_-]+", re.IGNORECASE)

BRIDGE_STALE_MINUTES = 30
WATCHER_STALE_MINUTES = 60
UNSAFE_BRIDGE_DECISIONS = frozenset(
    {
        "execute",
        "place_order",
        "real_trade",
        "mutation",
    }
)


@dataclass
class RoutingDiagnosticsInputs:
    real_trading_enabled: bool
    paper_only: bool
    external_delivery_enabled: bool
    telegram_enabled: bool
    telegram_configured: bool
    telegram_user_enabled: bool
    telegram_chat_configured: bool
    webhook_enabled: bool
    webhook_configured: bool
    worker_enabled: bool
    worker_running: bool
    worker_running_unexpected: bool
    bridge_enabled: bool
    bridge_running: bool
    bridge_paper_only: bool
    bridge_last_decision: str | None
    bridge_last_error: str | None
    failed_alerts_count: int
    pending_alerts_count: int
    delivery_disabled: bool
    warnings: list[str] = field(default_factory=list)


def _redact_operator_message(message: str, settings: Settings) -> str:
    redacted = redact_text(message)
    redacted = _TELEGRAM_BOT_TOKEN_PATTERN.sub("***REDACTED***", redacted)
    for secret in (
        settings.telegram_bot_token,
        settings.alert_webhook_url,
        settings.alert_webhook_secret,
    ):
        token = secret.strip()
        if token and token in redacted:
            redacted = redacted.replace(token, "***REDACTED***")
    return redacted[:200]


def _bridge_suggests_execution(decision: str | None, reason: str | None) -> bool:
    combined = f"{decision or ''} {reason or ''}".lower()
    return any(token in combined for token in UNSAFE_BRIDGE_DECISIONS)


def compute_alert_routing_readiness(inputs: RoutingDiagnosticsInputs) -> ReadinessLevel:
    """Derive operator readiness from alert routing and bridge posture."""
    if inputs.real_trading_enabled:
        return "blocked"
    if inputs.external_delivery_enabled and not inputs.paper_only:
        return "blocked"
    if inputs.worker_running_unexpected:
        return "blocked"
    if inputs.telegram_enabled and not inputs.telegram_configured:
        return "blocked"
    if inputs.telegram_user_enabled and not inputs.telegram_chat_configured:
        return "blocked"
    if inputs.webhook_enabled and not inputs.webhook_configured:
        return "blocked"
    if not inputs.bridge_paper_only:
        return "blocked"
    if _bridge_suggests_execution(inputs.bridge_last_decision, inputs.bridge_last_error):
        return "blocked"

    degraded = False
    if inputs.bridge_enabled and not inputs.bridge_running:
        degraded = True
    if inputs.bridge_last_error:
        degraded = True
    if inputs.failed_alerts_count > 0:
        degraded = True
    if inputs.delivery_disabled and inputs.pending_alerts_count > 0:
        degraded = True
    if inputs.warnings:
        degraded = True

    if degraded:
        return "degraded"

    if (
        not inputs.real_trading_enabled
        and inputs.paper_only
        and (not inputs.external_delivery_enabled or inputs.paper_only)
        and not inputs.worker_running_unexpected
        and inputs.bridge_paper_only
    ):
        return "ready"

    return "degraded"


def _quiet_hours_summary(
    settings: Settings,
    *,
    user_enabled: bool,
    user_start: str | None,
    user_end: str | None,
    user_timezone: str,
) -> QuietHoursSummary:
    worker_enabled = bool(
        settings.worker_quiet_hours_start.strip() and settings.worker_quiet_hours_end.strip()
    )
    if worker_enabled and user_enabled:
        return QuietHoursSummary(
            enabled=True,
            start=settings.worker_quiet_hours_start,
            end=settings.worker_quiet_hours_end,
            timezone="UTC",
            source="both",
        )
    if worker_enabled:
        return QuietHoursSummary(
            enabled=True,
            start=settings.worker_quiet_hours_start,
            end=settings.worker_quiet_hours_end,
            timezone="UTC",
            source="worker",
        )
    if user_enabled:
        return QuietHoursSummary(
            enabled=True,
            start=user_start,
            end=user_end,
            timezone=user_timezone,
            source="user",
        )
    return QuietHoursSummary(enabled=False, source="none")


def _severity_filters(settings: Settings, *, user_min_severity: str) -> list[str]:
    filters = [f"worker: {settings.worker_alert_min_severity}+"]
    filters.append(f"user: {user_min_severity}+")
    return filters


def _worker_running(settings: Settings, session: Session) -> bool:
    if not settings.worker_enabled:
        return False
    heartbeat = WorkerHeartbeatRepository(session).get_by_name(settings.worker_name)
    if heartbeat is None:
        return False
    last_beat = heartbeat.last_beat_at
    if last_beat.tzinfo is None:
        last_beat = last_beat.replace(tzinfo=UTC)
    seconds_since = (datetime.now(UTC) - last_beat).total_seconds()
    liveness_window = settings.worker_scan_interval_seconds * 3
    return seconds_since <= liveness_window and heartbeat.status != "error" and not heartbeat.paused


def _worker_running_unexpectedly(settings: Settings, session: Session) -> bool:
    heartbeat = WorkerHeartbeatRepository(session).get_by_name(settings.worker_name)
    if heartbeat is None:
        return False
    last_beat = heartbeat.last_beat_at
    if last_beat.tzinfo is None:
        last_beat = last_beat.replace(tzinfo=UTC)
    seconds_since = (datetime.now(UTC) - last_beat).total_seconds()
    liveness_window = settings.worker_scan_interval_seconds * 3
    running = (
        seconds_since <= liveness_window and heartbeat.status != "error" and not heartbeat.paused
    )
    return running and not settings.worker_enabled


def _bridge_running(settings: Settings, bridge: MarketWatcherBridgeStatus) -> bool:
    if not settings.market_watcher_bridge_enabled:
        return False
    if settings.market_watcher_bridge_auto_tick:
        return True
    if bridge.last_tick_at is None:
        return False
    last_tick = bridge.last_tick_at
    if last_tick.tzinfo is None:
        last_tick = last_tick.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_tick <= timedelta(minutes=BRIDGE_STALE_MINUTES)


def _market_watcher_running(settings: Settings, watcher: MarketWatcherStatus) -> bool:
    if not settings.market_watcher_enabled:
        return False
    if watcher.last_scan_at is None:
        return False
    last_scan = watcher.last_scan_at
    if last_scan.tzinfo is None:
        last_scan = last_scan.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_scan <= timedelta(minutes=WATCHER_STALE_MINUTES)


def _latest_alert(session: Session, organization_id: uuid.UUID) -> PaperValidationAlert | None:
    rows, total = PaperAlertRepository(session).list_for_org(organization_id, limit=1)
    if total == 0 or not rows:
        return None
    return rows[0]


def _latest_bridge_decision(
    session: Session,
    organization_id: uuid.UUID,
) -> MarketWatcherBridgeDecision | None:
    rows, total = MarketWatcherBridgeRepository(session).list_for_org(organization_id, limit=1)
    if total == 0 or not rows:
        return None
    return rows[0]


def build_alert_routing_summary(
    *,
    settings: Settings,
    session: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AlertRoutingSummaryResponse:
    """Aggregate redacted alert routing and bridge diagnostics for operators."""
    generated_at = datetime.now(UTC)
    warnings: list[str] = []

    delivery = AlertDeliveryService(session, settings)
    delivery_status = delivery.get_status(organization_id=organization_id, user_id=user_id)
    delivery_counts = delivery.delivery_summary(organization_id)
    prefs_service = NotificationPreferencesService(session, AuditService(session))
    prefs = prefs_service.get(organization_id=organization_id, user_id=user_id)

    watcher = MarketWatcherService(session, settings).get_status(
        organization_id=organization_id,
        user_id=user_id,
    )
    bridge_service = MarketWatcherBridgeService(session, settings)
    bridge = bridge_service.get_status(organization_id=organization_id)
    latest_alert = _latest_alert(session, organization_id)
    latest_bridge = _latest_bridge_decision(session, organization_id)

    worker_running = _worker_running(settings, session)
    worker_unexpected = _worker_running_unexpectedly(settings, session)
    bridge_running = _bridge_running(settings, bridge)
    watcher_running = _market_watcher_running(settings, watcher)

    bridge_last_decision = latest_bridge.decision.value if latest_bridge else None
    bridge_last_error: str | None = None
    if latest_bridge and latest_bridge.decision == MarketWatcherBridgeDecisionType.FAILED:
        bridge_last_error = _redact_operator_message(
            latest_bridge.reason or "Bridge tick failed.",
            settings,
        )
        warnings.append("Recent market watcher bridge error detected.")

    if worker_unexpected:
        warnings.append("Background worker heartbeat detected while worker is disabled in config.")
    if settings.market_watcher_bridge_enabled and not bridge_running:
        warnings.append("Market watcher bridge is configured but not actively ticking.")
    if delivery_counts.failed > 0:
        warnings.append(f"{delivery_counts.failed} alert(s) failed external delivery.")
    if not settings.alert_delivery_enabled and delivery_counts.pending > 0:
        warnings.append("Pending alerts exist while external delivery is disabled.")
    if settings.telegram_alerts_enabled and not delivery_status.telegram_configured:
        warnings.append("Telegram alerts enabled but bot token is not configured.")
    if prefs.telegram_enabled and not (prefs.telegram_chat_id or "").strip():
        warnings.append("Telegram enabled in preferences but chat ID is missing.")
    if settings.alert_webhook_enabled and not delivery_status.webhook_configured:
        warnings.append("Webhook alerts enabled but webhook URL is not configured.")

    external_delivery_enabled = bool(
        settings.alert_delivery_enabled
        and (settings.telegram_alerts_enabled or settings.alert_webhook_enabled)
    )

    inputs = RoutingDiagnosticsInputs(
        real_trading_enabled=settings.real_trading_enabled,
        paper_only=delivery_status.paper_only,
        external_delivery_enabled=external_delivery_enabled,
        telegram_enabled=settings.telegram_alerts_enabled,
        telegram_configured=delivery_status.telegram_configured,
        telegram_user_enabled=prefs.telegram_enabled,
        telegram_chat_configured=bool((prefs.telegram_chat_id or "").strip()),
        webhook_enabled=settings.alert_webhook_enabled,
        webhook_configured=delivery_status.webhook_configured,
        worker_enabled=settings.worker_enabled,
        worker_running=worker_running,
        worker_running_unexpected=worker_unexpected,
        bridge_enabled=settings.market_watcher_bridge_enabled,
        bridge_running=bridge_running,
        bridge_paper_only=bridge.paper_only,
        bridge_last_decision=bridge_last_decision,
        bridge_last_error=bridge_last_error,
        failed_alerts_count=delivery_counts.failed,
        pending_alerts_count=delivery_counts.pending,
        delivery_disabled=not settings.alert_delivery_enabled,
        warnings=warnings,
    )
    readiness = compute_alert_routing_readiness(inputs)

    telegram_chat_configured = bool((prefs.telegram_chat_id or "").strip()) or bool(
        settings.telegram_chat_id.strip()
    )
    test_service = TelegramTestAlertService(session, settings, audit_service=AuditService(session))
    last_test_at, last_test_status = test_service.latest_test_summary(
        organization_id=organization_id,
    )

    return AlertRoutingSummaryResponse(
        alerts_enabled=True,
        telegram_enabled=settings.telegram_alerts_enabled,
        telegram_configured=delivery_status.telegram_configured,
        telegram_chat_configured=telegram_chat_configured,
        manual_test_available=manual_test_available(
            settings,
            paper_only=delivery_status.paper_only,
        ),
        last_test_alert_at=last_test_at,
        last_test_alert_status=last_test_status,
        webhook_enabled=settings.alert_webhook_enabled,
        external_delivery_enabled=external_delivery_enabled,
        paper_only=delivery_status.paper_only,
        quiet_hours=_quiet_hours_summary(
            settings,
            user_enabled=prefs.quiet_hours_enabled,
            user_start=prefs.quiet_hours_start,
            user_end=prefs.quiet_hours_end,
            user_timezone=prefs.timezone,
        ),
        severity_filters=_severity_filters(settings, user_min_severity=prefs.min_severity.value),
        last_alert_created_at=latest_alert.created_at if latest_alert else None,
        last_alert_status=(
            latest_alert.delivery_status.value
            if latest_alert and latest_alert.delivery_status
            else None
        ),
        pending_alerts_count=delivery_counts.pending,
        delivered_alerts_count=delivery_counts.delivered,
        failed_alerts_count=delivery_counts.failed,
        market_watcher_configured=settings.market_watcher_enabled,
        market_watcher_running=watcher_running,
        bridge_enabled=settings.market_watcher_bridge_enabled,
        bridge_running=bridge_running,
        bridge_last_tick_at=bridge.last_tick_at,
        bridge_last_decision=bridge_last_decision,
        bridge_last_error=bridge_last_error,
        worker_enabled=settings.worker_enabled,
        worker_running=worker_running,
        readiness=readiness,
        warnings=warnings,
        generated_at=generated_at,
    )
