"""Record-only learning attribution after canonical paper journal projection.

Uses ``PostgresAttributionStore`` and ``LearningAttributionService.apply_projected``.
Does not evaluate setups, mint Candidates, or dispatch execution.

Missing Candidate, ActionEligibility, or required lineage fails closed with an
explicit ``LearningAttributionIncompleteError``. Callers must not skip learning
evidence after an ALLOW path.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import ExchangeMode, Settings
from app.learning_attribution.contracts import LearningVenueMode, TradePlanLineageRef
from app.learning_attribution.errors import (
    CrossTenantAttributionError,
    LearningAttributionIncompleteError,
)
from app.learning_attribution.service import LearningAttributionService
from app.persistence.attribution_postgres import PostgresAttributionStore
from app.runtime.canonical import ProductionCanonicalRuntime
from app.schemas.canonical_trade_plan import CanonicalTradePlanRevision
from app.schemas.journal_lifecycle import JournalLifecycleEventInput, JournalProjectionResult
from app.services.journal_lifecycle_projector import JournalLifecycleProjector
from app.signal_fusion.action_eligibility import ActionEligibilityEvaluation
from app.signal_fusion.candidate import Candidate


@dataclass(frozen=True, slots=True)
class CanonicalAttributionLineage:
    """Resolved Candidate + eligibility required to attribute a paper event."""

    candidate: Candidate
    evaluation: ActionEligibilityEvaluation


def learning_venue_mode_from_settings(settings: Settings) -> LearningVenueMode:
    if settings.exchange_mode is ExchangeMode.PAPER_EXCHANGE_DEMO:
        return LearningVenueMode.PAPER_EXCHANGE_DEMO
    return LearningVenueMode.PAPER_INTERNAL


def require_canonical_attribution_lineage(
    *,
    runtime: ProductionCanonicalRuntime,
    organization_id: UUID,
    envelope: CanonicalTradePlanRevision,
) -> CanonicalAttributionLineage:
    """Load Candidate and eligibility or fail closed with a deterministic reason."""

    if envelope.plan.organization_id != organization_id:
        raise CrossTenantAttributionError()
    candidate = runtime.lifecycle.get_by_candidate_id(
        organization_id, envelope.lineage.candidate_id
    )
    if candidate is None:
        raise LearningAttributionIncompleteError(
            "Canonical Candidate is missing; refusing to skip learning evidence.",
            reason="missing_candidate",
        )
    evaluation = runtime.eligibility.get(envelope.lineage.eligibility_uniqueness_hash)
    if evaluation is None:
        raise LearningAttributionIncompleteError(
            "ActionEligibility is missing; refusing to skip learning evidence.",
            reason="missing_eligibility",
        )
    assessment_hash = evaluation.setup_assessment_content_hash.strip()
    if not assessment_hash:
        raise LearningAttributionIncompleteError(
            "Required assessment lineage is missing; refusing to skip learning evidence.",
            reason="missing_required_lineage",
        )
    return CanonicalAttributionLineage(candidate=candidate, evaluation=evaluation)


def attribute_canonical_paper_event(
    *,
    session: Session,
    projector: JournalLifecycleProjector,
    runtime: ProductionCanonicalRuntime,
    settings: Settings,
    envelope: CanonicalTradePlanRevision,
    event: JournalLifecycleEventInput,
    projection: JournalProjectionResult,
    organization_id: UUID,
    user_id: UUID,
) -> None:
    """Persist durable attribution for one already-projected paper event."""

    resolved = require_canonical_attribution_lineage(
        runtime=runtime,
        organization_id=organization_id,
        envelope=envelope,
    )
    store = PostgresAttributionStore(session)
    service = LearningAttributionService(session, projector, store)
    service.apply_projected(
        organization_id=organization_id,
        user_id=user_id,
        candidate=resolved.candidate,
        assessment_id=envelope.lineage.assessment_id,
        assessment_content_hash=resolved.evaluation.setup_assessment_content_hash,
        evidence_window_hash=envelope.lineage.evidence_window_hash,
        trade_plan=TradePlanLineageRef(
            revision_id=envelope.plan.revision_id,
            content_hash=envelope.plan.content_hash,
            candidate_id=envelope.lineage.candidate_id,
            organization_id=envelope.plan.organization_id,
            account_id=envelope.plan.account_id,
            strategy_version_id=envelope.lineage.strategy_version_id,
            setup_definition_id=envelope.lineage.setup_definition_id,
        ),
        event=event,
        projection=projection,
        learning_venue_mode=learning_venue_mode_from_settings(settings),
    )
