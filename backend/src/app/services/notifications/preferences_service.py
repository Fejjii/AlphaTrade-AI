"""User notification preferences persistence (Slice 46)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserNotificationPreferences
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AlertDeliveryChannel,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    NotificationDigestMode,
    PaperAlertSeverity,
    PaperAlertType,
)
from app.schemas.notifications import (
    ChannelProviderStatus,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationTestResult,
)
from app.services.audit_service import AuditService
from app.services.delivery_routing_service import _provider_configured, _provider_env_enabled
from app.services.risk.settings_service import normalize_timezone


class NotificationPreferencesService:
    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._session = session
        self._audit = audit_service

    def get(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationPreferencesResponse:
        row = self._load_row(organization_id=organization_id, user_id=user_id)
        if row is None:
            return self._defaults_response(organization_id=organization_id, user_id=user_id)
        return self._to_response(row, using_defaults=False)

    def update(
        self,
        payload: NotificationPreferencesUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationPreferencesResponse:
        self._validate_update(payload)
        row = self._load_row(organization_id=organization_id, user_id=user_id)
        if row is None:
            row = UserNotificationPreferences(
                organization_id=organization_id,
                user_id=user_id,
                **self._defaults_dict(),
            )
            self._session.add(row)

        changes: dict[str, str] = {}
        timezone_fallback = False
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "timezone" and value is not None:
                tz, fallback = normalize_timezone(str(value))
                if fallback:
                    timezone_fallback = True
                    changes["timezone_fallback"] = "true"
                setattr(row, field, tz)
                changes[field] = tz
                continue
            if field == "enabled_alert_types" and value is not None:
                stored = [t.value if isinstance(t, PaperAlertType) else str(t) for t in value]
                setattr(row, field, stored)
                changes[field] = ",".join(stored)
                continue
            if field == "digest_mode" and value is not None:
                setattr(row, field, value.value)
                changes[field] = value.value
                continue
            if field == "min_severity" and value is not None:
                setattr(row, field, value)
                changes[field] = value.value
                continue
            setattr(row, field, value)
            changes[field] = str(value)

        self._session.flush()
        self._audit.record(
            AuditRecordCreate(
                request_id=f"notification-prefs-{organization_id}",
                trace_id=str(uuid.uuid4()),
                event_type=AuditEventType.NOTIFICATION_PREFERENCES_UPDATED,
                organization_id=organization_id,
                user_id=user_id,
                actor_type=ActorType.USER,
                resource_type="user_notification_preferences",
                resource_id=str(row.id),
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"changes": changes},
            )
        )
        return self._to_response(
            row,
            using_defaults=False,
            timezone_fallback=timezone_fallback or None,
        )

    def reset_defaults(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationPreferencesResponse:
        row = self._load_row(organization_id=organization_id, user_id=user_id)
        if row is None:
            row = UserNotificationPreferences(
                organization_id=organization_id,
                user_id=user_id,
                **self._defaults_dict(),
            )
            self._session.add(row)
        else:
            for key, value in self._defaults_dict().items():
                setattr(row, key, value)

        self._session.flush()
        self._audit.record(
            AuditRecordCreate(
                request_id=f"notification-prefs-reset-{organization_id}",
                trace_id=str(uuid.uuid4()),
                event_type=AuditEventType.NOTIFICATION_PREFERENCES_UPDATED,
                organization_id=organization_id,
                user_id=user_id,
                actor_type=ActorType.USER,
                resource_type="user_notification_preferences",
                resource_id=str(row.id),
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": "reset_defaults"},
            )
        )
        return self._to_response(row, using_defaults=False)

    def channel_statuses(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        settings: object,
    ) -> list[ChannelProviderStatus]:
        from app.core.config import Settings

        cfg = settings if isinstance(settings, Settings) else Settings()
        prefs = self.get(organization_id=organization_id, user_id=user_id)
        statuses: list[ChannelProviderStatus] = []
        for channel_name, user_flag in (
            ("webhook", prefs.webhook_enabled),
            ("telegram", prefs.telegram_enabled),
        ):
            ch = (
                AlertDeliveryChannel.WEBHOOK
                if channel_name == "webhook"
                else AlertDeliveryChannel.TELEGRAM
            )
            env_on = _provider_env_enabled(ch, cfg)
            configured = _provider_configured(ch, cfg)
            available = env_on and configured and user_flag and cfg.alert_delivery_enabled
            if not cfg.alert_delivery_enabled or not env_on:
                label = "disabled"
            elif not configured:
                label = "not_configured"
            elif not user_flag:
                label = "user_disabled"
            else:
                label = "configured"
            statuses.append(
                ChannelProviderStatus(
                    channel=channel_name,
                    env_enabled=env_on,
                    user_enabled=user_flag,
                    configured=configured,
                    available=available,
                    status_label=label,
                )
            )
        return statuses

    def build_test_result(
        self,
        *,
        delivery_results: dict[str, bool],
        errors: dict[str, str],
        skipped: list[str],
    ) -> NotificationTestResult:
        attempted = list(delivery_results.keys())
        succeeded = [k for k, ok in delivery_results.items() if ok]
        return NotificationTestResult(
            success=bool(succeeded),
            message=(
                f"Test notification sent to {len(succeeded)} channel(s)."
                if succeeded
                else "Test notification could not be delivered externally."
            ),
            channels_attempted=attempted,
            channels_succeeded=succeeded,
            channels_skipped=skipped,
            errors=errors,
        )

    def _load_row(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserNotificationPreferences | None:
        return self._session.scalar(
            select(UserNotificationPreferences).where(
                UserNotificationPreferences.organization_id == organization_id,
                UserNotificationPreferences.user_id == user_id,
            )
        )

    @staticmethod
    def _defaults_dict() -> dict[str, object]:
        return {
            "in_app_enabled": True,
            "webhook_enabled": False,
            "telegram_enabled": False,
            "min_severity": PaperAlertSeverity.INFO,
            "enabled_alert_types": None,
            "quiet_hours_enabled": False,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "timezone": "UTC",
            "digest_mode": NotificationDigestMode.IMMEDIATE.value,
            "telegram_chat_id": None,
        }

    def _defaults_response(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationPreferencesResponse:
        defaults = self._defaults_dict()
        return NotificationPreferencesResponse(
            organization_id=organization_id,
            user_id=user_id,
            in_app_enabled=bool(defaults["in_app_enabled"]),
            webhook_enabled=bool(defaults["webhook_enabled"]),
            telegram_enabled=bool(defaults["telegram_enabled"]),
            min_severity=defaults["min_severity"],
            enabled_alert_types=None,
            quiet_hours_enabled=bool(defaults["quiet_hours_enabled"]),
            quiet_hours_start=None,
            quiet_hours_end=None,
            timezone=str(defaults["timezone"]),
            digest_mode=NotificationDigestMode.IMMEDIATE,
            telegram_chat_id=None,
            using_defaults=True,
        )

    def _to_response(
        self,
        row: UserNotificationPreferences,
        *,
        using_defaults: bool,
        timezone_fallback: bool | None = None,
    ) -> NotificationPreferencesResponse:
        enabled_types: list[PaperAlertType] | None = None
        if row.enabled_alert_types:
            enabled_types = []
            for raw in row.enabled_alert_types:
                try:
                    enabled_types.append(PaperAlertType(raw))
                except ValueError:
                    continue
        try:
            digest = NotificationDigestMode(row.digest_mode)
        except ValueError:
            digest = NotificationDigestMode.IMMEDIATE
        return NotificationPreferencesResponse(
            organization_id=row.organization_id,
            user_id=row.user_id,
            in_app_enabled=row.in_app_enabled,
            webhook_enabled=row.webhook_enabled,
            telegram_enabled=row.telegram_enabled,
            min_severity=row.min_severity,
            enabled_alert_types=enabled_types,
            quiet_hours_enabled=row.quiet_hours_enabled,
            quiet_hours_start=row.quiet_hours_start,
            quiet_hours_end=row.quiet_hours_end,
            timezone=row.timezone,
            digest_mode=digest,
            telegram_chat_id=row.telegram_chat_id,
            using_defaults=using_defaults,
            timezone_fallback=bool(timezone_fallback),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _validate_update(self, payload: NotificationPreferencesUpdate) -> None:
        if payload.min_severity is not None and payload.min_severity not in PaperAlertSeverity:
            raise ValueError("Invalid minimum severity.")

    @staticmethod
    def severity_meets_minimum(
        severity: PaperAlertSeverity,
        minimum: PaperAlertSeverity,
    ) -> bool:
        from app.services.delivery_routing_service import _SEVERITY_RANK

        return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(minimum, 0)
