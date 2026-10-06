"""Preview a single tenant/owner/account-scoped Journal target repair; --apply commits."""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from app.db.session import get_session_factory
from app.services.audit_service import AuditService
from app.services.journal_lifecycle_projector import JournalLifecycleProjector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("organization-id", "user-id", "account-id", "journal-trade-id", "revision-id"):
        parser.add_argument(f"--{flag}", type=UUID, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply after reviewing the dry-run.")
    args = parser.parse_args()
    with get_session_factory()() as session:
        result = JournalLifecycleProjector(session, AuditService(session)).repair_planned_targets(
            organization_id=args.organization_id,
            user_id=args.user_id,
            account_id=args.account_id,
            journal_trade_id=args.journal_trade_id,
            revision_id=args.revision_id,
            dry_run=not args.apply,
        )
        if args.apply:
            session.commit()
        else:
            session.rollback()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
