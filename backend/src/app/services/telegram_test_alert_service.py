"""Owner-gated manual Telegram test alert (Slice 69 — paper only, no trades)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import ExecutionMode, Settings
from app.guardrails.redaction import redact_text
from app.providers.alert_delivery.base import AlertDeliveryPayload, AlertDeliveryResult
from app.providers.alert_delivery.telegram import TelegramAlertDeliveryProvider
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperAlertSeverity,
)
from app.schemas.telegram_test_alert import (
    TELEGRAM_TEST_CONFIRM_PHRASE,
    TelegramTestAlertResponse,
    TelegramTestAlertStatus,
)
from app.services.alert_delivery_service import TEST_ALERT_MESSAGE
from app.services.audit_service import AuditService
from app.services.notifications.preferences_service import NotificationPreferencesService

_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(r"bot[0-9]{8,}:[A-Za-z0-9_-]+", re.IGNORECASE)
_MANUAL_TEST_AUDIT_ACTION = "telegram_manual_test"


@dataclass(frozen=True)
class TelegramTestSafetyContext:
    execution_mode: ExecutionMode
    real_trading_enabled: bool
    paper_only: bool
    external_delivery_enabled: bool
    telegram_configured: bool
    chat_configured: bool


def manual_test_available(settings: Settings, *, paper_only: bool) -> bool:
    """True when safety gates allow the owner manual Telegram test path."""
    return (
        settings.execution_mode is ExecutionMode.PAPER
        and not settings.real_trading_enabled
        and paper_only
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


def _external_delivery_enabled(settings: Settings) -> bool:
    return bool(
        settings.alert_delivery_enabled
        and (settings.telegram_alerts_enabled or settings.alert_webhook_enabled)
    )


def _safety_context(
    settings: Settings,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
) -> TelegramTestSafetyContext:
    prefs_service = NotificationPreferencesService(session, AuditService(session))
    prefs = prefs_service.get(organization_id=organization_id, user_id=user_id)
    chat_id = (prefs.telegram_chat_id or settings.telegram_chat_id or "").strip()
    return TelegramTestSafetyContext(
        execution_mode=settings.execution_mode,
        real_trading_enabled=settings.real_trading_enabled,
        paper_only=True,
        external_delivery_enabled=_external_delivery_enabled(settings),
        telegram_configured=bool(settings.telegram_bot_token.strip()),
        chat_configured=bool(chat_id),
    )


def _blocked_response(
    ctx: TelegramTestSafetyContext,
    *,
    error_code: str,
    error_message: str,
) -> TelegramTestAlertResponse:
    return TelegramTestAlertResponse(
        status="blocked",
        telegram_configured=ctx.telegram_configured,
        chat_configured=ctx.chat_configured,
        paper_only=ctx.paper_only,
        external_delivery_enabled=ctx.external_delivery_enabled,
        error_code=error_code,
        error_message=error_message,
    )


def _latest_manual_test_from_audit(
    audit_service: AuditService,
    *,
    organization_id: uuid.UUID,
) -> tuple[datetime | None, TelegramTestAlertStatus | None]:
    records, total = audit_service.list_records(
        organization_id=organization_id,
        event_type=AuditEventType.NOTIFICATION_TEST_SENT,
        limit=20,
    )
    if total == 0:
        return None, None
    for record in records:
        meta = dict(record.redacted_metadata or {})
        if meta.get("action") != _MANUAL_TEST_AUDIT_ACTION:
            continue
        status = meta.get("status")
        if status in {"sent", "skipped_not_configured", "blocked", "failed_redacted"}:
            return record.timestamp, status  # type: ignore[return-value]
    return None, None


class TelegramTestAlertService:
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

    def latest_test_summary(
        self,
        *,
        organization_id: uuid.UUID,
    ) -> tuple[datetime | None, TelegramTestAlertStatus | None]:
        return _latest_manual_test_from_audit(
            self._audit,
            organization_id=organization_id,
        )

    def send_manual_test(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        confirm: str,
        message: str | None = None,
    ) -> TelegramTestAlertResponse:
        ctx = _safety_context(
            self._settings,
            organization_id=organization_id,
            user_id=user_id,
            session=self._session,
        )

        if confirm != TELEGRAM_TEST_CONFIRM_PHRASE:
            response = _blocked_response(
                ctx,
                error_code="confirmation_required",
                error_message="Confirmation phrase did not match.",
            )
            self._record_audit(
                organization_id=organization_id,
                user_id=user_id,
                response=response,
            )
            return response

        if ctx.real_trading_enabled:
            response = _blocked_response(
                ctx,
                error_code="real_trading_enabled",
                error_message="Manual Telegram test blocked while real trading is enabled.",
            )
            self._record_audit(
                organization_id=organization_id,
                user_id=user_id,
                response=response,
            )
            return response

        if ctx.execution_mode is not ExecutionMode.PAPER:
            response = _blocked_response(
                ctx,
                error_code="execution_mode_not_paper",
                error_message="Manual Telegram test requires paper execution mode.",
            )
            self._record_audit(
                organization_id=organization_id,
                user_id=user_id,
                response=response,
            )
            return response

        if not ctx.paper_only:
            response = _blocked_response(
                ctx,
                error_code="paper_only_required",
                error_message="Manual Telegram test requires paper-only posture.",
            )
            self._record_audit(
                organization_id=organization_id,
                user_id=user_id,
                response=response,
            )
            return response

        if not ctx.telegram_configured or not ctx.chat_configured:
            response = TelegramTestAlertResponse(
                status="skipped_not_configured",
                telegram_configured=ctx.telegram_configured,
                chat_configured=ctx.chat_configured,
                paper_only=ctx.paper_only,
                external_delivery_enabled=ctx.external_delivery_enabled,
                error_code="telegram_not_configured",
                error_message=(
                    "Telegram bot token or chat ID is not configured."
                    if not ctx.telegram_configured
                    else "Telegram chat ID is not configured."
                ),
            )
            self._record_audit(
                organization_id=organization_id,
                user_id=user_id,
                response=response,
            )
            return response

        prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
        chat_id = (prefs.telegram_chat_id or self._settings.telegram_chat_id or "").strip()
        operator_note = _redact_operator_text(message, self._settings) if message else ""
        body_message = TEST_ALERT_MESSAGE
        if operator_note:
            body_message = f"{TEST_ALERT_MESSAGE}\n\nOperator note: {operator_note}"

        payload = AlertDeliveryPayload(
            alert_id="telegram-manual-test",
            organization_id=str(organization_id),
            alert_type="telegram_manual_test",
            severity=PaperAlertSeverity.INFO.value,
            message=body_message,
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            telegram_chat_id=chat_id,
            is_test=True,
            metadata={"manual_test": True, "paper_only": True},
        )
        outcome = self._deliver_manual_test(payload)
        sent_at = datetime.now(UTC)

        if outcome.success:
            response = TelegramTestAlertResponse(
                status="sent",
                telegram_configured=True,
                chat_configured=True,
                paper_only=True,
                external_delivery_enabled=ctx.external_delivery_enabled,
                sent_at=sent_at,
            )
        else:
            response = TelegramTestAlertResponse(
                status="failed_redacted",
                telegram_configured=True,
                chat_configured=True,
                paper_only=True,
                external_delivery_enabled=ctx.external_delivery_enabled,
                error_code="telegram_delivery_failed",
                error_message=_redact_operator_text(
                    outcome.error or "Delivery failed.",
                    self._settings,
                ),
            )

        self._record_audit(
            organization_id=organization_id,
            user_id=user_id,
            response=response,
        )
        return response

    def _deliver_manual_test(self, payload: AlertDeliveryPayload) -> AlertDeliveryResult:
        """Send one Telegram test message without global delivery enable flags."""
        return self._telegram.deliver(payload, bypass_enable_check=True)

    def _record_audit(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        response: TelegramTestAlertResponse,
    ) -> None:
        result = AuditResult.SUCCESS if response.status == "sent" else AuditResult.FAILURE
        if response.status in {"blocked", "skipped_not_configured"}:
            result = AuditResult.BLOCKED
        self._audit.record(
            AuditRecordCreate(
                request_id=f"telegram-manual-test-{user_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.NOTIFICATION_TEST_SENT,
                resource_type="telegram_manual_test",
                resource_id=str(user_id),
                actor_type=ActorType.USER,
                result=result,
                severity=AuditSeverity.INFO,
                metadata={
                    "action": _MANUAL_TEST_AUDIT_ACTION,
                    "status": response.status,
                    "paper_only": True,
                    "error_code": response.error_code,
                },
            )
        )
