"""Note storage with scoped reads, revision checks and non-destructive Undo."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.agent_capture.contracts import SavedEntriesPage, SavedEntry, SavedEntryUpdate
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.models import AgentSavedEntry


def entry_record(row: AgentSavedEntry) -> SavedEntry:
    return SavedEntry(
        id=row.id,
        category=row.category,
        title=row.title,
        summary=row.summary,
        original_text=row.original_text,
        conversation_id=row.conversation_id,
        source_message_ids=row.sources.get("message_ids", []),
        source_document_id=row.sources.get("document_id"),
        trade_id=row.sources.get("trade_id"),
        tags=row.sources.get("tags", []),
        draft=row.draft,
        revision=row.revision,
        undone=row.undone,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def scope(organization_id: UUID, user_id: UUID) -> tuple[ColumnElement[bool], ...]:
    return (AgentSavedEntry.organization_id == organization_id, AgentSavedEntry.user_id == user_id)


def require_entry(
    session: Session, entry_id: UUID, organization_id: UUID, user_id: UUID, *, lock: bool = False
) -> AgentSavedEntry:
    query = select(AgentSavedEntry).where(
        AgentSavedEntry.id == entry_id, *scope(organization_id, user_id)
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        raise NotFoundError("Saved entry not found.")
    return row


def list_entries(
    session: Session,
    organization_id: UUID,
    user_id: UUID,
    *,
    category: str | None = None,
    view: str | None = None,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> SavedEntriesPage:
    query = select(AgentSavedEntry).where(
        *scope(organization_id, user_id), AgentSavedEntry.undone.is_(False)
    )
    if view == "knowledge":
        query = query.where(AgentSavedEntry.category != "journal")
    elif view == "journal":
        query = query.where(AgentSavedEntry.category == "journal")
    if category:
        query = query.where(AgentSavedEntry.category == category)
    if q.strip():
        # Escape LIKE wildcards: a search for '%' should not match every note.
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            AgentSavedEntry.title.ilike(f"%{term}%", escape="\\")
            | AgentSavedEntry.summary.ilike(f"%{term}%", escape="\\")
            | AgentSavedEntry.original_text.ilike(f"%{term}%", escape="\\")
        )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(AgentSavedEntry.updated_at.desc(), AgentSavedEntry.id)
        .limit(limit)
        .offset(offset)
    )
    return SavedEntriesPage(items=[entry_record(row) for row in rows], total=total)


def snapshot(row: AgentSavedEntry) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in ("category", "title", "summary", "original_text", "sources", "draft", "undone")
    }


def update_entry(
    session: Session, entry_id: UUID, body: SavedEntryUpdate, organization_id: UUID, user_id: UUID
) -> SavedEntry:
    row = require_entry(session, entry_id, organization_id, user_id, lock=True)
    if row.revision != body.expected_revision:
        raise ConflictError("This entry changed. Reload before correcting or undoing it.")
    if row.undone:
        return entry_record(row)
    if body.undo and any((body.category, body.title, body.summary)):
        raise ValidationAppError("Undo cannot include a correction.")
    before = snapshot(row)
    if body.undo:
        previous = (row.history or [])[-1] if row.history else None
        if previous:
            for key, value in previous.items():
                setattr(row, key, value)
            row.history = list(row.history[:-1])
        else:
            row.undone = True
    else:
        row.history = [*(row.history or []), before]
        for key in ("category", "title", "summary"):
            value = getattr(body, key)
            if value is not None:
                setattr(row, key, value)
        # Reclassification cannot create a draft, discard one, or grant automation.
    row.revision += 1
    row.updated_at = datetime.now(UTC)
    session.flush()
    return entry_record(row)
