"""Adapt existing paper alerts to the same Telegram policy contract."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import PaperValidationAlert
from app.schemas.common import (
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    PaperAlertSeverity,
    PaperAlertType,
)
from app.schemas.telegram_policy import (
    NotificationEventType,
    NotificationSeverity,
    TelegramNotificationEvent,
    TelegramNotificationPolicyV2,
)
from app.services.notifications.telegram_policy import PolicyHistory, evaluate_telegram_policy

PAPER_EVENT_TYPES = {
    PaperAlertType.SETUP_SIGNAL_DETECTED: NotificationEventType.SETUP,
    PaperAlertType.PAPER_TRADE_OPENED: NotificationEventType.PAPER_TRADE_OPENED,
    PaperAlertType.PAPER_TRADE_CLOSED: NotificationEventType.PAPER_TRADE_CLOSED,
    PaperAlertType.STOP_HIT: NotificationEventType.STOP,
    PaperAlertType.TP_HIT: NotificationEventType.PAPER_TRADE_CLOSED,
    PaperAlertType.RUNNER_EXIT: NotificationEventType.PAPER_TRADE_CLOSED,
    PaperAlertType.STRATEGY_BLOCKED: NotificationEventType.RISK,
    PaperAlertType.DATA_STALE: NotificationEventType.RISK,
    PaperAlertType.PAPER_VALIDATION_RESTRICTED: NotificationEventType.RISK,
    PaperAlertType.OVERTRADING_WARNING: NotificationEventType.RISK,
    PaperAlertType.DAILY_LOSS_LOCK_WARNING: NotificationEventType.RISK,
}
PAPER_SEVERITIES = {
    PaperAlertSeverity.INFO: NotificationSeverity.INFO,
    PaperAlertSeverity.WARNING: NotificationSeverity.WATCH,
    PaperAlertSeverity.CRITICAL: NotificationSeverity.CRITICAL,
}


def paper_notification_event(row: PaperValidationAlert) -> TelegramNotificationEvent:
    metadata = row.metadata_json or {}
    event_type = PAPER_EVENT_TYPES.get(row.alert_type, NotificationEventType.OTHER)
    if row.alert_type == PaperAlertType.TP_HIT and metadata.get("partial_profit") is True:
        event_type = NotificationEventType.PARTIAL_PROFIT
    return TelegramNotificationEvent(
        event_type=event_type,
        severity=PAPER_SEVERITIES[row.severity],
        strategy_id=row.strategy_id,
        symbol=metadata.get("symbol"),
        setup_stage=metadata.get("setup_stage"),
        phase=metadata.get("notification_phase"),
        quality=metadata.get("notification_quality"),
        duplicate_key=row.dedup_key or str(row.id),
        occurred_at=row.created_at.replace(tzinfo=UTC)
        if row.created_at.tzinfo is None
        else row.created_at,
        mandatory_risk=(
            event_type == NotificationEventType.RISK and row.severity == PaperAlertSeverity.CRITICAL
        ),
    )


def paper_telegram_policy_reason(
    session: Session,
    row: PaperValidationAlert,
    policy: TelegramNotificationPolicyV2,
    *,
    organization_id: UUID,
    user_id: UUID,
    chat_id: str,
    bot_id: str,
    now: datetime,
) -> str | None:
    if row.organization_id != organization_id or row.user_id not in (None, user_id):
        return "POLICY_RECIPIENT_MISMATCH"
    window = max(policy.cooldown_seconds, policy.duplicate_suppression_seconds)
    rows = (
        session.scalars(
            select(PaperValidationAlert).where(
                PaperValidationAlert.organization_id == organization_id,
                or_(
                    PaperValidationAlert.user_id == user_id, PaperValidationAlert.user_id.is_(None)
                ),
                PaperValidationAlert.delivery_channel == AlertDeliveryChannel.TELEGRAM,
                PaperValidationAlert.delivery_status == AlertDeliveryStatus.DELIVERED,
                PaperValidationAlert.delivered_at >= now - timedelta(seconds=window),
                PaperValidationAlert.id != row.id,
            )
        )
        if window
        else []
    )
    history = []
    for prior in rows:
        metadata = prior.metadata_json or {}
        if (
            metadata.get("telegram_policy_chat_id") != chat_id
            or metadata.get("telegram_policy_bot_id") != bot_id
            or metadata.get("telegram_policy_user_id") != str(user_id)
        ):
            continue
        accepted_at = prior.delivered_at
        if accepted_at is not None:
            history.append(
                PolicyHistory(
                    paper_notification_event(prior),
                    accepted_at.replace(tzinfo=UTC) if accepted_at.tzinfo is None else accepted_at,
                )
            )
    return evaluate_telegram_policy(policy, paper_notification_event(row), now=now, history=history)
