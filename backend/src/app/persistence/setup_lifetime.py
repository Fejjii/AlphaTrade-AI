"""SQLAlchemy adapter for setup-lifetime pins.

Duplicate writes converge. Expired pins cannot resurrect. Tenant isolation is
the unique semantic key. This adapter does not evaluate setups or mint trades.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.db.setup_lifetime import SetupLifetimePin
from app.evidence_pipeline.setup_lifetime import (
    SetupLifetimeKey,
    SetupTriggerPin,
    bind_setup_trigger_pin,
    converge_setup_trigger_pin,
    utc_trigger_end,
)
from app.schemas.common import AuditEventType


class SqlAlchemySetupLifetimeStore:
    """Session-backed pins. A new process reconstructs the same lifetime."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_trigger_end(self, key: SetupLifetimeKey) -> datetime | None:
        pin = self.get(key)
        return None if pin is None or pin.expired else pin.trigger_end

    def get(self, key: SetupLifetimeKey) -> SetupTriggerPin | None:
        row = self._row(key)
        if row is None:
            return None
        return SetupTriggerPin(
            trigger_end=utc_trigger_end(row.trigger_end),
            trigger_bar_hash=row.trigger_bar_hash,
            expired=row.expired,
            required_lineage_hash=row.required_lineage_hash,
        )

    def remember(self, key: SetupLifetimeKey, pin: SetupTriggerPin) -> None:
        incoming = bind_setup_trigger_pin(key, pin)
        row = self._row(key, for_update=True)
        if row is not None:
            self._apply_merge(row, incoming)
            return
        try:
            with self._session.begin_nested():
                self._session.add(
                    SetupLifetimePin(
                        organization_id=key.organization_id,
                        symbol=key.symbol.upper(),
                        timeframe=key.timeframe.value,
                        strategy_version_id=key.strategy_version_id,
                        compiled_setup_definition_id=key.compiled_setup_definition_id,
                        compiled_content_hash=key.compiled_content_hash,
                        trigger_end=incoming.trigger_end,
                        trigger_bar_hash=incoming.trigger_bar_hash,
                        expired=incoming.expired,
                        required_lineage_hash=incoming.required_lineage_hash,
                    )
                )
                self._session.flush()
        except IntegrityError:
            row = self._row(key, for_update=True)
            if row is None:
                raise
            self._apply_merge(row, incoming)

    def expire(self, key: SetupLifetimeKey) -> None:
        row = self._row(key, for_update=True)
        if row is None or row.expired:
            return
        self._record_expiry(row)
        row.expired = True
        self._session.flush()

    def _record_expiry(self, row: SetupLifetimePin) -> None:
        # The pin row is the mutable current cursor. Preserve the retired lineage
        # before a later trigger legitimately advances that cursor via remember().
        existing = self._session.scalars(
            select(AuditLog).where(
                AuditLog.resource_type == "setup_lifetime_pin",
                AuditLog.resource_id == str(row.id),
                AuditLog.payload_hash == row.required_lineage_hash,
            )
        ).first()
        if existing is not None:
            return
        self._session.add(
            AuditLog(
                organization_id=row.organization_id,
                actor="setup_lifetime",
                action=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="setup_lifetime_pin",
                resource_id=str(row.id),
                payload_hash=row.required_lineage_hash,
                event_at=datetime.now(UTC),
                redacted_metadata={
                    "event": "setup_lifetime_pin_expired",
                    "symbol": row.symbol,
                    "timeframe": row.timeframe,
                    "strategy_version_id": str(row.strategy_version_id),
                    "compiled_setup_definition_id": str(row.compiled_setup_definition_id),
                    "compiled_content_hash": row.compiled_content_hash,
                    "trigger_end": utc_trigger_end(row.trigger_end).isoformat(),
                    "trigger_bar_hash": row.trigger_bar_hash,
                    "required_lineage_hash": row.required_lineage_hash,
                    "expired": True,
                },
            )
        )

    def clear(self, key: SetupLifetimeKey) -> None:
        row = self._row(key)
        if row is None:
            return
        self._session.delete(row)
        self._session.flush()

    def _apply_merge(self, row: SetupLifetimePin, incoming: SetupTriggerPin) -> None:
        current = SetupTriggerPin(
            trigger_end=utc_trigger_end(row.trigger_end),
            trigger_bar_hash=row.trigger_bar_hash,
            expired=row.expired,
            required_lineage_hash=row.required_lineage_hash,
        )
        merged = converge_setup_trigger_pin(current, incoming)
        if merged is None or merged == current:
            return
        if current.expired and merged.trigger_end > current.trigger_end:
            # Also preserve already-expired pins written before expiry auditing.
            self._record_expiry(row)
        row.trigger_end = merged.trigger_end
        row.trigger_bar_hash = merged.trigger_bar_hash
        row.expired = merged.expired
        row.required_lineage_hash = merged.required_lineage_hash
        self._session.flush()

    def _row(self, key: SetupLifetimeKey, *, for_update: bool = False) -> SetupLifetimePin | None:
        statement = select(SetupLifetimePin).where(
            SetupLifetimePin.organization_id == key.organization_id,
            SetupLifetimePin.symbol == key.symbol.upper(),
            SetupLifetimePin.timeframe == key.timeframe.value,
            SetupLifetimePin.strategy_version_id == key.strategy_version_id,
            SetupLifetimePin.compiled_setup_definition_id == key.compiled_setup_definition_id,
            SetupLifetimePin.compiled_content_hash == key.compiled_content_hash,
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return self._session.scalars(statement).first()


def setup_lifetime_store(session: Session) -> SqlAlchemySetupLifetimeStore:
    return SqlAlchemySetupLifetimeStore(session)


__all__ = ["SqlAlchemySetupLifetimeStore", "setup_lifetime_store"]
