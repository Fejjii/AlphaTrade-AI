"""Record paper-evaluation observations from existing authorities.

Does not evaluate setups, mint Candidates, or dispatch execution.
Watcher scan recording cannot change EvaluationOutcome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.learning_attribution.contracts import AttributionRecord, PlannedSetupQuality
from app.paper_evaluation.contracts import (
    DataQualityClass,
    PaperEvaluationObservation,
    PaperEvaluationStage,
)
from app.paper_evaluation.errors import (
    NarrativeCannotRewriteEvaluationFactsError,
    PaperEvaluationNotTradingAuthorityError,
)
from app.paper_evaluation.hashing import hashed_observation
from app.paper_evaluation.identity import observation_id_for
from app.paper_evaluation.ports import PaperEvaluationStore
from app.signal_fusion.action_eligibility import ActionEligibilityEvaluation
from app.signal_fusion.enums import ActionEligibilityState, SetupAssessmentState
from app.watcher.contracts import EvaluationCommand, EvaluationOutcome, EvaluationStatus


class PaperEvaluationRecorder:
    """Append-only measurement writer. Duplicate source identity converges."""

    def __init__(self, store: PaperEvaluationStore) -> None:
        self._store = store

    def record(self, observation: PaperEvaluationObservation) -> PaperEvaluationObservation:
        if observation.live_executable:
            raise PaperEvaluationNotTradingAuthorityError()
        hashed = hashed_observation(observation)
        if (
            hashed.content_hash != observation.content_hash
            and observation.content_hash != "0" * 64
            and observation.narrative_explanation
        ):
            raise NarrativeCannotRewriteEvaluationFactsError()
        return self._store.put(hashed)

    def record_watcher_outcome(
        self,
        command: EvaluationCommand,
        outcome: EvaluationOutcome,
        *,
        strategy_version_id: UUID | None = None,
        setup_definition_id: UUID | None = None,
        replayed: bool = False,
        occurred_at: datetime | None = None,
    ) -> tuple[PaperEvaluationObservation, PaperEvaluationObservation]:
        """Copy Watcher scan + assessment facts. Does not mint Candidates."""

        moment = occurred_at or datetime.now(UTC)
        quality = _data_quality_for(outcome, replayed=replayed)
        assessment_state = _assessment_state(outcome.reason_code)
        scan = self.record(
            _draft_observation(
                organization_id=command.request.organization_id,
                stage=PaperEvaluationStage.WATCHER_SCAN,
                source_system="watcher_fusion",
                source_event_id=str(command.command_id),
                source_event_version=1,
                occurred_at=moment,
                strategy_version_id=strategy_version_id,
                setup_definition_id=setup_definition_id,
                scan_status=outcome.status.value,
                reason_code=outcome.reason_code,
                assessment_state=assessment_state,
                setup_quality=_setup_quality(assessment_state),
                data_quality=quality,
                replayed=replayed,
            )
        )
        assessment = self.record(
            _draft_observation(
                organization_id=command.request.organization_id,
                stage=PaperEvaluationStage.SETUP_ASSESSMENT,
                source_system="watcher_setup_assessment",
                source_event_id=str(command.command_id),
                source_event_version=1,
                occurred_at=moment,
                strategy_version_id=strategy_version_id,
                setup_definition_id=setup_definition_id,
                scan_status=outcome.status.value,
                reason_code=outcome.reason_code,
                assessment_state=assessment_state,
                setup_quality=_setup_quality(assessment_state),
                data_quality=quality,
                replayed=replayed,
            )
        )
        if outcome.candidate_ids:
            self.record(
                _draft_observation(
                    organization_id=command.request.organization_id,
                    stage=PaperEvaluationStage.CANDIDATE,
                    source_system="watcher_candidate",
                    source_event_id=str(outcome.candidate_ids[0]),
                    source_event_version=1,
                    occurred_at=moment,
                    strategy_version_id=strategy_version_id,
                    setup_definition_id=setup_definition_id,
                    candidate_id=outcome.candidate_ids[0],
                    reason_code=outcome.reason_code,
                    assessment_state=assessment_state,
                    setup_quality=_setup_quality(assessment_state),
                    data_quality=quality,
                    replayed=replayed,
                )
            )
        return scan, assessment

    def record_eligibility(
        self,
        evaluation: ActionEligibilityEvaluation,
        *,
        occurred_at: datetime | None = None,
    ) -> PaperEvaluationObservation:
        eligibility = evaluation.eligibility
        reason = eligibility.reason_codes[0].value if eligibility.reason_codes else None
        return self.record(
            _draft_observation(
                organization_id=eligibility.organization_id,
                stage=PaperEvaluationStage.ELIGIBILITY,
                source_system="action_eligibility",
                source_event_id=evaluation.uniqueness_hash,
                source_event_version=evaluation.evaluation_revision,
                occurred_at=occurred_at or eligibility.checked_at,
                candidate_id=eligibility.candidate_id,
                assessment_id=eligibility.assessment_id,
                eligibility_state=eligibility.state,
                reason_code=reason,
                data_quality=(
                    DataQualityClass.UNAVAILABLE
                    if eligibility.state is ActionEligibilityState.BLOCKED
                    and reason == "blocked_data_quality"
                    else DataQualityClass.UNKNOWN
                ),
            )
        )

    def record_attribution(
        self,
        record: AttributionRecord,
        *,
        occurred_at: datetime | None = None,
    ) -> PaperEvaluationObservation:
        facts = record.facts
        pattern = facts.strategy_pattern
        return self.record(
            _draft_observation(
                organization_id=record.organization_id,
                stage=PaperEvaluationStage.ATTRIBUTION,
                source_system="learning_attribution",
                source_event_id=str(record.attribution_id),
                source_event_version=max(len(record.events), 1),
                occurred_at=occurred_at or datetime.now(UTC),
                strategy_version_id=pattern.strategy_version_id,
                setup_definition_id=pattern.setup_definition_id,
                candidate_id=record.candidate_id,
                assessment_id=facts.assessment_id,
                journal_trade_id=facts.journal_trade_id,
                reason_code=facts.trader_behavior.axis.value,
                assessment_state=facts.setup_quality.assessment_state,
                plan_approved=pattern.plan_approved,
                rejected=pattern.rejected,
                skipped=pattern.skipped,
                filled=pattern.filled,
                closed=pattern.closed,
                executed_outcome=facts.outcome.eligible,
                result=facts.outcome.result,
                net_pnl=facts.outcome.net_pnl,
                setup_quality=facts.setup_quality.axis,
                execution_quality=facts.execution_quality.axis,
                risk_adherence=facts.risk_adherence.axis,
                trader_behavior=facts.trader_behavior.axis,
                learning_venue_mode=facts.learning_venue_mode,
                narrative_explanation=record.narrative_explanation,
            )
        )


def observe_watcher_evaluation(
    recorder: PaperEvaluationRecorder,
    command: EvaluationCommand,
    outcome: EvaluationOutcome,
    *,
    strategy_version_id: UUID | None = None,
    setup_definition_id: UUID | None = None,
    replayed: bool = False,
) -> None:
    """Best-effort Watcher observer. Must not change EvaluationOutcome."""

    try:
        recorder.record_watcher_outcome(
            command,
            outcome,
            strategy_version_id=strategy_version_id,
            setup_definition_id=setup_definition_id,
            replayed=replayed,
        )
    except Exception:
        return


def _draft_observation(**kwargs: object) -> PaperEvaluationObservation:
    organization_id = kwargs["organization_id"]
    source_system = kwargs["source_system"]
    source_event_id = kwargs["source_event_id"]
    source_event_version = kwargs["source_event_version"]
    assert isinstance(organization_id, UUID)
    assert isinstance(source_system, str)
    assert isinstance(source_event_id, str)
    assert isinstance(source_event_version, int)
    payload = {
        "observation_id": observation_id_for(
            organization_id=organization_id,
            source_system=source_system,
            source_event_id=source_event_id,
            source_event_version=source_event_version,
        ),
        "content_hash": "0" * 64,
        **kwargs,
    }
    return PaperEvaluationObservation.model_validate(payload)


def _assessment_state(reason_code: str) -> SetupAssessmentState | None:
    try:
        return SetupAssessmentState(reason_code)
    except ValueError:
        return None


def _setup_quality(state: SetupAssessmentState | None) -> PlannedSetupQuality | None:
    if state is SetupAssessmentState.CONFIRMED_SETUP:
        return PlannedSetupQuality.CONFIRMED
    if state is SetupAssessmentState.INVALIDATED:
        return PlannedSetupQuality.INVALIDATED
    if state is SetupAssessmentState.EXPIRED:
        return PlannedSetupQuality.EXPIRED
    if state is not None:
        return PlannedSetupQuality.NOT_CONFIRMED
    return None


def _data_quality_for(outcome: EvaluationOutcome, *, replayed: bool) -> DataQualityClass:
    if replayed:
        return DataQualityClass.REPLAY
    reason = outcome.reason_code
    if reason in {"stale_evidence", "stale"}:
        return DataQualityClass.STALE
    if reason in {"provider_outage", "canonical_evidence_unavailable"}:
        return DataQualityClass.UNAVAILABLE
    if outcome.status is EvaluationStatus.DEGRADED:
        return DataQualityClass.DEGRADED
    if outcome.status is EvaluationStatus.FAILED:
        return DataQualityClass.UNAVAILABLE
    if outcome.status is EvaluationStatus.SUCCEEDED:
        return DataQualityClass.FRESH
    return DataQualityClass.UNKNOWN
