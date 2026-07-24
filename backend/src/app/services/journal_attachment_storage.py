"""Attachment byte-storage backends for journal trade evidence (AT-033).

Strategy: the platform has no durable object store and the Render filesystem
is ephemeral, so the default backend keeps bytes in Postgres (size-capped,
covered by existing database backups). The interface isolates callers from
the backend so an S3-style store can replace it later by adding a new
implementation and switching the factory — no service or schema change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models import JournalTradeAttachment


class AttachmentStorage(ABC):
    """Persistence boundary for attachment bytes (metadata stays on the row)."""

    backend: str

    @abstractmethod
    def store(self, attachment: JournalTradeAttachment, content: bytes) -> None:
        """Attach ``content`` to the (not yet flushed) attachment row."""

    @abstractmethod
    def retrieve(self, attachment: JournalTradeAttachment) -> bytes:
        """Return the stored bytes for an attachment row."""

    @abstractmethod
    def remove(self, attachment: JournalTradeAttachment) -> None:
        """Release stored bytes before the row itself is deleted."""


class DatabaseAttachmentStorage(AttachmentStorage):
    """Default backend: bytes live in ``journal_trade_attachments.content``."""

    backend = "db"

    def store(self, attachment: JournalTradeAttachment, content: bytes) -> None:
        attachment.storage_backend = self.backend
        attachment.content = content

    def retrieve(self, attachment: JournalTradeAttachment) -> bytes:
        if attachment.content is None:
            raise ValueError(
                f"Attachment {attachment.id} has backend '{attachment.storage_backend}' "
                "but no stored content."
            )
        return bytes(attachment.content)

    def remove(self, attachment: JournalTradeAttachment) -> None:
        attachment.content = None


def get_attachment_storage() -> AttachmentStorage:
    """Storage factory. DB-backed is the only implemented backend (AT-033)."""
    return DatabaseAttachmentStorage()
