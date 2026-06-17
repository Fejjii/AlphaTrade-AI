"""Alert delivery orchestration (Slice 41 — disabled by default, paper only)."""

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
    PaperObservabilityEventType,
)
from app.services.audit_service import AuditService
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_observability_service import PaperObservabilityService

logger = structlog.get_logger("alert_delivery")


class AlertDeliveryService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        audit_service: AuditService | None = None,
        providers: list[AlertDeliveryProvider] | None = None,
        http_post: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._alerts = PaperAlertRepository(session)
        self._audit = audit_service or AuditService(session)
        self._observability = PaperObservabilityService(session)
        self._providers = providers or build_alert_delivery_providers(
            self._settings, http_post=http_post
        )

    def get_status(self) -> AlertDeliveryStatusResponse:
        webhook = self._provider(AlertDeliveryChannel.WEBHOOK)
        push = self._provider(AlertDeliveryChannel.PUSH)
        channels: list[str] = [AlertDeliveryChannel.IN_APP.value]
        if webhook and webhook.is_enabled():
            channels.append(AlertDeliveryChannel.WEBHOOK.value)
        return AlertDeliveryStatusResponse(
            delivery_enabled=self._settings.alert_delivery_enabled,
            webhook_enabled=self._settings.alert_webhook_enabled,
            telegram_enabled=self._settings.telegram_alerts_enabled,
            email_enabled=self._settings.email_alerts_enabled,
            push_enabled=push.is_enabled() if push else False,
            webhook_configured=bool(self._settings.alert_webhook_url.strip()),
            effective_external_enabled=any(
                p.is_enabled() and p.channel is not AlertDeliveryChannel.IN_APP
                for p in self._providers
            ),
            channels=channels,
            paper_only=True,
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

    def initialize_delivery_fields(self, row: AlertModel) -> None:
        if not self._settings.alert_delivery_enabled:
            row.delivery_status = AlertDeliveryStatus.DISABLED
            row.delivery_channel = AlertDeliveryChannel.IN_APP
            return
        row.delivery_status = AlertDeliveryStatus.PENDING
        row.delivery_channel = self._primary_external_channel()

    @staticmethod
    def build_payload(row: AlertModel) -> AlertDeliveryPayload:
        from datetime import UTC, datetime

        dedup = row.dedup_key or str(row.id)
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
            idempotency_key=dedup,
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

        provider = self._select_provider(row)
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
        row.delivery_attempts += 1
        row.delivery_channel = provider.channel
        try:
            outcome = provider.deliver(payload)
        except Exception as exc:
            outcome = AlertDeliveryResult(
                success=False,
                channel=provider.channel,
                error=str(exc),
            )

        now = datetime.now(UTC)
        if outcome.success:
            row.delivery_status = AlertDeliveryStatus.DELIVERED
            row.delivered_at = now
            row.last_delivery_error = None
            row.next_retry_at = None
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
            else:
                row.delivery_status = AlertDeliveryStatus.FAILED
                row.last_delivery_error = redact_text(outcome.error or "Delivery failed.")
                max_retries = self._settings.alert_webhook_max_retries
                if row.delivery_attempts <= max_retries:
                    row.next_retry_at = now + timedelta(minutes=5 * row.delivery_attempts)
                else:
                    row.next_retry_at = None
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

    def _select_provider(self, row: AlertModel) -> AlertDeliveryProvider | None:
        if row.delivery_channel != AlertDeliveryChannel.IN_APP:
            provider = self._provider(row.delivery_channel)
            if provider is not None:
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

    def _primary_external_channel(self) -> AlertDeliveryChannel:
        for channel in (
            AlertDeliveryChannel.WEBHOOK,
            AlertDeliveryChannel.TELEGRAM,
            AlertDeliveryChannel.EMAIL,
            AlertDeliveryChannel.PUSH,
        ):
            provider = self._provider(channel)
            if provider is not None and provider.is_enabled():
                return channel
        return AlertDeliveryChannel.IN_APP

    def _provider(self, channel: AlertDeliveryChannel) -> AlertDeliveryProvider | None:
        for provider in self._providers:
            if provider.channel == channel:
                return provider
        return None

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
