"""ORM listeners for append-only journal lifecycle, receipts, and venue corrections."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Mapper

from app.core.errors import ValidationAppError

_registered = False


class JournalHistoryImmutabilityError(ValidationAppError):
    code = "journal_history_immutable"


def _forbid_row_mutation(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise JournalHistoryImmutabilityError(
        f"{type(target).__name__} rows are append-only and cannot be updated.",
        details={"model": type(target).__name__, "id": str(getattr(target, "id", ""))},
    )


def _forbid_row_delete(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise JournalHistoryImmutabilityError(
        f"{type(target).__name__} rows are append-only and cannot be deleted.",
        details={"model": type(target).__name__, "id": str(getattr(target, "id", ""))},
    )


def register_journal_immutability() -> None:
    """Idempotent listener registration. Called after ORM maps are defined."""

    global _registered
    if _registered:
        return
    from app.db.models import (
        JournalLifecycleEvent,
        JournalProjectionReceipt,
        JournalTradeVenueCorrection,
    )

    for model in (
        JournalLifecycleEvent,
        JournalProjectionReceipt,
        JournalTradeVenueCorrection,
    ):
        event.listen(model, "before_update", _forbid_row_mutation)
        event.listen(model, "before_delete", _forbid_row_delete)
    _registered = True
