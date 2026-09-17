"""Phase 6 signal-fusion contracts and the deterministic setup-truth evaluator.

Canonical identities remain the PR 84 freeze. This package now also evaluates
first-slice ``SetupAssessment`` truth. It does not persist candidates, evaluate
ActionEligibility, run Alembic migrations, activate watcher/Telegram adapters,
or execute trades.

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
    TenantAssertionRole,
)
from app.signal_fusion.errors import (
    ConflictingSemanticInputError,
    EvidenceIdentityMismatchError,
    FormingObservationMutationError,
    FormingObservationNotExecutableError,
    IllegalAssessmentTransitionError,
    IllegalCandidateTransitionError,
    IllegalSetupIdentityError,
    TenantAssertionNotPublicError,
    TenantAssertionSelectionError,
)
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    build_canonical_evidence_window_v1,
    evidence_window_preimage,
    hash_canonical_evidence_window,
    select_identity_forming_tenant_assertions,
)
from app.signal_fusion.first_slice_types import (
    FIRST_SLICE_TICK_SIZE,
    FirstSliceEvidenceBundle,
    ManualResistanceEvidence,
)
from app.signal_fusion.observation import (
    TenantExternalAssertion,
    assert_public_observation_boundary,
    refuse_tenant_assertion_as_public_observation,
    require_distinct_observation_for_finality_change,
)
from app.signal_fusion.policy import (
    FusionPolicy,
    FusionThresholds,
    build_fusion_policy,
    first_slice_role_timeframes,
)
from app.signal_fusion.types import (
    ExecutableSetupRef,
    RoleTimeframeBinding,
    SelectedTenantAssertion,
)

__all__ = [
    "ALLOWED_ASSESSMENT_TRANSITIONS",
    "ALLOWED_CANDIDATE_TRANSITIONS",
    "FIRST_SLICE_TICK_SIZE",
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
    "ConflictingSemanticInputError",
    "DownstreamPaperValidationCandidateRef",
    "EligibilityReasonCode",
    "EvidenceAdapterKind",
    "EvidenceIdentityMismatchError",
    "EvidenceRole",
    "ExecutableSetupRef",
    "FirstSliceEvidenceBundle",
    "FormingObservationMutationError",
    "FormingObservationNotExecutableError",
    "FusionPolicy",
    "FusionThresholds",
    "IllegalAssessmentTransitionError",
    "IllegalCandidateTransitionError",
    "IllegalSetupIdentityError",
    "ManualResistanceEvidence",
    "PublicMarketObservation",
    "RoleTimeframeBinding",
    "SelectedTenantAssertion",
    "SetupAssessment",
    "SetupAssessmentState",
    "SetupAssessmentTransition",
    "SetupIdentityKind",
    "TenantAssertionNotPublicError",
    "TenantAssertionRole",
    "TenantAssertionSelectionError",
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
    "evaluate_setup",
    "evidence_window_from_assessment_command",
    "evidence_window_preimage",
    "first_slice_role_timeframes",
    "hash_canonical_evidence_window",
    "refuse_tenant_assertion_as_public_observation",
    "require_distinct_observation_for_finality_change",
    "select_identity_forming_tenant_assertions",
]
