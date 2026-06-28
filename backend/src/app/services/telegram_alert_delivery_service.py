"""Owner-gated manual Telegram delivery for one existing in-app alert (Slice 70)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ExecutionMode, Settings
from app.core.errors import NotFoundError
from app.db.models import PaperValidationAlert
from app.guardrails.redaction import redact_text
from app.providers.alert_delivery.telegram import TelegramAlertDeliveryProvider
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    AuditEventType,
    AuditResult,
    AuditSeverity,
)
from app.schemas.telegram_alert_delivery import (
    TELEGRAM_ALERT_DELIVERY_CONFIRM_PHRASE,
    TelegramAlertDeliveryResponse,
    TelegramAlertDeliveryStatus,
)
from app.services.alert_delivery_service import AlertDeliveryService
from app.services.audit_service import AuditService
from app.services.notifications.preferences_service import NotificationPreferencesService
from app.services.telegram_test_alert_service import manual_test_available

_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"bot[0-9]{8,}:[A-Za-z0-9_-]+", re.IGNORECASE)


@dataclass(frozen=True)
class TelegramDeliverySafetyContext:
    execution_mode: ExecutionMode
    real_trading_enabled: bool
    paper_only: bool
    telegram_configured: bool
    chat_configured: bool


def telegram_alert_delivery_available(
    settings: Settings,
    *,
    paper_only: bool,
    telegram_configured: bool,
    telegram_chat_configured: bool,
) -> bool:
    """True when owner may deliver one selected in-app alert to Telegram."""
    return (
        manual_test_available(settings, paper_only=paper_only)
        and telegram_configured
        and telegram_chat_configured
    )


def _redact_operator_text(message: str, settings: Settings) -> str:
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


def _safety_context(
    settings: Settings,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> TelegramDeliverySafetyContext:
    prefs_service = NotificationPreferencesService(session, AuditService(session))
    prefs = prefs_service.get(organization_id=organization_id, user_id=user_id)
    chat_id = (prefs.telegram_chat_id or settings.telegram_chat_id or "").strip()
    return TelegramDeliverySafetyContext(
        execution_mode=settings.execution_mode,
        real_trading_enabled=settings.real_trading_enabled,
        paper_only=True,
        telegram_configured=bool(settings.telegram_bot_token.strip()),
        chat_configured=bool(chat_id),
    )


def _already_delivered_telegram(row: object) -> bool:
    from app.db.models import PaperValidationAlert

    assert isinstance(row, PaperValidationAlert)
    if (
        row.delivery_status is AlertDeliveryStatus.DELIVERED
        and row.delivery_channel is AlertDeliveryChannel.TELEGRAM
    ):
        return True
    meta = dict(row.metadata_json or {})
    return bool(meta.get("telegram_manual_delivered"))


def _telegram_delivery_stats(
    audit_service: AuditService,
    *,
    organization_id: uuid.UUID,
) -> tuple[int, int, datetime | None, TelegramAlertDeliveryStatus | None]:
    _, delivered_count = audit_service.list_records(
        organization_id=organization_id,
        event_type=AuditEventType.ALERT_TELEGRAM_DELIVERY_SENT,
        limit=1,
    )
    _, failed_count = audit_service.list_records(
        organization_id=organization_id,
        event_type=AuditEventType.ALERT_TELEGRAM_DELIVERY_FAILED,
        limit=1,
    )
    latest_at: datetime | None = None
    latest_status: TelegramAlertDeliveryStatus | None = None
    for event_type, status in (
        (AuditEventType.ALERT_TELEGRAM_DELIVERY_SENT, "sent"),
        (AuditEventType.ALERT_TELEGRAM_DELIVERY_FAILED, "failed_redacted"),
    ):
        records, total = audit_service.list_records(
            organization_id=organization_id,
            event_type=event_type,
            limit=1,
        )
        if total == 0 or not records:
            continue
        record = records[0]
        if latest_at is None or record.timestamp > latest_at:
            latest_at = record.timestamp
            latest_status = status  # type: ignore[assignment]
    return delivered_count, failed_count, latest_at, latest_status


class TelegramAlertDeliveryService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        audit_service: AuditService | None = None,
        http_post: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._audit = audit_service or AuditService(session)
        self._preferences = NotificationPreferencesService(session, self._audit)
        self._telegram = TelegramAlertDeliveryProvider(settings, http_post=http_post)

    def delivery_summary(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> tuple[int, int, datetime | None, TelegramAlertDeliveryStatus | None]:
        return _telegram_delivery_stats(self._audit, organization_id=organization_id)

    def deliver_alert(
        self,
        alert_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        confirm: str,
    ) -> TelegramAlertDeliveryResponse:
        ctx = _safety_context(
            self._settings,
            organization_id=organization_id,
            user_id=user_id,
            session=self._session,
        )
        row = self._session.scalar(
            select(PaperValidationAlert).where(
                PaperValidationAlert.id == alert_id,
                PaperValidationAlert.organization_id == organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Alert not found.")

        self._audit_delivery(
            organization_id=organization_id,
            user_id=user_id,
            alert_id=alert_id,
            event_type=AuditEventType.ALERT_TELEGRAM_DELIVERY_REQUESTED,
            result=AuditResult.SUCCESS,
            metadata={"status": "requested", "paper_only": True},
        )

        if confirm != TELEGRAM_ALERT_DELIVERY_CONFIRM_PHRASE:
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                response=TelegramAlertDeliveryResponse(
                    status="blocked",
                    alert_id=alert_id,
                    error_code="confirmation_required",
                    error_message="Confirmation phrase did not match.",
                ),
            )

        if ctx.real_trading_enabled:
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                response=TelegramAlertDeliveryResponse(
                    status="blocked",
                    alert_id=alert_id,
                    error_code="real_trading_enabled",
                    error_message="Telegram alert delivery blocked while real trading is enabled.",
                ),
            )

        if ctx.execution_mode is not ExecutionMode.PAPER:
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                response=TelegramAlertDeliveryResponse(
                    status="blocked",
                    alert_id=alert_id,
                    error_code="execution_mode_not_paper",
                    error_message="Telegram alert delivery requires paper execution mode.",
                ),
            )

        if not ctx.paper_only:
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                response=TelegramAlertDeliveryResponse(
                    status="blocked",
                    alert_id=alert_id,
                    error_code="paper_only_required",
                    error_message="Telegram alert delivery requires paper-only posture.",
                ),
            )

        if not ctx.telegram_configured or not ctx.chat_configured:
            return self._finalize(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                response=TelegramAlertDeliveryResponse(
                    status="skipped_not_configured",
                    alert_id=alert_id,
                    error_code="telegram_not_configured",
                    error_message=(
                        "Telegram bot token or chat ID is not configured."
                        if not ctx.telegram_configured
                        else "Telegram chat ID is not configured."
                    ),
                ),
            )

        if _already_delivered_telegram(row):
            delivery_id = (row.metadata_json or {}).get("telegram_delivery_id")
            return TelegramAlertDeliveryResponse(
                status="already_delivered",
                alert_id=alert_id,
                sent_at=row.delivered_at,
                delivery_id=str(delivery_id) if delivery_id else None,
            )

        prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
        chat_id = (prefs.telegram_chat_id or self._settings.telegram_chat_id or "").strip()
        base_payload = AlertDeliveryService.build_payload(row)
        payload = replace(
            base_payload,
            telegram_chat_id=chat_id,
            metadata={
                **(base_payload.metadata or {}),
                "telegram_manual_delivery": True,
                "paper_only": True,
            },
        )
        delivery_id = str(uuid.uuid4())
        outcome = self._telegram.deliver(payload, bypass_enable_check=True)
        sent_at = datetime.now(UTC)
        row.delivery_attempts += 1
        row.delivery_channel = AlertDeliveryChannel.TELEGRAM

        if outcome.success:
            row.delivery_status = AlertDeliveryStatus.DELIVERED
            row.delivered_at = sent_at
            row.last_delivery_error = None
            meta = dict(row.metadata_json or {})
            meta["telegram_manual_delivered"] = True
            meta["telegram_delivery_id"] = delivery_id
            row.metadata_json = meta
            response = TelegramAlertDeliveryResponse(
                status="sent",
                alert_id=alert_id,
                sent_at=sent_at,
                delivery_id=delivery_id,
            )
            self._audit_delivery(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                event_type=AuditEventType.ALERT_TELEGRAM_DELIVERY_SENT,
                result=AuditResult.SUCCESS,
                metadata={
                    "status": "sent",
                    "delivery_id": delivery_id,
                    "paper_only": True,
                },
            )
            return response

        row.delivery_status = AlertDeliveryStatus.FAILED
        error_message = _redact_operator_text(outcome.error or "Delivery failed.", self._settings)
        row.last_delivery_error = error_message
        response = TelegramAlertDeliveryResponse(
            status="failed_redacted",
            alert_id=alert_id,
            error_code="telegram_delivery_failed",
            error_message=error_message,
        )
        self._audit_delivery(
            organization_id=organization_id,
            user_id=user_id,
            alert_id=alert_id,
            event_type=AuditEventType.ALERT_TELEGRAM_DELIVERY_FAILED,
            result=AuditResult.FAILURE,
            metadata={
                "status": "failed_redacted",
                "error_code": "telegram_delivery_failed",
                "paper_only": True,
            },
        )
        return response

    def _finalize(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        alert_id: uuid.UUID,
        response: TelegramAlertDeliveryResponse,
    ) -> TelegramAlertDeliveryResponse:
        if response.status == "blocked":
            self._audit_delivery(
                organization_id=organization_id,
                user_id=user_id,
                alert_id=alert_id,
                event_type=AuditEventType.ALERT_TELEGRAM_DELIVERY_FAILED,
                result=AuditResult.BLOCKED,
                metadata={
                    "status": response.status,
                    "error_code": response.error_code,
                    "paper_only": True,
                },
            )
        return response

    def _audit_delivery(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        alert_id: uuid.UUID,
        event_type: AuditEventType,
        result: AuditResult,
        metadata: dict[str, object],
    ) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=f"telegram-alert-delivery-{alert_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=event_type,
                resource_type="paper_validation_alert",
                resource_id=str(alert_id),
                actor_type=ActorType.USER,
                result=result,
                severity=AuditSeverity.INFO,
                metadata=metadata,
            )
        )
