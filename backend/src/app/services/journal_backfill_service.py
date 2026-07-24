"""Legacy TradeJournal → journal_trades backfill (AT-033 — Journal Completion).

Copies legacy reflection entries (table ``journals``) into canonical
``journal_trades`` rows with ``source=imported`` / ``entry_method=backfill``.
Legacy rows are never modified or deleted — the canonical row links back via
``linked_journal_entry_id`` and carries ``external_ref='legacy-journal:<id>'``,
which makes the backfill idempotent (and DB-enforced by the partial unique
index). Screenshot refs are preserved as evidence records.

Used by ``backend/scripts/backfill_journal_entries.py``; dry-run by default.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import JournalTrade, JournalTradeEvidence, TradeJournal
from app.repositories.journal_trades import JournalTradeRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    JournalEntryMethod,
    JournalEvidenceKind,
    JournalTradeSource,
    JournalTradeStatus,
    TradeResult,
)
from app.services.audit_service import AuditService

_REQUEST_TAG = "journal-backfill-cli"
_LEGACY_REF_PREFIX = "legacy-journal:"


@dataclass(frozen=True, slots=True)
class BackfillSummary:
    """Outcome of one backfill run (per invocation, all orgs in scope)."""

    dry_run: bool
    total_legacy: int
    created: int
    skipped_existing: int
    organizations: int


class JournalBackfillService:
    """Idempotent TradeJournal → journal_trades backfill."""

    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._session = session
        self._trades = JournalTradeRepository(session)
        self._audit = audit_service

    def backfill(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        dry_run: bool = True,
    ) -> BackfillSummary:
        """Backfill all legacy entries (optionally scoped to one organization).

        Dry-run counts what would be created without writing anything.
        The caller owns the transaction (script commits, tests may roll back).
        """
        stmt = select(TradeJournal).order_by(TradeJournal.created_at.asc(), TradeJournal.id.asc())
        if organization_id is not None:
            stmt = stmt.where(TradeJournal.organization_id == organization_id)
        legacy_rows = list(self._session.scalars(stmt).all())

        created_by_org: dict[uuid.UUID, int] = {}
        skipped = 0
        for entry in legacy_rows:
            ref = f"{_LEGACY_REF_PREFIX}{entry.id}"
            if self._already_backfilled(entry, ref):
                skipped += 1
                continue
            if not dry_run:
                self._create_canonical(entry, ref)
            created_by_org[entry.organization_id] = created_by_org.get(entry.organization_id, 0) + 1

        if not dry_run:
            for org_id, count in created_by_org.items():
                self._record_backfill_audit(org_id, created=count, skipped=skipped)

        return BackfillSummary(
            dry_run=dry_run,
            total_legacy=len(legacy_rows),
            created=sum(created_by_org.values()),
            skipped_existing=skipped,
            organizations=len({row.organization_id for row in legacy_rows}),
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _already_backfilled(self, entry: TradeJournal, ref: str) -> bool:
        if (
            self._trades.find_by_external_ref(
                organization_id=entry.organization_id, external_ref=ref
            )
            is not None
        ):
            return True
        # Also respect manual links created before AT-033.
        linked = self._session.scalar(
            select(JournalTrade.id).where(
                JournalTrade.organization_id == entry.organization_id,
                JournalTrade.linked_journal_entry_id == entry.id,
            )
        )
        return linked is not None

    def _create_canonical(self, entry: TradeJournal, ref: str) -> None:
        is_closed = entry.result is not TradeResult.OPEN
        row = JournalTrade(
            organization_id=entry.organization_id,
            user_id=entry.user_id,
            source=JournalTradeSource.IMPORTED,
            entry_method=JournalEntryMethod.BACKFILL,
            status=JournalTradeStatus.CLOSED if is_closed else JournalTradeStatus.OPEN,
            symbol=entry.symbol,
            timeframe=entry.timeframe,
            direction=entry.direction,
            strategy_label=entry.strategy_id.value if entry.strategy_id is not None else None,
            thesis=entry.entry_rationale,
            net_pnl=entry.pnl,
            result=entry.result,
            notes=_compose_notes(entry),
            tags=list(entry.tags or []),
            linked_proposal_id=entry.linked_proposal_id,
            linked_position_id=entry.linked_position_id,
            linked_journal_entry_id=entry.id,
            external_ref=ref,
        )
        self._trades.add(row)
        for screenshot_ref in entry.screenshot_refs or []:
            self._session.add(
                JournalTradeEvidence(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    kind=JournalEvidenceKind.SCREENSHOT,
                    ref=str(screenshot_ref)[:1024],
                    caption="Backfilled from legacy journal entry.",
                    recorded_by=entry.user_id,
                )
            )
        self._session.flush()

    def _record_backfill_audit(
        self, organization_id: uuid.UUID, *, created: int, skipped: int
    ) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id=_REQUEST_TAG,
                trace_id=_REQUEST_TAG,
                event_type=AuditEventType.JOURNAL_BACKFILL_COMPLETED,
                resource_type="journal_trade",
                organization_id=organization_id,
                actor_type=ActorType.SYSTEM,
                metadata={"created_count": created, "skipped_existing": skipped},
            )
        )


def _compose_notes(entry: TradeJournal) -> str | None:
    """Fold legacy reflection fields into the canonical free-text notes."""
    sections: list[str] = []
    if entry.exit_rationale:
        sections.append(f"Exit rationale: {entry.exit_rationale}")
    if entry.lessons:
        sections.append(f"Lessons: {entry.lessons}")
    if entry.improvement_rule:
        sections.append(f"Improvement rule: {entry.improvement_rule}")
    if entry.emotions:
        sections.append(f"Emotions: {', '.join(str(e) for e in entry.emotions)}")
    if entry.mistakes:
        sections.append(f"Mistakes: {', '.join(str(m) for m in entry.mistakes)}")
    return "\n".join(sections) or None
