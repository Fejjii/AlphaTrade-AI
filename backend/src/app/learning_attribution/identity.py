"""Deterministic attribution identity. Not a Candidate or JournalTrade authority."""

from __future__ import annotations

from uuid import UUID, uuid5

from app.learning_attribution.contracts import LineageSnapshot, TradePlanLineageRef
from app.schemas.journal_lifecycle import JournalLineagePayload
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate

ATTRIBUTION_NAMESPACE = UUID("7e1a7b51-0c4e-4d7a-9f3a-21a0d0a7b051")
ATTRIBUTION_EVENT_NAMESPACE = UUID("8e2b8c62-1d5f-4e8b-a04b-32b1e1b8c162")


def attribution_id_for(*, organization_id: UUID, candidate_id: UUID) -> UUID:
    """Stable aggregate id: one learning record per org-owned candidate."""
    return uuid5(ATTRIBUTION_NAMESPACE, f"{organization_id}:{candidate_id}")


def attribution_event_id_for(
    *,
    organization_id: UUID,
    account_id: UUID,
    source_system: str,
    source_aggregate: str,
    event_type: str,
    source_event_id: str,
    source_event_version: int,
    supersession: int,
) -> UUID:
    """Stable event id: one row per journal source identity within an organization."""
    return uuid5(
        ATTRIBUTION_EVENT_NAMESPACE,
        ":".join(
            (
                str(organization_id),
                str(account_id),
                source_system,
                source_aggregate,
                event_type,
                source_event_id,
                str(source_event_version),
                str(supersession),
            )
        ),
    )


def lineage_payload_from_snapshot(snapshot: LineageSnapshot) -> dict[str, object]:
    """Nested payload fragment stored on append-only journal lifecycle events."""
    candidate = snapshot.candidate
    assessment = snapshot.assessment
    plan = snapshot.trade_plan
    payload = JournalLineagePayload(
        organization_id=candidate.organization_id,
        account_id=snapshot.account_id,
        execution_lifecycle_id=snapshot.execution_lifecycle_id,
        candidate_id=candidate.candidate_id,
        candidate_content_hash=candidate.content_hash,
        assessment_id=assessment.assessment_id,
        assessment_content_hash=assessment.content_hash,
        evidence_window_hash=candidate.evidence_window_hash,
        trade_plan_revision_id=None if plan is None else plan.revision_id,
        trade_plan_content_hash=None if plan is None else plan.content_hash,
        setup_definition_id=candidate.setup_definition_id,
        strategy_version_id=candidate.strategy_version_id,
        fusion_policy_version=candidate.fusion_policy_version,
        uniqueness_tuple_hash=candidate.uniqueness_tuple().canonical_hash(),
    )
    return payload.model_dump(mode="json", exclude_none=True)


def require_matching_hashes(
    *,
    assessment: SetupAssessment,
    candidate: Candidate,
    trade_plan: TradePlanLineageRef | None,
) -> None:
    """Lineage pointers must agree. Does not re-evaluate setup truth."""
    if candidate.assessment_id != assessment.assessment_id:
        raise ValueError("candidate.assessment_id does not match SetupAssessment.")
    if candidate.evidence_window_hash != assessment.evidence_window_hash:
        raise ValueError("Candidate evidence_window_hash does not match SetupAssessment.")
    if candidate.organization_id != assessment.organization_id:
        raise ValueError("Candidate organization does not match SetupAssessment.")
    if candidate.strategy_version_id != assessment.strategy_version_id:
        raise ValueError("Candidate strategy_version_id does not match SetupAssessment.")
    if candidate.setup_definition_id != assessment.setup_definition_id:
        raise ValueError("Candidate setup_definition_id does not match SetupAssessment.")
    if candidate.fusion_policy_version != assessment.fusion_policy_version:
        raise ValueError("Candidate fusion_policy_version does not match SetupAssessment.")
    if trade_plan is None:
        return
    if trade_plan.candidate_id != candidate.candidate_id:
        raise ValueError("TradePlan lineage candidate_id does not match Candidate.")
    if trade_plan.organization_id != candidate.organization_id:
        raise ValueError("TradePlan lineage organization does not match Candidate.")
    if trade_plan.strategy_version_id != candidate.strategy_version_id:
        raise ValueError("TradePlan lineage strategy_version_id does not match Candidate.")
    if trade_plan.setup_definition_id != candidate.setup_definition_id:
        raise ValueError("TradePlan lineage setup_definition_id does not match Candidate.")
