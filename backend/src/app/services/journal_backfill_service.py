"""Legacy TradeJournal → journal_trades backfill (AT-033 / Phase 4).

Copies legacy reflection entries (table ``journals``) into canonical
``journal_trades`` rows with ``source=imported`` / ``entry_method=backfill``.
Legacy rows are never modified or deleted — the canonical row links back via
``linked_journal_entry_id`` and carries ``external_ref='legacy-journal:<id>'``.

Phase 4 maps emotions, mistakes, behavioral tags, lessons, improvement rules
and screenshots to typed observations/evidence. Lessons remain advisory.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    JournalTrade,
    JournalTradeEvidence,
    JournalTradeObservation,
    TradeJournal,
)
from app.repositories.journal_trades import JournalTradeRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    JournalEntryMethod,
    JournalEvidenceKind,
    JournalObservationCategory,
    JournalTradeSource,
    JournalTradeStatus,
    TradeResult,
)
from app.schemas.journal_lifecycle import JournalMigrationParityReport
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
    emotion_observations: int = 0
    mistake_observations: int = 0
    behavioral_observations: int = 0
    lesson_observations: int = 0
    evidence_created: int = 0
    linked_proposals: int = 0
    linked_positions: int = 0


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
        emotion_observations = 0
        mistake_observations = 0
        behavioral_observations = 0
        lesson_observations = 0
        evidence_created = 0
        linked_proposals = 0
        linked_positions = 0
        for entry in legacy_rows:
            ref = f"{_LEGACY_REF_PREFIX}{entry.id}"
            if self._already_backfilled(entry, ref):
                skipped += 1
                continue
            counts = _observation_counts(entry)
            emotion_observations += counts["emotion"]
            mistake_observations += counts["mistake"]
            behavioral_observations += counts["behavioral"]
            lesson_observations += counts["lesson"]
            evidence_created += len(entry.screenshot_refs or [])
            if entry.linked_proposal_id is not None:
                linked_proposals += 1
            if entry.linked_position_id is not None:
                linked_positions += 1
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
            emotion_observations=emotion_observations,
            mistake_observations=mistake_observations,
            behavioral_observations=behavioral_observations,
            lesson_observations=lesson_observations,
            evidence_created=evidence_created,
            linked_proposals=linked_proposals,
            linked_positions=linked_positions,
        )

    def parity_report(
        self, *, organization_id: uuid.UUID | None = None
    ) -> JournalMigrationParityReport:
        """Compare legacy rows to canonical backfill rows without writing."""
        stmt = select(TradeJournal)
        trade_stmt = select(JournalTrade).where(
            JournalTrade.entry_method == JournalEntryMethod.BACKFILL
        )
        if organization_id is not None:
            stmt = stmt.where(TradeJournal.organization_id == organization_id)
            trade_stmt = trade_stmt.where(JournalTrade.organization_id == organization_id)
        legacy_rows = list(self._session.scalars(stmt).all())
        trades = list(self._session.scalars(trade_stmt).all())
        by_legacy = {
            row.linked_journal_entry_id: row
            for row in trades
            if row.linked_journal_entry_id is not None
        }
        unmatched: list[uuid.UUID] = []
        emotion_ok = True
        mistake_ok = True
        attachment_ok = True
        linked_proposal_canonical = 0
        linked_position_canonical = 0
        for entry in legacy_rows:
            trade = by_legacy.get(entry.id)
            if trade is None:
                unmatched.append(entry.id)
                continue
            if trade.linked_proposal_id is not None:
                linked_proposal_canonical += 1
            if trade.linked_position_id is not None:
                linked_position_canonical += 1
            observations = list(
                self._session.scalars(
                    select(JournalTradeObservation).where(
                        JournalTradeObservation.journal_trade_id == trade.id
                    )
                ).all()
            )
            emotions = {
                obs.observation
                for obs in observations
                if obs.category is JournalObservationCategory.EMOTIONAL
            }
            mistakes = {
                obs.observation
                for obs in observations
                if obs.category is JournalObservationCategory.MISTAKE
            }
            if {str(item) for item in (entry.emotions or [])} != emotions:
                emotion_ok = False
            if {str(item) for item in (entry.mistakes or [])} != mistakes:
                mistake_ok = False
            evidence = list(
                self._session.scalars(
                    select(JournalTradeEvidence).where(
                        JournalTradeEvidence.journal_trade_id == trade.id
                    )
                ).all()
            )
            if len(evidence) != len(entry.screenshot_refs or []):
                attachment_ok = False
        return JournalMigrationParityReport(
            organization_id=organization_id,
            legacy_count=len(legacy_rows),
            canonical_count=len(trades),
            row_count_parity=len(legacy_rows) == len(trades) and not unmatched,
            linked_proposal_legacy=sum(
                1 for row in legacy_rows if row.linked_proposal_id is not None
            ),
            linked_proposal_canonical=linked_proposal_canonical,
            linked_position_legacy=sum(
                1 for row in legacy_rows if row.linked_position_id is not None
            ),
            linked_position_canonical=linked_position_canonical,
            emotion_parity=emotion_ok and not unmatched,
            mistake_parity=mistake_ok and not unmatched,
            attachment_parity=attachment_ok and not unmatched,
            unmatched_legacy_ids=unmatched,
        )

    def _already_backfilled(self, entry: TradeJournal, ref: str) -> bool:
        if (
            self._trades.find_by_external_ref(
                organization_id=entry.organization_id, external_ref=ref
            )
            is not None
        ):
            return True
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
        self._add_typed_observations(row, entry)
        self._session.flush()

    def _add_typed_observations(self, row: JournalTrade, entry: TradeJournal) -> None:
        observed_at = entry.created_at
        for emotion in entry.emotions or []:
            self._session.add(
                JournalTradeObservation(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    category=JournalObservationCategory.EMOTIONAL,
                    observation=str(emotion),
                    emotion_tags=[str(emotion)],
                    recorded_by=entry.user_id,
                    observed_at=observed_at,
                )
            )
        for mistake in entry.mistakes or []:
            self._session.add(
                JournalTradeObservation(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    category=JournalObservationCategory.MISTAKE,
                    observation=str(mistake),
                    emotion_tags=[],
                    recorded_by=entry.user_id,
                    observed_at=observed_at,
                )
            )
        for tag in entry.tags or []:
            self._session.add(
                JournalTradeObservation(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    category=JournalObservationCategory.BEHAVIORAL,
                    observation=str(tag),
                    emotion_tags=[],
                    recorded_by=entry.user_id,
                    observed_at=observed_at,
                )
            )
        if entry.improvement_rule:
            self._session.add(
                JournalTradeObservation(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    category=JournalObservationCategory.PROCESS,
                    observation=entry.improvement_rule,
                    emotion_tags=[],
                    recorded_by=entry.user_id,
                    observed_at=observed_at,
                )
            )
        if entry.lessons:
            self._session.add(
                JournalTradeObservation(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    category=JournalObservationCategory.LESSON,
                    observation=entry.lessons,
                    emotion_tags=[],
                    recorded_by=entry.user_id,
                    observed_at=observed_at,
                )
            )
        if entry.stress_score is not None:
            self._session.add(
                JournalTradeObservation(
                    journal_trade_id=row.id,
                    organization_id=entry.organization_id,
                    category=JournalObservationCategory.DISCIPLINE,
                    observation=f"stress_score={entry.stress_score}",
                    emotion_tags=[],
                    recorded_by=entry.user_id,
                    observed_at=observed_at,
                )
            )

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


def _observation_counts(entry: TradeJournal) -> dict[str, int]:
    return {
        "emotion": len(entry.emotions or []),
        "mistake": len(entry.mistakes or []),
        "behavioral": len(entry.tags or []),
        "lesson": 1 if entry.lessons else 0,
    }


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
