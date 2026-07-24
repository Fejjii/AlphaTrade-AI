"""Backfill legacy TradeJournal entries into canonical journal_trades (AT-033).

Usage:
  cd backend
  uv run python scripts/backfill_journal_entries.py                # dry-run (default)
  uv run python scripts/backfill_journal_entries.py --commit       # apply
  uv run python scripts/backfill_journal_entries.py --org <uuid>   # one organization

Idempotent: already-backfilled entries (external_ref 'legacy-journal:<id>' or an
existing link via linked_journal_entry_id) are skipped, so re-running is safe.
Legacy rows are never modified or deleted. Record-only; no execution-path change.
"""

from __future__ import annotations

import argparse
import uuid

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.audit_service import AuditService
from app.services.journal_backfill_service import JournalBackfillService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Apply the backfill. Without this flag the run is a dry-run preview.",
    )
    parser.add_argument(
        "--org",
        type=uuid.UUID,
        default=None,
        help="Restrict the backfill to one organization id.",
    )
    args = parser.parse_args()
    dry_run = not args.commit

    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        audit = AuditService(
            session,
            strict_mode=settings.observability_strict_mode,
            session_factory=factory,
        )
        service = JournalBackfillService(session, audit)
        summary = service.backfill(organization_id=args.org, dry_run=dry_run)
        if dry_run:
            session.rollback()
        else:
            session.commit()

    mode = "DRY-RUN (nothing written)" if summary.dry_run else "COMMITTED"
    print(
        f"Journal backfill {mode} — "
        f"legacy_entries={summary.total_legacy} "
        f"{'would_create' if summary.dry_run else 'created'}={summary.created} "
        f"skipped_existing={summary.skipped_existing} "
        f"organizations={summary.organizations}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
