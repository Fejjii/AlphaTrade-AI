"""Trade journal persistence."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import TradeJournal as JournalModel
from app.repositories.journal import JournalRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import ActorType, AuditEventType
from app.schemas.journal import JournalEntry, JournalEntryCreate, JournalEntryUpdate
from app.services.audit_service import AuditService

if TYPE_CHECKING:
    from app.services.journal_rag_sync_service import JournalRagSyncService


class JournalService:
    def __init__(
        self,
        session: Session,
        audit_service: AuditService,
        *,
        rag_sync: JournalRagSyncService | None = None,
    ) -> None:
        self._repo = JournalRepository(session)
        self._audit = audit_service
        self._rag_sync = rag_sync

    def create(self, data: JournalEntryCreate) -> JournalEntry:
        if data.organization_id is None or data.user_id is None:
            raise ValueError("organization_id and user_id are required")
        row = JournalModel(
            organization_id=data.organization_id,
            user_id=data.user_id,
            symbol=str(data.symbol),
            timeframe=data.timeframe.value,
            direction=data.direction,
            strategy_id=data.strategy_id,
            entry_rationale=data.entry_rationale,
            exit_rationale=data.exit_rationale,
            emotions=data.emotions,
            mistakes=data.mistakes,
            lessons=data.lessons,
            improvement_rule=data.improvement_rule,
            result=data.result,
            pnl=data.pnl,
            stress_score=data.stress_score,
            tags=data.tags,
            screenshot_refs=data.screenshot_refs,
            linked_proposal_id=data.linked_proposal_id,
            linked_position_id=data.linked_position_id,
        )
        self._repo.add(row)
        entry = _to_schema(row)
        self._record_audit(row, "create")
        if self._rag_sync is not None:
            self._rag_sync.sync_entry(entry)
        return entry

    def list_entries(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[JournalEntry], int]:
        rows, total = self._repo.list_entries(
            organization_id=organization_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return [_to_schema(row) for row in rows], total

    def get(self, entry_id: uuid.UUID) -> JournalEntry:
        row = self._repo.get(entry_id)
        if row is None:
            raise NotFoundError("Journal entry not found")
        return _to_schema(row)

    def update(self, entry_id: uuid.UUID, data: JournalEntryUpdate) -> JournalEntry:
        row = self._repo.get(entry_id)
        if row is None:
            raise NotFoundError("Journal entry not found")
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(row, key, value)
        self._repo.add(row)
        self._record_audit(row, "update")
        entry = _to_schema(row)
        if self._rag_sync is not None:
            self._rag_sync.sync_entry(entry)
        return entry

    def delete(self, entry_id: uuid.UUID) -> None:
        row = self._repo.get(entry_id)
        if row is None:
            raise NotFoundError("Journal entry not found")
        self._record_audit(row, "delete")
        self._repo.delete(row)

    def _record_audit(self, row: JournalModel, action: str) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id="journal-api",
                trace_id="journal-api",
                event_type=AuditEventType.JOURNAL_ENTRY_CREATED,
                resource_type="journal_entry",
                resource_id=str(row.id),
                organization_id=row.organization_id,
                user_id=row.user_id,
                actor_type=ActorType.USER,
                metadata={"action": action, "symbol": row.symbol},
            )
        )


def _to_schema(row: JournalModel) -> JournalEntry:
    from app.schemas.common import Timeframe

    return JournalEntry(
        id=row.id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        symbol=row.symbol,
        timeframe=Timeframe(row.timeframe),
        direction=row.direction,
        strategy_id=row.strategy_id,
        entry_rationale=row.entry_rationale,
        exit_rationale=row.exit_rationale,
        emotions=row.emotions or [],
        mistakes=row.mistakes or [],
        lessons=row.lessons,
        improvement_rule=row.improvement_rule,
        result=row.result,
        pnl=row.pnl,
        stress_score=row.stress_score,
        tags=row.tags or [],
        screenshot_refs=row.screenshot_refs or [],
        linked_proposal_id=row.linked_proposal_id,
        linked_position_id=row.linked_position_id,
        created_at=row.created_at,
    )
