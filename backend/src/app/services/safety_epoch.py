"""Account-scoped safety epoch locked before risk accounting.

Lock order (architecture §24):
1. account_safety_epochs
2. account_risk_accounting_states
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AccountRiskAccountingState,
    AccountSafetyEpoch,
    ExecutionAccount,
    KillSwitchState,
)
from app.repositories.execution_protocol import (
    AccountRiskAccountingRepository,
    AccountSafetyEpochRepository,
)
from app.services.execution_integrity import (
    ensure_db_transaction,
    is_risk_accounting_unique_violation,
    is_safety_epoch_unique_violation,
)
from app.services.risk.settings_service import RiskSettingsService


class SafetyEpochService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        risk_settings: RiskSettingsService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._epochs = AccountSafetyEpochRepository(session)
        self._accounting = AccountRiskAccountingRepository(session)
        self._risk_settings = risk_settings

    def lock_epoch(
        self,
        *,
        organization_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountSafetyEpoch:
        ensure_db_transaction(self._session)
        existing = self._epochs.get_for_update(
            organization_id=organization_id, account_id=account_id
        )
        if existing is not None:
            return existing
        row = AccountSafetyEpoch(
            organization_id=organization_id,
            account_id=account_id,
            epoch=1,
            blocking=self.organization_kill_active(organization_id),
            last_reason_code="initialized",
        )
        try:
            with self._session.begin_nested():
                self._epochs.add(row)
        except IntegrityError as exc:
            if not is_safety_epoch_unique_violation(exc):
                raise
        locked = self._epochs.get_for_update(organization_id=organization_id, account_id=account_id)
        if locked is None:
            raise RuntimeError("Safety epoch row missing after insert-or-lock.")
        return locked

    def lock_risk_accounting(
        self,
        *,
        organization_id: uuid.UUID,
        account_id: uuid.UUID,
        user_id: uuid.UUID,
        exposure_unit: str,
    ) -> AccountRiskAccountingState:
        ensure_db_transaction(self._session)
        existing = self._accounting.get_for_update(
            organization_id=organization_id, account_id=account_id
        )
        if existing is not None:
            return existing
        limits = self._default_limits(organization_id=organization_id, user_id=user_id)
        row = AccountRiskAccountingState(
            organization_id=organization_id,
            account_id=account_id,
            reserved_notional=Decimal("0"),
            reserved_daily_loss=Decimal("0"),
            reserved_trade_slots=0,
            actual_notional=Decimal("0"),
            actual_daily_loss=Decimal("0"),
            actual_trade_count=0,
            symbol_reserved={},
            symbol_actual={},
            max_notional=limits["max_notional"],
            max_daily_loss=limits["max_daily_loss"],
            max_trade_slots=int(limits["max_trade_slots"]),
            max_symbol_notional=limits["max_symbol_notional"],
            daily_locked=False,
            exposure_unit=exposure_unit,
            version=1,
        )
        try:
            with self._session.begin_nested():
                self._accounting.add(row)
        except IntegrityError as exc:
            if not is_risk_accounting_unique_violation(exc):
                raise
        locked = self._accounting.get_for_update(
            organization_id=organization_id, account_id=account_id
        )
        if locked is None:
            raise RuntimeError("Risk accounting row missing after insert-or-lock.")
        return locked

    def advance_for_kill_activation(
        self,
        *,
        organization_id: uuid.UUID,
        at: datetime,
    ) -> None:
        ensure_db_transaction(self._session)
        self._ensure_epochs_for_accounts(organization_id)
        rows = self._epochs.list_for_organization_for_update(organization_id)
        for row in rows:
            row.epoch = int(row.epoch) + 1
            row.blocking = True
            row.last_reason_code = "kill_switch_activated"
            row.updated_at = at
        self._session.flush()

    def clear_blocking_for_kill_deactivation(
        self,
        *,
        organization_id: uuid.UUID,
        at: datetime,
    ) -> None:
        rows = self._epochs.list_for_organization_for_update(organization_id)
        for row in rows:
            row.blocking = False
            row.last_reason_code = "kill_switch_deactivated"
            row.updated_at = at
        self._session.flush()

    def organization_kill_active(self, organization_id: uuid.UUID) -> bool:
        if self._settings.global_kill_switch_active:
            return True
        row = self._session.scalar(
            select(KillSwitchState).where(KillSwitchState.organization_id == organization_id)
        )
        return bool(row is not None and row.active)

    def _ensure_epochs_for_accounts(self, organization_id: uuid.UUID) -> None:
        account_ids = list(
            self._session.scalars(
                select(ExecutionAccount.id)
                .where(ExecutionAccount.organization_id == organization_id)
                .order_by(ExecutionAccount.id.asc())
            ).all()
        )
        for account_id in account_ids:
            self.lock_epoch(organization_id=organization_id, account_id=account_id)

    def _default_limits(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, Decimal | int]:
        settings = self._risk_settings.get(organization_id=organization_id, user_id=user_id)
        max_notional = settings.default_account_balance
        max_daily_loss = settings.daily_loss_limit or settings.default_account_balance
        return {
            "max_notional": max_notional,
            "max_daily_loss": max_daily_loss,
            "max_trade_slots": int(settings.max_trades_per_day),
            "max_symbol_notional": max_notional,
        }
