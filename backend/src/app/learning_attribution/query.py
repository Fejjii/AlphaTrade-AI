"""Read-only learning query service over persisted attribution facts.

Not a JournalTrade writer. Does not call RagService, mutate lessons, or
rewrite SetupAssessment / HistoricalCandle rows.
"""

from __future__ import annotations

from uuid import UUID

from app.learning_attribution.adapters.analytics import (
    AttributionAnalyticsSnapshot,
    HumanVsSystemCohortRollup,
    rollup_organization,
)
from app.learning_attribution.adapters.lessons import (
    as_human_vs_system_suggestions,
    lesson_suggestions,
)
from app.learning_attribution.adapters.rag import (
    LearningEvidenceDocument,
    learning_evidence_document,
)
from app.learning_attribution.contracts import (
    AttributionRecord,
    LearningVenueMode,
    LessonSuggestionFact,
)
from app.learning_attribution.ports import AttributionStore
from app.schemas.human_vs_system import LessonCandidateSuggestion


class LearningQueryService:
    """Tenant-scoped reads over canonical learning attribution records."""

    def __init__(self, store: AttributionStore) -> None:
        self._store = store

    def get_record(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> AttributionRecord | None:
        return self._store.get(organization_id=organization_id, candidate_id=candidate_id)

    def get_by_lifecycle(
        self,
        *,
        organization_id: UUID,
        execution_lifecycle_id: UUID,
    ) -> AttributionRecord | None:
        return self._store.get_by_lifecycle(
            organization_id=organization_id,
            execution_lifecycle_id=execution_lifecycle_id,
        )

    def list_records(
        self,
        *,
        organization_id: UUID,
        learning_venue_mode: LearningVenueMode | None = None,
    ) -> tuple[AttributionRecord, ...]:
        records = self._store.list_for_organization(organization_id)
        if learning_venue_mode is None:
            return records
        return tuple(
            record for record in records if record.facts.learning_venue_mode is learning_venue_mode
        )

    def strategy_pattern_stats(
        self,
        *,
        organization_id: UUID,
        learning_venue_mode: LearningVenueMode | None = None,
    ) -> AttributionAnalyticsSnapshot:
        return rollup_organization(
            self._store,
            organization_id=organization_id,
            learning_venue_mode=learning_venue_mode,
        )

    def human_vs_system(
        self,
        *,
        organization_id: UUID,
        learning_venue_mode: LearningVenueMode | None = None,
    ) -> HumanVsSystemCohortRollup:
        return self.strategy_pattern_stats(
            organization_id=organization_id,
            learning_venue_mode=learning_venue_mode,
        ).human_vs_system

    def rag_evidence(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> LearningEvidenceDocument | None:
        record = self.get_record(organization_id=organization_id, candidate_id=candidate_id)
        if record is None:
            return None
        return learning_evidence_document(record)

    def list_rag_evidence(
        self,
        *,
        organization_id: UUID,
        learning_venue_mode: LearningVenueMode | None = None,
    ) -> tuple[LearningEvidenceDocument, ...]:
        return tuple(
            learning_evidence_document(record)
            for record in self.list_records(
                organization_id=organization_id,
                learning_venue_mode=learning_venue_mode,
            )
        )

    def lesson_suggestions_for(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> tuple[LessonSuggestionFact, ...]:
        record = self.get_record(organization_id=organization_id, candidate_id=candidate_id)
        if record is None:
            return ()
        return lesson_suggestions(record)

    def lesson_review_suggestions_for(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> list[LessonCandidateSuggestion]:
        """Existing lesson UI shape. Callers must still POST to persist."""
        record = self.get_record(organization_id=organization_id, candidate_id=candidate_id)
        if record is None:
            return []
        return as_human_vs_system_suggestions(record)
