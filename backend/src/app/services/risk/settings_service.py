"""User risk settings persistence and defaults (Slice 45)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DailyRiskState, UserRiskSettings
from app.db.models import User as UserModel
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import ActorType, AuditEventType, AuditResult, AuditSeverity
from app.schemas.risk import UserRiskSettingsResponse, UserRiskSettingsUpdate
from app.services.audit_service import AuditService
from app.services.risk.limits import RiskLimits


@dataclass(frozen=True)
class SystemRiskDefaults:
    daily_loss_limit: Decimal | None = None
    daily_target: Decimal | None = None
    max_trades_per_day: int = RiskLimits().max_trades_per_day
    max_risk_per_trade_percent: Decimal = Decimal("1")
    default_account_balance: Decimal = Decimal("10000")
    timezone: str = "UTC"
    green_day_protection_enabled: bool = True
    one_loss_stop_enabled: bool = False
    overtrading_guard_enabled: bool = True


SYSTEM_RISK_DEFAULTS = SystemRiskDefaults()


def normalize_timezone(timezone_name: str | None) -> tuple[str, bool]:
    label = (timezone_name or "UTC").strip() or "UTC"
    try:
        ZoneInfo(label)
        return label, False
    except Exception:
        return "UTC", True


class RiskSettingsService:
    """CRUD for tenant-scoped user risk settings."""

    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._session = session
        self._audit = audit_service

    def get(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserRiskSettingsResponse:
        row = self._load_row(organization_id=organization_id, user_id=user_id)
        if row is None:
            return self._defaults_response(organization_id=organization_id, user_id=user_id)
        return self._to_response(row, using_defaults=False)

    def update(
        self,
        payload: UserRiskSettingsUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserRiskSettingsResponse:
        self._validate_update(payload)
        row = self._load_row(organization_id=organization_id, user_id=user_id)
        if row is None:
            row = UserRiskSettings(
                organization_id=organization_id,
                user_id=user_id,
                **self._defaults_dict(),
            )
            self._session.add(row)

        changes: dict[str, str] = {}
        timezone_fallback_applied = False
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "timezone" and value is not None:
                tz, fallback = normalize_timezone(str(value))
                if fallback:
                    timezone_fallback_applied = True
                    changes["timezone_fallback"] = "true"
                setattr(row, field, tz)
                changes[field] = tz
                continue
            if value is not None or field in {"daily_loss_limit", "daily_target", "notes"}:
                setattr(row, field, value)
                changes[field] = str(value)

        self._session.flush()
        self._audit.record(
            AuditRecordCreate(
                request_id=f"risk-settings-{organization_id}",
                trace_id=str(uuid.uuid4()),
                event_type=AuditEventType.RISK_SETTINGS_UPDATED,
                organization_id=organization_id,
                user_id=user_id,
                actor_type=ActorType.USER,
                resource_type="user_risk_settings",
                resource_id=str(row.id),
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"changes": changes},
            )
        )
        return self._to_response(
            row,
            using_defaults=False,
            timezone_fallback=timezone_fallback_applied or None,
        )

    def reset_defaults(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserRiskSettingsResponse:
        row = self._load_row(organization_id=organization_id, user_id=user_id)
        defaults = self._defaults_dict()
        if row is None:
            row = UserRiskSettings(
                organization_id=organization_id,
                user_id=user_id,
                **defaults,
            )
            self._session.add(row)
        else:
            for key, value in defaults.items():
                setattr(row, key, value)
            row.notes = None

        self._session.flush()
        self._audit.record(
            AuditRecordCreate(
                request_id=f"risk-settings-{organization_id}",
                trace_id=str(uuid.uuid4()),
                event_type=AuditEventType.RISK_SETTINGS_UPDATED,
                organization_id=organization_id,
                user_id=user_id,
                actor_type=ActorType.USER,
                resource_type="user_risk_settings",
                resource_id=str(row.id),
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={"action": "reset_defaults"},
            )
        )
        return self._to_response(row, using_defaults=False)

    def ensure_daily_risk_state(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        day: date,
    ) -> DailyRiskState | None:
        """Initialize today's daily risk state from persisted settings when missing."""
        existing = self._session.scalar(
            select(DailyRiskState).where(
                DailyRiskState.organization_id == organization_id,
                DailyRiskState.user_id == user_id,
                DailyRiskState.day == day,
            )
        )
        if existing is not None:
            return existing

        settings_row = self._load_row(organization_id=organization_id, user_id=user_id)
        if settings_row is None:
            return None

        daily_loss_limit = settings_row.daily_loss_limit
        if daily_loss_limit is None:
            return None

        row = DailyRiskState(
            organization_id=organization_id,
            user_id=user_id,
            day=day,
            daily_loss_limit=daily_loss_limit,
            daily_target=settings_row.daily_target,
            max_trades_per_day=settings_row.max_trades_per_day,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _load_row(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserRiskSettings | None:
        return self._session.scalar(
            select(UserRiskSettings).where(
                UserRiskSettings.organization_id == organization_id,
                UserRiskSettings.user_id == user_id,
            )
        )

    def _defaults_dict(self) -> dict[str, object]:
        d = SYSTEM_RISK_DEFAULTS
        return {
            "daily_loss_limit": d.daily_loss_limit,
            "daily_target": d.daily_target,
            "max_trades_per_day": d.max_trades_per_day,
            "max_risk_per_trade_percent": d.max_risk_per_trade_percent,
            "default_account_balance": d.default_account_balance,
            "timezone": d.timezone,
            "green_day_protection_enabled": d.green_day_protection_enabled,
            "one_loss_stop_enabled": d.one_loss_stop_enabled,
            "overtrading_guard_enabled": d.overtrading_guard_enabled,
        }

    def _defaults_response(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserRiskSettingsResponse:
        user = self._session.get(UserModel, user_id)
        tz = user.timezone if user and user.timezone else SYSTEM_RISK_DEFAULTS.timezone
        tz_label, tz_fallback = normalize_timezone(tz)
        d = SYSTEM_RISK_DEFAULTS
        return UserRiskSettingsResponse(
            organization_id=organization_id,
            user_id=user_id,
            daily_loss_limit=d.daily_loss_limit,
            daily_target=d.daily_target,
            max_trades_per_day=d.max_trades_per_day,
            max_risk_per_trade_percent=d.max_risk_per_trade_percent,
            default_account_balance=d.default_account_balance,
            timezone=tz_label,
            green_day_protection_enabled=d.green_day_protection_enabled,
            one_loss_stop_enabled=d.one_loss_stop_enabled,
            overtrading_guard_enabled=d.overtrading_guard_enabled,
            notes=None,
            using_defaults=True,
            timezone_fallback=tz_fallback,
        )

    def _to_response(
        self,
        row: UserRiskSettings,
        *,
        using_defaults: bool,
        timezone_fallback: bool | None = None,
    ) -> UserRiskSettingsResponse:
        _, tz_fallback = normalize_timezone(row.timezone)
        if timezone_fallback is not None:
            tz_fallback = timezone_fallback
        return UserRiskSettingsResponse(
            organization_id=row.organization_id,
            user_id=row.user_id,
            daily_loss_limit=row.daily_loss_limit,
            daily_target=row.daily_target,
            max_trades_per_day=row.max_trades_per_day,
            max_risk_per_trade_percent=row.max_risk_per_trade_percent,
            default_account_balance=row.default_account_balance,
            timezone=row.timezone,
            green_day_protection_enabled=row.green_day_protection_enabled,
            one_loss_stop_enabled=row.one_loss_stop_enabled,
            overtrading_guard_enabled=row.overtrading_guard_enabled,
            notes=row.notes,
            using_defaults=using_defaults,
            timezone_fallback=tz_fallback,
        )

    def _validate_update(self, payload: UserRiskSettingsUpdate) -> None:
        if payload.daily_loss_limit is not None and payload.daily_loss_limit <= 0:
            raise ValueError("daily_loss_limit must be positive when set.")
        if payload.daily_target is not None and payload.daily_target <= 0:
            raise ValueError("daily_target must be positive when set.")
