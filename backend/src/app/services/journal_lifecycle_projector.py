"""Phase 4 journal lifecycle projector.

Candidate, REJECT and SKIP write lifecycle/audit events only and never create
``JournalTrade``. Approved-plan / fill / close / reconcile events resolve the
database-unique ``(organization_id, execution_lifecycle_id)`` aggregate.

This service does not enqueue workers, call exchanges, or auto-journal from
execution. Callers invoke it explicitly. Automatic projection is Phase 10.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.db.models import (
    JournalLifecycleEvent,
    JournalProjectionReceipt,
    JournalTrade,
)
from app.repositories.journal_trades import JournalTradeRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    JournalEntryMethod,
    JournalLifecycleEventType,
    JournalTradeSource,
    JournalTradeStatus,
    TradeDirection,
    TradeResult,
)
from app.schemas.journal_lifecycle import JournalLifecycleEventInput, JournalProjectionResult
from app.services.audit_service import AuditService
from app.services.canonical_serialization import canonical_sha256
from app.services.journal_integrity import (
    is_journal_lifecycle_event_unique_violation,
    is_journal_lifecycle_unique_violation,
    is_journal_receipt_unique_violation,
)

_REQUEST_TAG = "journal-lifecycle-projector"
_NON_CREATING = frozenset(
    {
        JournalLifecycleEventType.CANDIDATE_CONFIRMED,
        JournalLifecycleEventType.REJECT,
        JournalLifecycleEventType.SKIP,
    }
)
_UNRESOLVED_RECONCILIATION = frozenset({"RECONCILIATION_REQUIRED", "OPERATOR_HOLD"})
_MONEY_FIELDS = frozenset(
    {
        "planned_entry_price",
        "planned_stop_price",
        "planned_risk_amount",
        "entry_price",
        "exit_price",
        "size",
        "leverage",
        "fees",
        "funding",
        "slippage",
        "gross_pnl",
        "net_pnl",
    }
)
_UUID_FIELDS = frozenset(
    {
        "linked_position_id",
        "linked_paper_trade_id",
        "linked_proposal_id",
        "linked_order_id",
        "setup_id",
        "user_strategy_id",
        "strategy_version_id",
    }
)
_CREATE_FIELDS = frozenset(
    {
        "symbol",
        "timeframe",
        "direction",
        "exchange",
        "thesis",
        "trigger",
        "entry_plan",
        "invalidation",
        "planned_entry_price",
        "planned_stop_price",
        "planned_targets",
        "runner_enabled",
        "runner_plan",
        "planned_risk_amount",
        "strategy_label",
        "setup_id",
        "user_strategy_id",
        "strategy_version_id",
        "linked_proposal_id",
        "linked_position_id",
        "linked_paper_trade_id",
        "linked_order_id",
        "notes",
        "tags",
    }
)
_VENUE_APPLY_FIELDS = frozenset(
    {
        "entry_price",
        "entry_time",
        "exit_price",
        "exit_time",
        "exit_reason",
        "size",
        "leverage",
        "fees",
        "funding",
        "slippage",
        "gross_pnl",
        "net_pnl",
        "result",
        "status",
        "linked_order_id",
        "linked_position_id",
        "linked_paper_trade_id",
    }
)


class JournalLifecycleProjector:
    """Resolve one canonical JournalTrade per execution lifecycle."""

    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._session = session
        self._trades = JournalTradeRepository(session)
        self._audit = audit_service

    def project(
        self,
        event: JournalLifecycleEventInput,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
    ) -> JournalProjectionResult:
        self._require_provenance(event)
        existing_receipt = self._find_receipt(organization_id, event)
        if existing_receipt is not None:
            return JournalProjectionResult(
                event_type=event.event_type,
                journal_trade_id=existing_receipt.journal_trade_id,
                created_journal_trade=False,
                replayed=True,
                skipped_reason=existing_receipt.skipped_reason,
            )

        skipped_reason: str | None = None
        trade: JournalTrade | None = None
        created = False

        if event.event_type in _NON_CREATING:
            skipped_reason = "non_creating_lifecycle_event"
        elif event.execution_lifecycle_id is None:
            skipped_reason = "missing_execution_lifecycle"
        elif self._close_blocked(event):
            skipped_reason = "unresolved_reconciliation"
        else:
            trade, created = self._resolve_lifecycle_trade(
                event,
                organization_id=organization_id,
                user_id=user_id,
            )
            if trade is not None:
                self._apply_event(trade, event)

        content_hash = self._event_hash(organization_id, event)
        lifecycle_event = self._insert_lifecycle_event(
            event,
            organization_id=organization_id,
            user_id=user_id,
            actor_user_id=actor_user_id,
            journal_trade_id=trade.id if trade is not None else None,
            content_hash=content_hash,
        )
        receipt = self._insert_receipt(
            event,
            organization_id=organization_id,
            user_id=user_id,
            journal_trade_id=trade.id if trade is not None else None,
            created_journal_trade=created,
            skipped_reason=skipped_reason,
            content_hash=content_hash,
        )
        if receipt is not None and trade is None and receipt.journal_trade_id is not None:
            trade = self._trades.get_scoped(
                receipt.journal_trade_id, organization_id=organization_id
            )
            created = False

        resource_id: str | None = None
        if trade is not None:
            resource_id = str(trade.id)
        elif lifecycle_event is not None:
            resource_id = str(lifecycle_event.id)
        self._audit.record(
            AuditRecordCreate(
                request_id=_REQUEST_TAG,
                trace_id=event.correlation_id or _REQUEST_TAG,
                event_type=AuditEventType.JOURNAL_LIFECYCLE_PROJECTED,
                resource_type="journal_trade" if trade is not None else "journal_lifecycle_event",
                resource_id=resource_id,
                organization_id=organization_id,
                user_id=user_id,
                actor_type=ActorType.SYSTEM,
                metadata={
                    "event_type": event.event_type.value,
                    "created_journal_trade": created,
                    "skipped_reason": skipped_reason,
                    "replayed": False,
                },
            )
        )
        return JournalProjectionResult(
            event_type=event.event_type,
            journal_trade_id=trade.id if trade is not None else None,
            created_journal_trade=created,
            replayed=False,
            skipped_reason=skipped_reason,
        )

    def _require_provenance(self, event: JournalLifecycleEventInput) -> None:
        if not event.source_system or not event.source_aggregate or not event.source_event_id:
            raise ValidationAppError(
                "Journal projection requires source_system, source_aggregate, and source_event_id.",
                details={"reason": "missing_provenance"},
            )

    def _close_blocked(self, event: JournalLifecycleEventInput) -> bool:
        if event.event_type not in {
            JournalLifecycleEventType.CLOSE,
            JournalLifecycleEventType.RECONCILE,
        }:
            return False
        status = event.payload.get("reconciliation_status")
        if status is None:
            return False
        return str(status) in _UNRESOLVED_RECONCILIATION

    def _find_receipt(
        self,
        organization_id: uuid.UUID,
        event: JournalLifecycleEventInput,
    ) -> JournalProjectionReceipt | None:
        stmt = select(JournalProjectionReceipt).where(
            JournalProjectionReceipt.organization_id == organization_id,
            JournalProjectionReceipt.source_system == event.source_system,
            JournalProjectionReceipt.source_aggregate == event.source_aggregate,
            JournalProjectionReceipt.event_type == event.event_type,
            JournalProjectionReceipt.source_event_id == event.source_event_id,
            JournalProjectionReceipt.source_event_version == event.source_event_version,
            JournalProjectionReceipt.supersession == event.supersession,
        )
        return self._session.scalar(stmt)

    def _event_hash(self, organization_id: uuid.UUID, event: JournalLifecycleEventInput) -> str:
        return canonical_sha256(
            {
                "organization_id": str(organization_id),
                "event_type": event.event_type.value,
                "execution_lifecycle_id": (
                    str(event.execution_lifecycle_id) if event.execution_lifecycle_id else None
                ),
                "source_system": event.source_system,
                "source_aggregate": event.source_aggregate,
                "source_event_id": event.source_event_id,
                "source_event_version": event.source_event_version,
                "supersession": event.supersession,
                "payload": event.payload,
            }
        )

    def _insert_lifecycle_event(
        self,
        event: JournalLifecycleEventInput,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        journal_trade_id: uuid.UUID | None,
        content_hash: str,
    ) -> JournalLifecycleEvent | None:
        row = JournalLifecycleEvent(
            organization_id=organization_id,
            user_id=user_id,
            account_id=event.account_id,
            event_type=event.event_type,
            execution_lifecycle_id=event.execution_lifecycle_id,
            source_system=event.source_system,
            source_aggregate=event.source_aggregate,
            source_event_id=event.source_event_id,
            source_event_version=event.source_event_version,
            supersession=event.supersession,
            payload=dict(event.payload),
            content_hash=content_hash,
            correlation_id=event.correlation_id,
            actor_user_id=actor_user_id,
            journal_trade_id=journal_trade_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
            return row
        except IntegrityError as exc:
            if not is_journal_lifecycle_event_unique_violation(exc):
                raise
            return self._session.scalar(
                select(JournalLifecycleEvent).where(
                    JournalLifecycleEvent.organization_id == organization_id,
                    JournalLifecycleEvent.source_system == event.source_system,
                    JournalLifecycleEvent.source_aggregate == event.source_aggregate,
                    JournalLifecycleEvent.event_type == event.event_type,
                    JournalLifecycleEvent.source_event_id == event.source_event_id,
                    JournalLifecycleEvent.source_event_version == event.source_event_version,
                    JournalLifecycleEvent.supersession == event.supersession,
                )
            )

    def _insert_receipt(
        self,
        event: JournalLifecycleEventInput,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        journal_trade_id: uuid.UUID | None,
        created_journal_trade: bool,
        skipped_reason: str | None,
        content_hash: str,
    ) -> JournalProjectionReceipt | None:
        row = JournalProjectionReceipt(
            organization_id=organization_id,
            user_id=user_id,
            account_id=event.account_id,
            event_type=event.event_type,
            execution_lifecycle_id=event.execution_lifecycle_id,
            source_system=event.source_system,
            source_aggregate=event.source_aggregate,
            source_event_id=event.source_event_id,
            source_event_version=event.source_event_version,
            supersession=event.supersession,
            journal_trade_id=journal_trade_id,
            created_journal_trade=created_journal_trade,
            skipped_reason=skipped_reason,
            content_hash=content_hash,
            correlation_id=event.correlation_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
            return row
        except IntegrityError as exc:
            if not is_journal_receipt_unique_violation(exc):
                raise
            return self._find_receipt(organization_id, event)

    def _resolve_lifecycle_trade(
        self,
        event: JournalLifecycleEventInput,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[JournalTrade | None, bool]:
        assert event.execution_lifecycle_id is not None
        existing = self._trades.find_by_execution_lifecycle(
            organization_id=organization_id,
            execution_lifecycle_id=event.execution_lifecycle_id,
        )
        if existing is not None:
            if existing.organization_id != organization_id:
                raise ValidationAppError(
                    "Execution lifecycle belongs to another organization.",
                    details={"reason": "cross_tenant_lifecycle"},
                )
            return existing, False

        symbol = event.payload.get("symbol")
        timeframe = event.payload.get("timeframe")
        direction_raw = event.payload.get("direction")
        if not isinstance(symbol, str) or not isinstance(timeframe, str) or direction_raw is None:
            raise ValidationAppError(
                "Approved-plan/fill projection requires symbol, timeframe, and direction.",
                details={"reason": "missing_instrument_identity"},
            )
        direction = (
            direction_raw
            if isinstance(direction_raw, TradeDirection)
            else TradeDirection(str(direction_raw))
        )
        row = JournalTrade(
            organization_id=organization_id,
            user_id=user_id,
            source=JournalTradeSource.PAPER_EXECUTION,
            entry_method=JournalEntryMethod.AUTO,
            status=JournalTradeStatus.PLANNED,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            execution_lifecycle_id=event.execution_lifecycle_id,
            tags=[],
            planned_targets=[],
        )
        self._apply_create_fields(row, event.payload)
        try:
            with self._session.begin_nested():
                self._trades.add(row)
            return row, True
        except IntegrityError as exc:
            if not is_journal_lifecycle_unique_violation(exc):
                raise
            winner = self._trades.find_by_execution_lifecycle(
                organization_id=organization_id,
                execution_lifecycle_id=event.execution_lifecycle_id,
            )
            if winner is None:
                raise
            return winner, False

    def _apply_create_fields(self, row: JournalTrade, payload: dict[str, object]) -> None:
        for key in _CREATE_FIELDS:
            if key not in payload:
                continue
            setattr(row, key, _coerce_field(key, payload[key]))

    def _apply_event(self, row: JournalTrade, event: JournalLifecycleEventInput) -> None:
        if event.event_type is JournalLifecycleEventType.APPROVED_PLAN:
            self._apply_create_fields(row, event.payload)
            if row.status is JournalTradeStatus.PLANNED:
                row.status = JournalTradeStatus.PLANNED
            return
        if event.event_type is JournalLifecycleEventType.FILL:
            self._apply_venue_fields(row, event.payload)
            if row.status is JournalTradeStatus.PLANNED:
                row.status = JournalTradeStatus.OPEN
            if row.result is TradeResult.OPEN:
                row.result = TradeResult.OPEN
            return
        if event.event_type is JournalLifecycleEventType.CLOSE:
            self._apply_venue_fields(row, event.payload)
            row.status = JournalTradeStatus.CLOSED
            return
        if event.event_type is JournalLifecycleEventType.RECONCILE:
            self._apply_venue_fields(row, event.payload)

    def _apply_venue_fields(self, row: JournalTrade, payload: dict[str, object]) -> None:
        for key in _VENUE_APPLY_FIELDS:
            if key not in payload:
                continue
            setattr(row, key, _coerce_field(key, payload[key]))


def _coerce_field(key: str, value: object) -> Any:
    if value is None:
        return None
    if key in _MONEY_FIELDS:
        return Decimal(str(value))
    if key in _UUID_FIELDS:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    if key == "direction":
        return value if isinstance(value, TradeDirection) else TradeDirection(str(value))
    if key == "status":
        return value if isinstance(value, JournalTradeStatus) else JournalTradeStatus(str(value))
    if key == "result":
        return value if isinstance(value, TradeResult) else TradeResult(str(value))
    if key in {"entry_time", "exit_time"} and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value
