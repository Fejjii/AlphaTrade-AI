"""Named unique-constraint classification for Phase 4 journal projection."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

JOURNAL_LIFECYCLE_CONSTRAINT = "uq_journal_trades_org_lifecycle"
JOURNAL_RECEIPT_CONSTRAINT = "uq_journal_projection_receipt_source"
JOURNAL_LIFECYCLE_EVENT_CONSTRAINT = "uq_journal_lifecycle_event_source"


def is_named_unique_violation(exc: IntegrityError, constraint_name: str) -> bool:
    orig = getattr(exc, "orig", None)
    sources = [str(exc).lower()]
    if orig is not None:
        sources.append(str(orig).lower())
        diag = getattr(orig, "diag", None)
        if diag is not None:
            name = getattr(diag, "constraint_name", None)
            if name == constraint_name:
                return True
    joined = " ".join(sources)
    return constraint_name.lower() in joined


def is_journal_lifecycle_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, JOURNAL_LIFECYCLE_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return (
        "journal_trades" in message and "execution_lifecycle_id" in message and "unique" in message
    )


def is_journal_receipt_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, JOURNAL_RECEIPT_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return "journal_projection_receipts" in message and "unique" in message


def is_journal_lifecycle_event_unique_violation(exc: IntegrityError) -> bool:
    if is_named_unique_violation(exc, JOURNAL_LIFECYCLE_EVENT_CONSTRAINT):
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return "journal_lifecycle_events" in message and "unique" in message
