"""Read-only automatic Telegram delivery selection and readiness (Slice 71)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import ExecutionMode, Settings
from app.db.models import PaperValidationAlert
from app.guardrails.redaction import redact_text
from app.repositories.paper_scheduler import PaperAlertRepository
from app.schemas.common import (
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    PaperAlertSeverity,
)
from app.schemas.telegram_automatic_delivery import (
    AlertDeliveryPreviewItem,
    AlertDeliveryPreviewRequest,
    AlertDeliveryPreviewResponse,
    DeliveryLimits,
    PreviewItemStatus,
)
from app.services.alert_delivery_service import AlertDeliveryService
from app.services.audit_service import AuditService
from app.services.delivery_routing_service import _SEVERITY_RANK
from app.services.market_watcher_service import MarketWatcherService
from app.services.notifications.preferences_service import NotificationPreferencesService
from app.services.telegram_alert_delivery_service import (
    TelegramAlertDeliveryService,
    _already_delivered_telegram,
)
from app.workers.repository import WorkerHeartbeatRepository

_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"bot[0-9]{8,}:[A-Za-z0-9_-]+", re.IGNORECASE)
_RESOLVED_READ_DAYS = 30
_FAILED_DELIVERY_BLOCK_THRESHOLD = 5
_SELECTION_SCAN_LIMIT = 200

DELIVERY_LIMITS = DeliveryLimits()


@dataclass(frozen=True)
class AutomaticTelegramReadiness:
    automatic_telegram_delivery_ready: bool
    automatic_delivery_blockers: list[str]
    eligible_pending_telegram_count: int
    already_delivered_telegram_count: int
    next_delivery_preview_count: int
    delivery_limits: DeliveryLimits
    dry_run_supported: bool = True


_WATCHER_STALE_MINUTES = 60


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


def _market_watcher_running_unexpectedly(
    settings: Settings,
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    if settings.market_watcher_enabled:
        return False
    watcher = MarketWatcherService(session, settings).get_status(
        organization_id=organization_id,
        user_id=user_id,
    )
    if watcher.last_scan_at is None:
        return False
    last_scan = watcher.last_scan_at
    if last_scan.tzinfo is None:
        last_scan = last_scan.replace(tzinfo=UTC)
    running = datetime.now(UTC) - last_scan <= timedelta(minutes=_WATCHER_STALE_MINUTES)
    return running


def _redact_message(message: str, settings: Settings) -> str:
    redacted = redact_text(message.strip())
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


def _severity_meets_minimum(
    severity: PaperAlertSeverity,
    minimum: PaperAlertSeverity,
) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(minimum, 0)


def _is_resolved_or_stale(row: PaperValidationAlert, *, now: datetime) -> bool:
    if row.delivery_status is AlertDeliveryStatus.SKIPPED:
        return True
    if row.read_at is not None:
        read_at = row.read_at if row.read_at.tzinfo else row.read_at.replace(tzinfo=UTC)
        if now - read_at > timedelta(days=_RESOLVED_READ_DAYS):
            return True
    return False


def _evaluate_alert(
    row: PaperValidationAlert,
    *,
    settings: Settings,
    severity_min: PaperAlertSeverity,
    enabled_alert_types: set[str] | None,
    now: datetime,
) -> tuple[PreviewItemStatus, str | None]:
    if _already_delivered_telegram(row):
        return "already_delivered", "Already delivered to Telegram."

    if _is_resolved_or_stale(row, now=now):
        return "skipped", "Alert is resolved or stale for automatic delivery."

    if not _severity_meets_minimum(row.severity, severity_min):
        return (
            "skipped",
            f"Severity {row.severity.value} below minimum {severity_min.value}.",
        )

    if enabled_alert_types and row.alert_type.value not in enabled_alert_types:
        return (
            "skipped",
            f"Alert type {row.alert_type.value} not in enabled filters.",
        )

    if (
        row.delivery_status is AlertDeliveryStatus.FAILED
        and row.delivery_channel is AlertDeliveryChannel.TELEGRAM
    ):
        return "skipped", "Recent Telegram delivery failed for this alert."

    return "eligible", "Eligible for automatic Telegram delivery preview."


def _deterministic_sort_key(row: PaperValidationAlert) -> tuple[datetime, str]:
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return (-created.timestamp(), str(row.id))


class TelegramAutomaticDeliveryService:
    """Pure read-only selection for future automatic Telegram delivery."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._alerts = PaperAlertRepository(session)
        self._audit = AuditService(session)
        self._preferences = NotificationPreferencesService(session, self._audit)
        self._delivery = AlertDeliveryService(session, settings)
        self._telegram_delivery = TelegramAlertDeliveryService(
            session,
            settings,
            audit_service=self._audit,
        )

    def preview(
        self,
        request: AlertDeliveryPreviewRequest,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AlertDeliveryPreviewResponse:
        """Read-only preview — never sends Telegram or mutates alerts."""
        generated_at = datetime.now(UTC)
        warnings: list[str] = []
        if request.channel != "telegram":
            warnings.append("Only telegram channel is supported for preview.")

        prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
        enabled_types = (
            {t.value for t in prefs.enabled_alert_types} if prefs.enabled_alert_types else None
        )

        rows, _total = self._alerts.list_for_org(
            organization_id,
            limit=_SELECTION_SCAN_LIMIT,
            offset=0,
        )
        rows_sorted = sorted(rows, key=_deterministic_sort_key)

        eligible_count = 0
        skipped_count = 0
        already_delivered_count = 0
        items: list[AlertDeliveryPreviewItem] = []

        for row in rows_sorted:
            status, reason = _evaluate_alert(
                row,
                settings=self._settings,
                severity_min=request.severity_min,
                enabled_alert_types=enabled_types,
                now=generated_at,
            )
            if status == "eligible":
                eligible_count += 1
            elif status == "already_delivered":
                already_delivered_count += 1
            else:
                skipped_count += 1

            if len(items) >= request.limit:
                continue

            items.append(
                AlertDeliveryPreviewItem(
                    alert_id=row.id,
                    alert_type=row.alert_type,
                    severity=row.severity,
                    message_preview=_redact_message(row.message, self._settings),
                    created_at=row.created_at,
                    status=status,
                    reason=reason,
                )
            )

        if eligible_count == 0:
            warnings.append("No eligible pending alerts for Telegram automatic delivery.")

        return AlertDeliveryPreviewResponse(
            channel=request.channel,
            eligible_count=eligible_count,
            skipped_count=skipped_count,
            already_delivered_count=already_delivered_count,
            items=items,
            warnings=warnings,
            generated_at=generated_at,
        )

    def count_telegram_delivery_buckets(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        severity_min: PaperAlertSeverity = PaperAlertSeverity.INFO,
    ) -> tuple[int, int]:
        """Return (eligible_pending, already_delivered) across scan window."""
        prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
        enabled_types = (
            {t.value for t in prefs.enabled_alert_types} if prefs.enabled_alert_types else None
        )
        now = datetime.now(UTC)
        rows, _ = self._alerts.list_for_org(organization_id, limit=_SELECTION_SCAN_LIMIT)
        eligible = 0
        delivered = 0
        for row in rows:
            status, _ = _evaluate_alert(
                row,
                settings=self._settings,
                severity_min=severity_min,
                enabled_alert_types=enabled_types,
                now=now,
            )
            if status == "eligible":
                eligible += 1
            elif status == "already_delivered":
                delivered += 1
        return eligible, delivered

    def readiness(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        paper_only: bool,
        telegram_configured: bool,
        telegram_chat_configured: bool,
        external_delivery_enabled: bool,
    ) -> AutomaticTelegramReadiness:
        blockers: list[str] = []
        if self._settings.execution_mode is not ExecutionMode.PAPER:
            blockers.append("Execution mode is not paper.")
        if self._settings.real_trading_enabled:
            blockers.append("Real trading is enabled.")
        if not paper_only:
            blockers.append("Paper-only posture is not active.")
        if not telegram_configured:
            blockers.append("Telegram bot token is not configured.")
        if not telegram_chat_configured:
            blockers.append("Telegram chat ID is not configured.")

        if _worker_running_unexpectedly(self._settings, self._session):
            blockers.append("Background worker is running while disabled in config.")
        if _market_watcher_running_unexpectedly(
            self._settings,
            self._session,
            organization_id=organization_id,
            user_id=user_id,
        ):
            blockers.append("Market watcher is running while disabled in config.")

        if not self._settings.automatic_telegram_delivery_enabled:
            blockers.append(
                "Live automatic Telegram delivery is not enabled "
                "(AUTOMATIC_TELEGRAM_DELIVERY_ENABLED=false)."
            )

        if not self._settings.alert_delivery_enabled:
            blockers.append("External alert delivery is disabled (ALERT_DELIVERY_ENABLED=false).")
        if not external_delivery_enabled:
            blockers.append("External delivery is not enabled for this environment.")
        if not self._settings.telegram_alerts_enabled:
            blockers.append(
                "Automatic Telegram delivery is not enabled (TELEGRAM_ALERTS_ENABLED=false)."
            )

        prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
        if not prefs.telegram_enabled:
            blockers.append("Telegram is disabled in user notification preferences.")

        _delivered, failed_count, _last_at, last_status = self._telegram_delivery.delivery_summary(
            organization_id=organization_id
        )
        if failed_count >= _FAILED_DELIVERY_BLOCK_THRESHOLD:
            blockers.append(f"Recent Telegram delivery failures ({failed_count}) exceed threshold.")
        if last_status == "failed_redacted" and failed_count > 0:
            blockers.append("Most recent Telegram delivery attempt failed.")

        eligible_pending, already_delivered = self.count_telegram_delivery_buckets(
            organization_id=organization_id,
            user_id=user_id,
        )
        if eligible_pending == 0:
            blockers.append("No eligible pending alerts for automatic Telegram delivery.")

        next_preview = min(
            eligible_pending,
            DELIVERY_LIMITS.default_preview_limit,
            DELIVERY_LIMITS.max_automatic_batch_limit,
        )

        return AutomaticTelegramReadiness(
            automatic_telegram_delivery_ready=len(blockers) == 0,
            automatic_delivery_blockers=blockers,
            eligible_pending_telegram_count=eligible_pending,
            already_delivered_telegram_count=already_delivered,
            next_delivery_preview_count=next_preview,
            delivery_limits=DELIVERY_LIMITS,
            dry_run_supported=True,
        )
