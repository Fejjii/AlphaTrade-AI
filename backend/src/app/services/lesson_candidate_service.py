"""Lesson candidate review workflow (Slice 37)."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import LessonCandidate as LessonCandidateModel
from app.repositories.lesson_candidates import LessonCandidateRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    DocumentSourceType,
    LessonCandidateStatus,
    LessonSeverity,
    LessonSourceType,
)
from app.schemas.lesson import (
    AcceptedLesson,
    LessonCandidate,
    LessonCandidateAccept,
    LessonCandidateArchive,
    LessonCandidateCreate,
    LessonCandidateReject,
    ProposedRuleUpdate,
)
from app.schemas.paper_eligibility import LessonSourceMetadata
from app.schemas.rag import IngestDocumentRequest
from app.services.audit_service import AuditService
from app.services.journal_rag_sync_service import sanitize_journal_text
from app.services.rag_service import RagService

logger = structlog.get_logger(__name__)

_LEGACY_STATUS_MAP = {
    "lesson_candidate": LessonCandidateStatus.PENDING_REVIEW,
    "needs_review": LessonCandidateStatus.PENDING_REVIEW,
    "accepted_lesson": LessonCandidateStatus.ACCEPTED,
    "rejected_lesson": LessonCandidateStatus.REJECTED,
}


class LessonCandidateService:
    """Store and review discipline lessons — never auto-promoted to active rules."""

    def __init__(
        self,
        session: Session,
        *,
        audit_service: AuditService | None = None,
        rag_service: RagService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._repo = LessonCandidateRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._audit = audit_service or AuditService(session)
        self._rag = rag_service
        self._settings = settings or get_settings()

    def create(
        self,
        payload: LessonCandidateCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidate:
        row = LessonCandidateModel(
            organization_id=organization_id,
            user_id=user_id,
            source_type=payload.source_type.value,
            source_id=payload.source_id,
            related_strategy_id=payload.related_strategy_id,
            trade_id=payload.related_trade_id,
            journal_entry_id=payload.related_journal_entry_id,
            related_journal_entry_id=payload.related_journal_entry_id,
            lesson_text=payload.lesson_text,
            mistake_type=payload.mistake_type,
            severity=payload.severity.value,
            confidence=payload.confidence,
            status=LessonCandidateStatus.PENDING_REVIEW.value,
            proposed_rule_update=(
                payload.proposed_rule_update.model_dump(mode="json")
                if payload.proposed_rule_update
                else None
            ),
            analysis_metadata=payload.analysis_metadata,
        )
        self._repo.add(row)
        self._audit.record(
            AuditRecordCreate(
                request_id="lesson-api",
                trace_id="lesson-api",
                organization_id=organization_id,
                user_id=user_id,
                event_type=AuditEventType.LESSON_CANDIDATE_CREATED,
                resource_type="lesson_candidate",
                resource_id=str(row.id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                metadata={
                    "source_type": payload.source_type.value,
                    "mistake_type": payload.mistake_type,
                    "status": LessonCandidateStatus.PENDING_REVIEW.value,
                },
            )
        )
        return self._to_schema(row)

    def create_candidate(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        journal_entry_id: uuid.UUID | None,
        trade_id: uuid.UUID | None,
        category: str,
        summary: str,
        status: LessonCandidateStatus = LessonCandidateStatus.PENDING_REVIEW,
        source_type: LessonSourceType = LessonSourceType.RUNNER_ANALYSIS,
        related_strategy_id: uuid.UUID | None = None,
        severity: LessonSeverity = LessonSeverity.MEDIUM,
        confidence: Decimal | None = Decimal("0.6"),
        proposed_rule_update: ProposedRuleUpdate | None = None,
        analysis_metadata: dict | None = None,
    ) -> uuid.UUID:
        """Backward-compatible helper used by discipline analyzers (Slice 36)."""
        payload = LessonCandidateCreate(
            source_type=source_type,
            source_id=journal_entry_id or trade_id,
            related_strategy_id=related_strategy_id,
            related_trade_id=trade_id,
            related_journal_entry_id=journal_entry_id,
            lesson_text=summary,
            mistake_type=category,
            severity=severity,
            confidence=confidence,
            proposed_rule_update=proposed_rule_update,
            analysis_metadata=analysis_metadata,
        )
        row_id = self.create(payload, organization_id=organization_id, user_id=user_id).id
        if status != LessonCandidateStatus.PENDING_REVIEW:
            row = self._repo.get_scoped(row_id, organization_id=organization_id, user_id=user_id)
            if row is not None:
                row.status = status.value
        return row_id

    def get(
        self,
        lesson_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidate:
        row = self._require(lesson_id, organization_id=organization_id, user_id=user_id)
        return self._to_schema(row)

    def list_candidates(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: LessonCandidateStatus | None = None,
        mistake_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[LessonCandidate], int]:
        rows, total = self._repo.list_scoped(
            organization_id=organization_id,
            user_id=user_id,
            status=status,
            mistake_type=mistake_type,
            limit=limit,
            offset=offset,
        )
        return [self._to_schema(row) for row in rows], total

    def list_accepted(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        mistake_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AcceptedLesson], int]:
        rows, total = self._repo.list_scoped(
            organization_id=organization_id,
            user_id=user_id,
            status=LessonCandidateStatus.ACCEPTED,
            mistake_type=mistake_type,
            limit=limit,
            offset=offset,
        )
        return [self._to_accepted(row) for row in rows], total

    def list_for_journal(
        self,
        journal_entry_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        rows = self._repo.list_for_journal(
            journal_entry_id, organization_id=organization_id, user_id=user_id
        )
        return [row.id for row in rows]

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: LessonCandidateStatus | None = None,
        limit: int = 50,
    ) -> list[LessonCandidate]:
        rows = self._repo.list_for_strategy(
            strategy_id,
            organization_id=organization_id,
            user_id=user_id,
            status=status,
            limit=limit,
        )
        return [self._to_schema(row) for row in rows]

    def accept(
        self,
        lesson_id: uuid.UUID,
        payload: LessonCandidateAccept,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AcceptedLesson:
        row = self._require(lesson_id, organization_id=organization_id, user_id=user_id)
        if row.status == LessonCandidateStatus.ACCEPTED.value:
            return self._to_accepted(row)
        if row.status not in {
            LessonCandidateStatus.PENDING_REVIEW.value,
            LessonCandidateStatus.REJECTED.value,
        }:
            raise ValidationAppError("Only pending or rejected lessons can be accepted.")

        rule_update = payload.accepted_rule_update or (
            ProposedRuleUpdate.model_validate(row.proposed_rule_update)
            if row.proposed_rule_update
            else None
        )
        row.status = LessonCandidateStatus.ACCEPTED.value
        row.reviewer_notes = payload.reviewer_notes
        row.reviewed_at = datetime.now(UTC)
        if rule_update is not None:
            row.accepted_rule_update = rule_update.model_dump(mode="json")

        if payload.related_strategy_id and not row.related_strategy_id:
            row.related_strategy_id = payload.related_strategy_id

        rag_doc_id: uuid.UUID | None = None
        if self._rag is not None and self._settings.journal_rag_sync_enabled:
            rag_doc_id = self._ingest_accepted_lesson(row)

        if rule_update and row.related_strategy_id:
            if payload.create_strategy_version or rule_update.create_new_version:
                self._create_strategy_version_with_rules(
                    row,
                    rule_update,
                    organization_id=organization_id,
                    user_id=user_id,
                )
            elif payload.attach_rule_to_strategy or rule_update.attach_to_strategy:
                self._attach_rules_to_strategy(
                    row.related_strategy_id,
                    rule_update,
                    organization_id=organization_id,
                    user_id=user_id,
                )

        self._audit.record(
            AuditRecordCreate(
                request_id="lesson-api",
                trace_id="lesson-api",
                organization_id=organization_id,
                user_id=user_id,
                event_type=AuditEventType.LESSON_ACCEPTED,
                resource_type="lesson_candidate",
                resource_id=str(row.id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                metadata={
                    "mistake_type": row.mistake_type,
                    "rag_ingested": rag_doc_id is not None,
                    "strategy_id": (
                        str(row.related_strategy_id) if row.related_strategy_id else None
                    ),
                },
            )
        )
        accepted = self._to_accepted(row)
        return accepted.model_copy(update={"rag_document_id": rag_doc_id})

    def reject(
        self,
        lesson_id: uuid.UUID,
        payload: LessonCandidateReject,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidate:
        row = self._require(lesson_id, organization_id=organization_id, user_id=user_id)
        if row.status == LessonCandidateStatus.ACCEPTED.value:
            raise ValidationAppError("Accepted lessons cannot be rejected — archive instead.")
        row.status = LessonCandidateStatus.REJECTED.value
        row.reviewer_notes = payload.reviewer_notes
        row.reviewed_at = datetime.now(UTC)
        self._audit.record(
            AuditRecordCreate(
                request_id="lesson-api",
                trace_id="lesson-api",
                organization_id=organization_id,
                user_id=user_id,
                event_type=AuditEventType.LESSON_REJECTED,
                resource_type="lesson_candidate",
                resource_id=str(row.id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                metadata={"mistake_type": row.mistake_type},
            )
        )
        return self._to_schema(row)

    def archive(
        self,
        lesson_id: uuid.UUID,
        payload: LessonCandidateArchive,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidate:
        row = self._require(lesson_id, organization_id=organization_id, user_id=user_id)
        previous_status = row.status
        row.status = LessonCandidateStatus.ARCHIVED.value
        if payload.reviewer_notes:
            row.reviewer_notes = payload.reviewer_notes
        row.reviewed_at = datetime.now(UTC)
        self._audit.record(
            AuditRecordCreate(
                request_id="lesson-api",
                trace_id="lesson-api",
                organization_id=organization_id,
                user_id=user_id,
                event_type=AuditEventType.LESSON_ARCHIVED,
                resource_type="lesson_candidate",
                resource_id=str(row.id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                metadata={"previous_status": previous_status},
            )
        )
        return self._to_schema(row)

    def prepare_memory_search_text(self, lesson_id: uuid.UUID) -> str | None:
        """Text prepared for RAG retrieval — accepted lessons only."""
        row = self._session.get(LessonCandidateModel, lesson_id)
        if row is None or row.status != LessonCandidateStatus.ACCEPTED.value:
            return None
        return self._build_rag_text(row)

    def _ingest_accepted_lesson(self, row: LessonCandidateModel) -> uuid.UUID | None:
        if self._rag is None:
            return None
        text = self._build_rag_text(row)
        if not text:
            return None
        request = IngestDocumentRequest(
            organization_id=row.organization_id,
            user_id=row.user_id,
            source_type=DocumentSourceType.REVIEW_NOTE,
            title=f"Accepted lesson: {row.mistake_type}",
            text=text,
            source_uri=f"lesson://{row.id}",
            risk_tag=row.severity,
        )
        result = self._rag.upsert_linked_document(request)
        meta = dict(row.analysis_metadata or {})
        meta["rag_document_id"] = str(result.document_id)
        meta["review_status"] = "accepted"
        meta["source_type"] = row.source_type
        row.analysis_metadata = meta
        logger.info("lesson_rag_ingest", lesson_id=str(row.id), document_id=str(result.document_id))
        return result.document_id

    def _build_rag_text(self, row: LessonCandidateModel) -> str:
        lines = [
            f"Status: accepted trading lesson (reviewed {row.reviewed_at or row.created_at})",
            f"Source: {row.source_type}",
            f"Mistake type: {row.mistake_type}",
            f"Severity: {row.severity}",
            f"Lesson: {row.lesson_text}",
        ]
        if row.reviewer_notes:
            lines.append(f"Reviewer notes: {row.reviewer_notes}")
        if row.accepted_rule_update:
            summary = row.accepted_rule_update.get("summary")
            if summary:
                lines.append(f"Rule update: {summary}")
        if row.analysis_metadata:
            limitations = row.analysis_metadata.get("limitations")
            if limitations:
                lines.append(f"Analysis limitations: {limitations}")
        return sanitize_journal_text("\n".join(lines))

    def _attach_rules_to_strategy(
        self,
        strategy_id: uuid.UUID,
        rule_update: ProposedRuleUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        if rule_update.structured_rules_patch is None:
            return
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Related strategy not found.")
        version = self._versions.latest(strategy_id)
        if version is None:
            raise NotFoundError("Strategy version not found.")
        version.structured_rules = rule_update.structured_rules_patch.model_dump(mode="json")

    def _create_strategy_version_with_rules(
        self,
        lesson_row: LessonCandidateModel,
        rule_update: ProposedRuleUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        strategy_id = lesson_row.related_strategy_id
        if strategy_id is None:
            raise NotFoundError("Related strategy not found.")
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Related strategy not found.")
        version = self._versions.latest(strategy_id)
        if version is None:
            raise NotFoundError("Strategy version not found.")
        strategy.current_version += 1
        card = dict(version.card)
        if rule_update.summary:
            runner_plan = list(card.get("runner_plan") or [])
            runner_plan.append(rule_update.summary)
            card["runner_plan"] = runner_plan
        from app.db.models import UserStrategyVersion as UserStrategyVersionModel

        source_metadata = LessonSourceMetadata(
            lesson_id=lesson_row.id,
            mistake_type=lesson_row.mistake_type,
            accepted_lesson_text=lesson_row.lesson_text,
            rule_update_summary=rule_update.summary,
            reviewer_notes=lesson_row.reviewer_notes,
            created_at=datetime.now(UTC),
        )
        new_version = UserStrategyVersionModel(
            strategy_id=strategy_id,
            version=strategy.current_version,
            card=card,
            validation_status=version.validation_status,
            structured_rules=(
                rule_update.structured_rules_patch.model_dump(mode="json")
                if rule_update.structured_rules_patch
                else version.structured_rules
            ),
            lesson_source_metadata=source_metadata.model_dump(mode="json"),
        )
        self._versions.add(new_version)

    def _require(
        self,
        lesson_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonCandidateModel:
        row = self._repo.get_scoped(lesson_id, organization_id=organization_id, user_id=user_id)
        if row is None:
            raise NotFoundError("Lesson candidate not found.")
        return row

    def _normalize_status(self, raw: str) -> LessonCandidateStatus:
        if raw in _LEGACY_STATUS_MAP:
            return _LEGACY_STATUS_MAP[raw]
        return LessonCandidateStatus(raw)

    def _to_schema(self, row: LessonCandidateModel) -> LessonCandidate:
        proposed = None
        if row.proposed_rule_update:
            proposed = ProposedRuleUpdate.model_validate(row.proposed_rule_update)
        accepted = None
        if row.accepted_rule_update:
            accepted = ProposedRuleUpdate.model_validate(row.accepted_rule_update)
        journal_id = row.related_journal_entry_id or row.journal_entry_id
        return LessonCandidate(
            id=row.id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            source_type=LessonSourceType(row.source_type),
            source_id=row.source_id,
            related_strategy_id=row.related_strategy_id,
            related_trade_id=row.trade_id,
            related_journal_entry_id=journal_id,
            lesson_text=row.lesson_text,
            mistake_type=row.mistake_type,
            severity=LessonSeverity(row.severity),
            confidence=row.confidence,
            status=self._normalize_status(row.status),
            proposed_rule_update=proposed,
            accepted_rule_update=accepted,
            reviewer_notes=row.reviewer_notes,
            analysis_metadata=row.analysis_metadata,
            created_at=row.created_at,
            reviewed_at=row.reviewed_at,
        )

    def _to_accepted(self, row: LessonCandidateModel) -> AcceptedLesson:
        base = self._to_schema(row)
        rag_id = None
        if row.analysis_metadata and row.analysis_metadata.get("rag_document_id"):
            with contextlib.suppress(Exception):
                rag_id = uuid.UUID(str(row.analysis_metadata["rag_document_id"]))
        return AcceptedLesson(**base.model_dump(), rag_document_id=rag_id)
