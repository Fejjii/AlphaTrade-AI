"""Alert delivery orchestration (Slice 41/46 — disabled by default, paper only)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.db.models import PaperValidationAlert as AlertModel
from app.guardrails.redaction import redact_text
from app.providers.alert_delivery import build_alert_delivery_providers
from app.providers.alert_delivery.base import (
    AlertDeliveryPayload,
    AlertDeliveryProvider,
    AlertDeliveryResult,
)
from app.repositories.paper_scheduler import PaperAlertRepository
from app.schemas.alert_delivery import (
    AlertDeliverPendingResult,
    AlertDeliverResult,
    AlertDeliveryStatusResponse,
    AlertDeliverySummary,
)
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AlertDeliveryChannel,
    AlertDeliveryStatus,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    PaperAlertSeverity,
    PaperAlertType,
    PaperObservabilityEventType,
)
from app.schemas.notifications import NotificationPreferencesResponse, NotificationTestResult
from app.services.audit_service import AuditService
from app.services.delivery_routing_service import route_alert_delivery
from app.services.notifications.preferences_service import NotificationPreferencesService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_observability_service import PaperObservabilityService

logger = structlog.get_logger("alert_delivery")

TEST_ALERT_MESSAGE = (
    "[TEST] AlphaTrade notification test. This is a safe test alert — no trade was executed."
)


class AlertDeliveryService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        audit_service: AuditService | None = None,
        providers: list[AlertDeliveryProvider] | None = None,
        http_post: Callable[..., httpx.Response] | None = None,
        preferences_service: NotificationPreferencesService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._alerts = PaperAlertRepository(session)
        self._audit = audit_service or AuditService(session)
        self._observability = PaperObservabilityService(session)
        self._providers = providers or build_alert_delivery_providers(
            self._settings, http_post=http_post
        )
        self._preferences = preferences_service or NotificationPreferencesService(
            session, self._audit
        )

    def get_status(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AlertDeliveryStatusResponse:
        webhook = self._provider(AlertDeliveryChannel.WEBHOOK)
        telegram = self._provider(AlertDeliveryChannel.TELEGRAM)
        push = self._provider(AlertDeliveryChannel.PUSH)
        channels: list[str] = [AlertDeliveryChannel.IN_APP.value]
        if webhook and webhook.is_enabled():
            channels.append(AlertDeliveryChannel.WEBHOOK.value)
        if telegram and telegram.is_enabled():
            channels.append(AlertDeliveryChannel.TELEGRAM.value)

        channel_statuses = []
        limitations: list[str] = []
        if organization_id is not None and user_id is not None:
            channel_statuses = self._preferences.channel_statuses(
                organization_id=organization_id,
                user_id=user_id,
                settings=self._settings,
            )
            prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
            if not prefs.webhook_enabled and not prefs.telegram_enabled:
                limitations.append("User external channels disabled in preferences.")
            if prefs.digest_mode.value == "disabled":
                limitations.append("User digest mode disabled external delivery.")

        effective = any(
            p.is_enabled() and p.channel is not AlertDeliveryChannel.IN_APP for p in self._providers
        )
        if organization_id is not None and user_id is not None:
            effective = any(s.available for s in channel_statuses)

        return AlertDeliveryStatusResponse(
            delivery_enabled=self._settings.alert_delivery_enabled,
            webhook_enabled=self._settings.alert_webhook_enabled,
            telegram_enabled=self._settings.telegram_alerts_enabled,
            email_enabled=self._settings.email_alerts_enabled,
            push_enabled=push.is_enabled() if push else False,
            webhook_configured=bool(self._settings.alert_webhook_url.strip()),
            telegram_configured=bool(self._settings.telegram_bot_token.strip()),
            effective_external_enabled=effective,
            channels=channels,
            channel_statuses=channel_statuses,
            paper_only=True,
            limitations=limitations,
        )

    def delivery_summary(self, organization_id: uuid.UUID) -> AlertDeliverySummary:
        counts = self._alerts.count_by_delivery_status(organization_id)
        return AlertDeliverySummary(
            total=sum(counts.values()),
            pending=counts.get(AlertDeliveryStatus.PENDING.value, 0),
            delivered=counts.get(AlertDeliveryStatus.DELIVERED.value, 0),
            failed=counts.get(AlertDeliveryStatus.FAILED.value, 0),
            disabled=counts.get(AlertDeliveryStatus.DISABLED.value, 0),
            skipped=counts.get(AlertDeliveryStatus.SKIPPED.value, 0),
        )

    def deliver_alert(
        self,
        alert_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> AlertDeliverResult:
        row = self._get_row(alert_id, organization_id=organization_id)
        return self._deliver_row(row, organization_id=organization_id, user_id=user_id)

    def deliver_pending(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> AlertDeliverPendingResult:
        rows = self._alerts.list_pending_delivery(organization_id, limit=limit)
        results: list[AlertDeliverResult] = []
        delivered = failed = skipped = 0
        for row in rows:
            result = self._deliver_row(row, organization_id=organization_id, user_id=user_id)
            results.append(result)
            if result.delivered:
                delivered += 1
            elif result.alert.delivery_status == AlertDeliveryStatus.SKIPPED:
                skipped += 1
            elif result.alert.delivery_status == AlertDeliveryStatus.FAILED:
                failed += 1
        return AlertDeliverPendingResult(
            processed=len(rows),
            delivered=delivered,
            failed=failed,
            skipped=skipped,
            results=results,
        )

    def send_test_notification(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationTestResult:
        prefs = self._preferences.get(organization_id=organization_id, user_id=user_id)
        routing = route_alert_delivery(
            settings=self._settings,
            preferences=prefs,
            providers=self._providers,
            severity=PaperAlertSeverity.INFO,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            now=datetime.now(UTC),
        )
        payload = AlertDeliveryPayload(
            alert_id="test-notification",
            organization_id=str(organization_id),
            alert_type="test_notification",
            severity=PaperAlertSeverity.INFO.value,
            message=TEST_ALERT_MESSAGE,
            idempotency_key=f"test-notification:{organization_id}:{user_id}",
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            telegram_chat_id=prefs.telegram_chat_id or self._settings.telegram_chat_id or None,
            is_test=True,
            metadata={"test": True, "paper_only": True},
        )
        delivery_results: dict[str, bool] = {}
        errors: dict[str, str] = {}
        skipped: list[str] = []
        external = [
            c for c in routing.selected_channels if c is not AlertDeliveryChannel.IN_APP
        ]
        if not routing.should_deliver or not external:
            skipped.append("external")
            if routing.skipped_reason:
                errors["routing"] = routing.skipped_reason
        for channel in external:
            provider = self._provider(channel)
            if provider is None or not provider.is_enabled():
                skipped.append(channel.value)
                continue
            outcome = self._safe_deliver(provider, payload)
            delivery_results[channel.value] = outcome.success
            if not outcome.success:
                errors[channel.value] = outcome.error or "Delivery failed."
            elif outcome.skipped:
                skipped.append(channel.value)

        result = self._preferences.build_test_result(
            delivery_results=delivery_results,
            errors={k: redact_text(v) for k, v in errors.items()},
            skipped=skipped,
        )
        self._audit.record(
            AuditRecordCreate(
                request_id=f"notification-test-{user_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.NOTIFICATION_TEST_SENT,
                resource_type="notification_test",
                resource_id=str(user_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS if result.success else AuditResult.FAILURE,
                severity=AuditSeverity.INFO,
                metadata={
                    "channels_succeeded": result.channels_succeeded,
                    "channels_skipped": result.channels_skipped,
                    "paper_only": True,
                },
            )
        )
        return result

    def initialize_delivery_fields(
        self,
        row: AlertModel,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> None:
        if not self._settings.alert_delivery_enabled:
            row.delivery_status = AlertDeliveryStatus.DISABLED
            row.delivery_channel = AlertDeliveryChannel.IN_APP
            return

        prefs = self._load_preferences(organization_id, user_id or row.user_id)
        routing = route_alert_delivery(
            settings=self._settings,
            preferences=prefs,
            providers=self._providers,
            severity=row.severity,
            alert_type=row.alert_type,
            now=datetime.now(UTC),
        )
        self._store_skipped_reason(row, routing.skipped_reason)
        external = [
            c for c in routing.selected_channels if c is not AlertDeliveryChannel.IN_APP
        ]
        if routing.should_deliver and external:
            row.delivery_status = AlertDeliveryStatus.PENDING
            row.delivery_channel = external[0]
        elif routing.skipped_reason:
            row.delivery_status = AlertDeliveryStatus.SKIPPED
            row.delivery_channel = AlertDeliveryChannel.IN_APP
        else:
            row.delivery_status = AlertDeliveryStatus.DISABLED
            row.delivery_channel = AlertDeliveryChannel.IN_APP

    @staticmethod
    def build_payload(row: AlertModel) -> AlertDeliveryPayload:
        stable_key = f"alert-deliver:{row.id}"
        return AlertDeliveryPayload(
            alert_id=str(row.id),
            organization_id=str(row.organization_id),
            alert_type=row.alert_type.value,
            severity=row.severity.value,
            message=row.message,
            strategy_id=str(row.strategy_id) if row.strategy_id else None,
            paper_validation_run_id=(
                str(row.paper_validation_run_id) if row.paper_validation_run_id else None
            ),
            paper_trade_id=str(row.paper_trade_id) if row.paper_trade_id else None,
            dedup_key=row.dedup_key,
            metadata=row.metadata_json,
            event_id=str(uuid.uuid4()),
            idempotency_key=stable_key,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def _deliver_row(
        self,
        row: AlertModel,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> AlertDeliverResult:
        if row.delivery_status == AlertDeliveryStatus.DELIVERED:
            schema = PaperAlertService._to_schema(row)
            return AlertDeliverResult(
                alert=schema,
                delivered=True,
                channel=row.delivery_channel,
                message="Already delivered.",
            )

        if not self._settings.alert_delivery_enabled:
            row.delivery_status = AlertDeliveryStatus.DISABLED
            row.delivery_channel = AlertDeliveryChannel.IN_APP
            schema = PaperAlertService._to_schema(row)
            return AlertDeliverResult(
                alert=schema,
                delivered=False,
                channel=AlertDeliveryChannel.IN_APP,
                message="External delivery disabled.",
            )

        prefs = self._load_preferences(organization_id, user_id or row.user_id)
        routing = route_alert_delivery(
            settings=self._settings,
            preferences=prefs,
            providers=self._providers,
            severity=row.severity,
            alert_type=row.alert_type,
            now=datetime.now(UTC),
        )
        self._store_skipped_reason(row, routing.skipped_reason)

        if not routing.should_deliver:
            row.delivery_status = AlertDeliveryStatus.SKIPPED
            row.delivery_channel = AlertDeliveryChannel.IN_APP
            schema = PaperAlertService._to_schema(row)
            return AlertDeliverResult(
                alert=schema,
                delivered=False,
                channel=AlertDeliveryChannel.IN_APP,
                message=routing.skipped_reason or "External delivery skipped.",
            )

        external_channels = [
            c for c in routing.selected_channels if c is not AlertDeliveryChannel.IN_APP
        ]
        provider = self._select_provider(row, external_channels)
        if provider is None or not provider.is_enabled():
            row.delivery_status = AlertDeliveryStatus.SKIPPED
            row.delivery_channel = AlertDeliveryChannel.IN_APP
            schema = PaperAlertService._to_schema(row)
            return AlertDeliverResult(
                alert=schema,
                delivered=False,
                channel=AlertDeliveryChannel.IN_APP,
                message="No external provider enabled — in-app only.",
            )

        if row.next_retry_at and row.next_retry_at > datetime.now(UTC):
            schema = PaperAlertService._to_schema(row)
            return AlertDeliverResult(
                alert=schema,
                delivered=False,
                channel=provider.channel,
                message="Retry not yet due.",
            )

        payload = self.build_payload(row)
        if provider.channel == AlertDeliveryChannel.TELEGRAM:
            chat_id = prefs.telegram_chat_id or self._settings.telegram_chat_id or None
            payload = AlertDeliveryPayload(
                alert_id=payload.alert_id,
                organization_id=payload.organization_id,
                alert_type=payload.alert_type,
                severity=payload.severity,
                message=payload.message,
                strategy_id=payload.strategy_id,
                paper_validation_run_id=payload.paper_validation_run_id,
                paper_trade_id=payload.paper_trade_id,
                dedup_key=payload.dedup_key,
                metadata=payload.metadata,
                event_id=payload.event_id,
                idempotency_key=payload.idempotency_key,
                timestamp=payload.timestamp,
                telegram_chat_id=chat_id,
            )

        row.delivery_attempts += 1
        row.delivery_channel = provider.channel
        outcome = self._safe_deliver(provider, payload)

        now = datetime.now(UTC)
        max_retries = self._max_retries_for(provider.channel)
        if outcome.success:
            row.delivery_status = AlertDeliveryStatus.DELIVERED
            row.delivered_at = now
            row.last_delivery_error = None
            row.next_retry_at = None
            self._store_skipped_reason(row, None)
            self._observability.emit(
                organization_id=organization_id,
                event_type=PaperObservabilityEventType.ALERT_DELIVERY_SUCCEEDED,
                strategy_id=row.strategy_id,
                run_id=row.paper_validation_run_id,
                metadata={"channel": provider.channel.value, "alert_id": str(row.id)},
            )
            message = "Delivered."
            delivered = True
        else:
            delivered = False
            if outcome.skipped:
                row.delivery_status = AlertDeliveryStatus.SKIPPED
                message = outcome.error or "Delivery skipped."
                self._store_skipped_reason(row, message)
            else:
                row.delivery_status = AlertDeliveryStatus.FAILED
                base_error = outcome.error or "Delivery failed."
                if row.delivery_attempts > max_retries:
                    row.last_delivery_error = redact_text(
                        f"Retry exhausted after {row.delivery_attempts} attempt(s): {base_error}"
                    )
                    row.next_retry_at = None
                    message = row.last_delivery_error
                else:
                    row.last_delivery_error = redact_text(base_error)
                    row.next_retry_at = now + timedelta(minutes=5 * row.delivery_attempts)
                    message = row.last_delivery_error or "Delivery failed."
                self._observability.emit(
                    organization_id=organization_id,
                    event_type=PaperObservabilityEventType.ALERT_DELIVERY_FAILED,
                    strategy_id=row.strategy_id,
                    run_id=row.paper_validation_run_id,
                    metadata={
                        "channel": provider.channel.value,
                        "alert_id": str(row.id),
                        "error": row.last_delivery_error,
                    },
                )
                logger.warning(
                    "alert_delivery_failed",
                    alert_id=str(row.id),
                    channel=provider.channel.value,
                    error=row.last_delivery_error,
                )

        self._audit.record(
            AuditRecordCreate(
                request_id=f"alert-deliver-{row.id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="paper_validation_alert",
                resource_id=str(row.id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS if delivered else AuditResult.FAILURE,
                severity=AuditSeverity.INFO if delivered else AuditSeverity.MEDIUM,
                metadata={
                    "action": "alert_deliver",
                    "channel": provider.channel.value,
                    "delivered": delivered,
                    "attempts": row.delivery_attempts,
                },
            )
        )
        schema = PaperAlertService._to_schema(row)
        return AlertDeliverResult(
            alert=schema,
            delivered=delivered,
            channel=provider.channel,
            message=message,
        )

    def _safe_deliver(
        self,
        provider: AlertDeliveryProvider,
        payload: AlertDeliveryPayload,
    ) -> AlertDeliveryResult:
        try:
            return provider.deliver(payload)
        except Exception as exc:
            return AlertDeliveryResult(
                success=False,
                channel=provider.channel,
                error=str(exc),
            )

    def _select_provider(
        self,
        row: AlertModel,
        preferred_channels: list[AlertDeliveryChannel],
    ) -> AlertDeliveryProvider | None:
        if row.delivery_channel != AlertDeliveryChannel.IN_APP:
            provider = self._provider(row.delivery_channel)
            if provider is not None and provider.is_enabled():
                return provider
        for channel in preferred_channels:
            provider = self._provider(channel)
            if provider is not None and provider.is_enabled():
                return provider
        for channel in (
            AlertDeliveryChannel.WEBHOOK,
            AlertDeliveryChannel.TELEGRAM,
            AlertDeliveryChannel.EMAIL,
            AlertDeliveryChannel.PUSH,
        ):
            provider = self._provider(channel)
            if provider is not None and provider.is_enabled():
                return provider
        return self._provider(AlertDeliveryChannel.IN_APP)

    def _max_retries_for(self, channel: AlertDeliveryChannel) -> int:
        if channel == AlertDeliveryChannel.TELEGRAM:
            return self._settings.telegram_max_retries
        return self._settings.alert_webhook_max_retries

    def _provider(self, channel: AlertDeliveryChannel) -> AlertDeliveryProvider | None:
        for provider in self._providers:
            if provider.channel == channel:
                return provider
        return None

    def _load_preferences(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> NotificationPreferencesResponse:
        if user_id is None:
            return self._preferences._defaults_response(
                organization_id=organization_id,
                user_id=uuid.UUID(int=0),
            )
        return self._preferences.get(organization_id=organization_id, user_id=user_id)

    @staticmethod
    def _store_skipped_reason(row: AlertModel, reason: str | None) -> None:
        meta = dict(row.metadata_json or {})
        if reason:
            meta["delivery_skipped_reason"] = reason
        elif "delivery_skipped_reason" in meta:
            del meta["delivery_skipped_reason"]
        row.metadata_json = meta

    def _get_row(self, alert_id: uuid.UUID, *, organization_id: uuid.UUID) -> AlertModel:
        from sqlalchemy import select

        row = self._session.scalar(
            select(AlertModel).where(
                AlertModel.id == alert_id,
                AlertModel.organization_id == organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Alert not found.")
        return row
