"""Phase 6 canonical contracts for observations, fusion, assessment, and candidates.

This package freezes typed immutable contracts and CanonicalEvidenceWindowV1
hashing. It does not implement the fusion evaluator, candidate persistence,
Alembic migrations, watcher/Telegram/TradingView adapters, risk evaluation,
alerts, outbox, execution, or frontend.

Public market facts reuse ``app.market_contracts.PublicMarketObservation``.
Venue, instrument, timeframe, direction, strategy, setup, freshness, and
market identities are reused from Phase 3 and Phase 5. Setup truth and
ActionEligibility remain separate contracts.
"""

from app.market_contracts.observation import PublicMarketObservation
from app.signal_fusion.adapters import (
    AssessmentCommand,
    DownstreamPaperValidationCandidateRef,
    evidence_window_from_assessment_command,
)
from app.signal_fusion.assessment import (
    ALLOWED_ASSESSMENT_TRANSITIONS,
    SetupAssessment,
    SetupAssessmentTransition,
    build_setup_assessment,
    build_setup_assessment_transition,
)
from app.signal_fusion.candidate import (
    ALLOWED_CANDIDATE_TRANSITIONS,
    TERMINAL_CANDIDATE_STATES,
    Candidate,
    CandidateTransition,
    CandidateUniquenessTuple,
    build_candidate,
    build_candidate_transition,
    build_confirmed_candidate,
)
from app.signal_fusion.eligibility import ActionEligibility, build_action_eligibility
from app.signal_fusion.enums import (
    ActionEligibilityState,
    AssessmentReasonCode,
    CandidateReasonCode,
    CandidateState,
    EligibilityReasonCode,
    EvidenceAdapterKind,
    EvidenceRole,
    SetupAssessmentState,
    SetupIdentityKind,
)
from app.signal_fusion.errors import (
    FormingObservationMutationError,
    FormingObservationNotExecutableError,
    IllegalAssessmentTransitionError,
    IllegalCandidateTransitionError,
    IllegalSetupIdentityError,
    TenantAssertionNotPublicError,
)
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    build_canonical_evidence_window_v1,
    evidence_window_preimage,
    hash_canonical_evidence_window,
)
from app.signal_fusion.observation import (
    TenantExternalAssertion,
    assert_public_observation_boundary,
    refuse_tenant_assertion_as_public_observation,
    require_distinct_observation_for_finality_change,
)
from app.signal_fusion.policy import FusionPolicy, FusionThresholds, build_fusion_policy
from app.signal_fusion.types import ExecutableSetupRef

__all__ = [
    "ALLOWED_ASSESSMENT_TRANSITIONS",
    "ALLOWED_CANDIDATE_TRANSITIONS",
    "TERMINAL_CANDIDATE_STATES",
    "ActionEligibility",
    "ActionEligibilityState",
    "AssessmentCommand",
    "AssessmentReasonCode",
    "Candidate",
    "CandidateReasonCode",
    "CandidateState",
    "CandidateTransition",
    "CandidateUniquenessTuple",
    "CanonicalEvidenceWindowV1",
    "DownstreamPaperValidationCandidateRef",
    "EligibilityReasonCode",
    "EvidenceAdapterKind",
    "EvidenceRole",
    "ExecutableSetupRef",
    "FormingObservationMutationError",
    "FormingObservationNotExecutableError",
    "FusionPolicy",
    "FusionThresholds",
    "IllegalAssessmentTransitionError",
    "IllegalCandidateTransitionError",
    "IllegalSetupIdentityError",
    "PublicMarketObservation",
    "SetupAssessment",
    "SetupAssessmentState",
    "SetupAssessmentTransition",
    "SetupIdentityKind",
    "TenantAssertionNotPublicError",
    "TenantExternalAssertion",
    "assert_public_observation_boundary",
    "build_action_eligibility",
    "build_candidate",
    "build_candidate_transition",
    "build_canonical_evidence_window_v1",
    "build_confirmed_candidate",
    "build_fusion_policy",
    "build_setup_assessment",
    "build_setup_assessment_transition",
    "evidence_window_from_assessment_command",
    "evidence_window_preimage",
    "hash_canonical_evidence_window",
    "refuse_tenant_assertion_as_public_observation",
    "require_distinct_observation_for_finality_change",
]
