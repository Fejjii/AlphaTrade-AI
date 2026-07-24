"""Journal trade attachment schemas (AT-033 — Journal Completion).

Metadata only — binary content is streamed via the dedicated content endpoint
and never embedded in JSON responses.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import ORMModel, StrictModel


class JournalTradeAttachmentRead(ORMModel):
    """Attachment metadata for a journal trade."""

    id: UUID
    journal_trade_id: UUID
    organization_id: UUID
    uploaded_by: UUID | None = None
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_backend: str
    caption: str | None = None
    created_at: datetime


class JournalTradeAttachmentList(StrictModel):
    items: list[JournalTradeAttachmentRead] = Field(default_factory=list)
    total: int
