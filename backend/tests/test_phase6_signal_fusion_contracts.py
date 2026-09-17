"""Phase 6 contract freeze: immutability, identity, and CanonicalEvidenceWindowV1 hashing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.market_contracts.enums import Finality, MarketType, PrivacyClass, VenueId
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.observation import PublicMarketObservation
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.adapters import (
    DownstreamPaperValidationCandidateRef,
    evidence_window_from_assessment_command,
)
from app.signal_fusion.assessment import build_setup_assessment, build_setup_assessment_transition
from app.signal_fusion.candidate import (
    TERMINAL_CANDIDATE_STATES,
    CandidateUniquenessTuple,
    build_candidate_transition,
    build_confirmed_candidate,
    uniqueness_preimage,
)
from app.signal_fusion.eligibility import build_action_eligibility
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
    TenantAssertionNotPublicError,
)
from app.signal_fusion.evidence_window import (
    EVIDENCE_WINDOW_EXCLUDED_INPUTS,
    assert_excluded_from_preimage,
    build_canonical_evidence_window_v1,
    evidence_window_preimage,
)
from app.signal_fusion.observation import (
    assert_public_observation_boundary,
    refuse_tenant_assertion_as_public_observation,
    require_distinct_observation_for_finality_change,
)
from app.signal_fusion.types import (
    ExecutableSetupRef,
    PresentationEvidenceRef,
    RuleResult,
    SelectedPublicObservation,
    TenantAssertionRef,
)
from tests.support.phase5_market import EVALUATED_AT, TRIGGER_OPEN, eth_instrument
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    ACTION_ID,
    ASSESSMENT_ID,
    CANDIDATE_ID,
    CORRELATION_A,
    CORRELATION_B,
    ELIGIBILITY_ID,
    ORG_ID,
    RISK_SNAPSHOT_ID,
    SCAN_ID,
    SETUP_CONTENT_HASH,
    STRATEGY_VERSION_ID,
    USER_ID,
    VALID_UNTIL,
    VENUE_STATE_ID,
    assessment_command,
    executable_setup,
    fusion_policy,
    interval,
    manual_level,
    presentation_evidence,
    public_observation,
    tenant_assertion,
    window_kwargs,
)


def _build_window(**overrides: object):
    payload = window_kwargs()
    payload.update(overrides)
    return build_canonical_evidence_window_v1(**payload)  # type: ignore[arg-type]


def test_public_market_observation_is_phase5_envelope() -> None:
    observation = public_observation()
    assert isinstance(observation, PublicMarketObservation)
    assert observation.privacy_class is PrivacyClass.PUBLIC_MARKET_DATA
    assert "organization_id" not in type(observation).model_fields
    assert assert_public_observation_boundary(observation) is observation


def test_tenant_assertion_cannot_become_public_observation() -> None:
    assertion = tenant_assertion()
    assert "organization_id" in type(assertion).model_fields
    with pytest.raises(TenantAssertionNotPublicError, match="cannot become"):
        refuse_tenant_assertion_as_public_observation(assertion)


def test_public_observation_is_immutable() -> None:
    observation = public_observation()
    with pytest.raises(ValidationError, match="frozen"):
        observation.finality = Finality.FINAL  # type: ignore[misc]


def test_forming_cannot_mutate_into_final() -> None:
    forming = public_observation().model_copy(update={"finality": Finality.FORMING})
    mutated = forming.model_copy(update={"finality": Finality.FINAL})
    assert forming.observation_id == mutated.observation_id
    with pytest.raises(FormingObservationMutationError, match="cannot mutate"):
        require_distinct_observation_for_finality_change(forming, mutated)
    distinct_final = public_observation(index=9)
    assert distinct_final.observation_id != forming.observation_id
    require_distinct_observation_for_finality_change(forming, distinct_final)


def test_forming_observation_cannot_occupy_executable_role() -> None:
    forming = public_observation().model_copy(update={"finality": Finality.FORMING})
    with pytest.raises(
        (ValidationError, FormingObservationNotExecutableError), match="cannot select"
    ):
        SelectedPublicObservation(
            role=EvidenceRole.TRIGGER_OHLCV,
            content_hash=forming.content_hash,
            finality=forming.finality,
            observation_id=forming.observation_id,
        )


def test_fusion_policy_is_immutable_and_decimal_normalized() -> None:
    left = fusion_policy(threshold=Decimal("1.0"))
    right = fusion_policy(threshold=Decimal("1.00"))
    assert left.content_hash == right.content_hash
    with pytest.raises(ValidationError, match="frozen"):
        left.policy_version = "other"  # type: ignore[misc]
    assert "account_id" not in type(left).model_fields
    assert "risk_snapshot_id" not in type(left).model_fields


def test_fusion_policy_rejects_global_setup_template() -> None:
    with pytest.raises(ValidationError, match="CompiledSetupDefinition"):
        ExecutableSetupRef(
            setup_definition_id=uuid4(),
            kind=SetupIdentityKind.GLOBAL_SETUP_TEMPLATE,
            content_hash=SETUP_CONTENT_HASH,
        )


def test_setup_assessment_has_no_account_or_risk_fields() -> None:
    window = _build_window()
    assessment = build_setup_assessment(
        assessment_id=ASSESSMENT_ID,
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=executable_setup(),
        fusion_policy_version=fusion_policy().policy_version,
        observation_ids=(public_observation().observation_id,),
        assessment_window=interval(),
        state=SetupAssessmentState.CONFIRMED_SETUP,
        previous_assessment_id=None,
        previous_state=SetupAssessmentState.PARTIAL_MATCH,
        rule_results=(
            RuleResult(
                rule_id="mandatory_evidence",
                passed=True,
                weight=Decimal("1.0"),
                reason_code=AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED.value,
                evidence_role=EvidenceRole.TRIGGER_OHLCV,
            ),
        ),
        threshold=Decimal("1.00"),
        reason_codes=(AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED,),
        explanation="All mandatory evidence confirmed under first-slice-fusion/v1.",
        evidence_window_hash=window.content_hash,
        assessed_at=EVALUATED_AT,
        valid_until=VALID_UNTIL,
        correlation_id=CORRELATION_A,
    )
    fields = set(type(assessment).model_fields)
    assert not {"user_id", "account_id", "risk_snapshot_id", "venue_state_id"} & fields
    with pytest.raises(ValidationError, match="frozen"):
        assessment.state = SetupAssessmentState.NO_SETUP  # type: ignore[misc]
    decimal_twin = build_setup_assessment(
        assessment_id=ASSESSMENT_ID,
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=executable_setup(),
        fusion_policy_version=fusion_policy().policy_version,
        observation_ids=assessment.observation_ids,
        assessment_window=interval(),
        state=SetupAssessmentState.CONFIRMED_SETUP,
        previous_state=SetupAssessmentState.PARTIAL_MATCH,
        rule_results=(
            RuleResult(
                rule_id="mandatory_evidence",
                passed=True,
                weight=Decimal("1.00"),
                reason_code=AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED.value,
                evidence_role=EvidenceRole.TRIGGER_OHLCV,
            ),
        ),
        threshold=Decimal("1.0"),
        reason_codes=(AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED,),
        explanation=assessment.explanation,
        evidence_window_hash=window.content_hash,
        assessed_at=EVALUATED_AT,
        valid_until=VALID_UNTIL,
        correlation_id=CORRELATION_A,
    )
    assert assessment.content_hash == decimal_twin.content_hash


def test_setup_assessment_transition_requires_distinct_window_after_expiry() -> None:
    window = _build_window()
    adjacent = _build_window(interval=interval(end=TRIGGER_OPEN + timedelta(minutes=30)))
    build_setup_assessment_transition(
        previous_assessment_id=ASSESSMENT_ID,
        previous_state=SetupAssessmentState.EXPIRED,
        previous_evidence_window_hash=window.content_hash,
        new_state=SetupAssessmentState.NO_SETUP,
        evidence_window_hash=adjacent.content_hash,
        evidence_observation_hashes=tuple(
            item.content_hash for item in adjacent.selected_public_observations
        ),
        rule_results=(),
        weights=(),
        threshold=Decimal("1"),
        reason_codes=(AssessmentReasonCode.DISTINCT_EVIDENCE_WINDOW,),
        assessed_at=EVALUATED_AT,
        valid_until=VALID_UNTIL,
        correlation_id=CORRELATION_A,
    )
    with pytest.raises(ValidationError, match="distinct evidence window"):
        build_setup_assessment_transition(
            previous_assessment_id=ASSESSMENT_ID,
            previous_state=SetupAssessmentState.EXPIRED,
            previous_evidence_window_hash=window.content_hash,
            new_state=SetupAssessmentState.NO_SETUP,
            evidence_window_hash=window.content_hash,
            evidence_observation_hashes=(),
            rule_results=(),
            threshold=Decimal("1"),
            reason_codes=(AssessmentReasonCode.DISTINCT_EVIDENCE_WINDOW,),
            assessed_at=EVALUATED_AT,
            valid_until=VALID_UNTIL,
            correlation_id=CORRELATION_A,
        )


def test_action_eligibility_is_separate_from_setup_truth() -> None:
    window = _build_window()
    eligibility = build_action_eligibility(
        eligibility_id=ELIGIBILITY_ID,
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        candidate_id=CANDIDATE_ID,
        candidate_revision=1,
        assessment_id=ASSESSMENT_ID,
        risk_snapshot_id=RISK_SNAPSHOT_ID,
        venue_state_id=VENUE_STATE_ID,
        state=ActionEligibilityState.BLOCKED,
        reason_codes=(EligibilityReasonCode.BLOCKED_KILL_SWITCH,),
        checked_at=EVALUATED_AT,
        valid_until=VALID_UNTIL,
        correlation_id=CORRELATION_A,
    )
    assert eligibility.state is ActionEligibilityState.BLOCKED
    assert "state" in type(eligibility).model_fields
    assert set(SetupAssessmentState) != set(ActionEligibilityState)
    with pytest.raises(ValidationError, match="frozen"):
        eligibility.state = ActionEligibilityState.ELIGIBLE  # type: ignore[misc]
    assert window.content_hash  # setup window is independent of eligibility


def test_candidate_uniqueness_tuple_canonical_serialization() -> None:
    window = _build_window()
    first = CandidateUniquenessTuple(
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        setup_definition_id=executable_setup().setup_definition_id,
        fusion_policy_version=fusion_policy().policy_version,
        direction=TradeDirection.SHORT,
        evidence_venue=VenueId.BINANCE,
        evidence_market=MarketType.PERPETUAL,
        evidence_instrument=first_slice_identity(
            timeframe=Timeframe.M15, replay=True
        ).instrument.instrument_id,
        timeframe=Timeframe.M15,
        evidence_window_hash=window.content_hash,
    )
    second = CandidateUniquenessTuple(
        evidence_window_hash=window.content_hash,
        timeframe=Timeframe.M15,
        evidence_instrument=first.evidence_instrument,
        evidence_market=MarketType.PERPETUAL,
        evidence_venue=VenueId.BINANCE,
        direction=TradeDirection.SHORT,
        fusion_policy_version=first.fusion_policy_version,
        setup_definition_id=first.setup_definition_id,
        strategy_version_id=STRATEGY_VERSION_ID,
        organization_id=ORG_ID,
    )
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.canonical_hash() == second.canonical_hash()
    assert list(uniqueness_preimage(first)) == sorted(uniqueness_preimage(first))


def test_confirmed_candidate_starts_active() -> None:
    window = _build_window()
    identity = first_slice_identity(timeframe=Timeframe.M15, replay=True)
    candidate = build_confirmed_candidate(
        candidate_id=CANDIDATE_ID,
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=executable_setup(),
        fusion_policy_version=fusion_policy().policy_version,
        direction=TradeDirection.SHORT,
        assessment_id=ASSESSMENT_ID,
        evidence_window_hash=window.content_hash,
        evidence_identity=identity,
        evidence_venue=identity.venue,
        evidence_market=identity.market_type,
        evidence_instrument=identity.instrument.instrument_id,
        timeframe=Timeframe.M15,
        created_at=EVALUATED_AT,
        valid_until=VALID_UNTIL,
        idempotency_key="candidate-active-1",
        correlation_id=CORRELATION_A,
    )
    assert candidate.state is CandidateState.ACTIVE
    assert candidate.uniqueness_tuple().evidence_window_hash == window.content_hash
    with pytest.raises(ValidationError, match="frozen"):
        candidate.state = CandidateState.REJECTED  # type: ignore[misc]


@pytest.mark.parametrize("terminal", sorted(TERMINAL_CANDIDATE_STATES, key=lambda item: item.value))
def test_terminal_candidate_cannot_resurrect_to_active(terminal: CandidateState) -> None:
    with pytest.raises(ValidationError, match="resurrected"):
        build_candidate_transition(
            previous_state=terminal,
            new_state=CandidateState.ACTIVE,
            transition_version=2,
            reason_codes=(CandidateReasonCode.CONFIRMED_SETUP,),
            occurred_at=EVALUATED_AT,
            correlation_id=CORRELATION_A,
            idempotency_key="resurrect-illegal",
        )


def test_active_candidate_may_transition_to_plan_created() -> None:
    transition = build_candidate_transition(
        previous_state=CandidateState.ACTIVE,
        new_state=CandidateState.PLAN_CREATED,
        transition_version=2,
        reason_codes=(CandidateReasonCode.PLAN_CREATED,),
        occurred_at=EVALUATED_AT,
        correlation_id=CORRELATION_A,
        idempotency_key="plan-created-1",
    )
    assert transition.new_state is CandidateState.PLAN_CREATED


def test_same_semantic_window_hashes_identically() -> None:
    left = _build_window()
    right = _build_window()
    assert left.content_hash == right.content_hash
    assert_excluded_from_preimage(evidence_window_preimage(left))
    leaked = EVIDENCE_WINDOW_EXCLUDED_INPUTS.intersection(evidence_window_preimage(left))
    assert not leaked


def test_correlation_scan_action_and_presentation_do_not_change_hash() -> None:
    baseline = _build_window()
    ignored = _build_window(
        correlation_id=CORRELATION_B,
        scan_id=SCAN_ID,
        action_id=ACTION_ID,
        receive_time=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
        presentation_evidence=(
            presentation_evidence("overlay-a"),
            PresentationEvidenceRef(label="overlay-b", content_hash="44" * 32),
        ),
        adapter_kind=EvidenceAdapterKind.TRADINGVIEW.value,
    )
    assert baseline.content_hash == ignored.content_hash


def test_evidence_role_ordering_does_not_change_hash() -> None:
    baseline = _build_window()
    shuffled_roles = (
        EvidenceRole.CVD_WINDOW,
        EvidenceRole.TRIGGER_OHLCV,
        EvidenceRole.CONTEXT_OHLCV,
    )
    shuffled_selected = tuple(reversed(baseline.selected_public_observations))
    ordered = _build_window(
        mandatory_evidence_roles=shuffled_roles,
        selected_public_observations=shuffled_selected,
        source_set=tuple(reversed(baseline.source_set)),
    )
    assert ordered.content_hash == baseline.content_hash
    assert ordered.mandatory_evidence_roles == tuple(
        sorted(shuffled_roles, key=lambda role: role.value)
    )


def test_timezone_normalization_does_not_change_hash() -> None:
    baseline = _build_window()
    offset = timezone(timedelta(hours=2))
    start = datetime(2026, 1, 15, 18, 0, tzinfo=offset)
    end = datetime(2026, 1, 15, 18, 15, tzinfo=offset)
    normalized = _build_window(interval=interval(start=start, end=end))
    assert start.astimezone(UTC) == TRIGGER_OPEN
    assert normalized.content_hash == baseline.content_hash


def test_required_observation_content_change_changes_hash() -> None:
    baseline = _build_window()
    trigger = public_observation(index=9)
    replaced = tuple(
        SelectedPublicObservation(
            role=EvidenceRole.TRIGGER_OHLCV,
            content_hash=trigger.content_hash,
            finality=Finality.FINAL,
            observation_id=trigger.observation_id,
        )
        if item.role is EvidenceRole.TRIGGER_OHLCV
        else item
        for item in baseline.selected_public_observations
    )
    changed = _build_window(selected_public_observations=replaced)
    assert changed.content_hash != baseline.content_hash


def test_strategy_version_change_changes_hash() -> None:
    baseline = _build_window()
    changed = _build_window(strategy_version_id=uuid4())
    assert changed.content_hash != baseline.content_hash


def test_compiled_setup_hash_change_changes_hash() -> None:
    baseline = _build_window()
    changed = _build_window(compiled_setup_content_hash="ab" * 32)
    assert changed.content_hash != baseline.content_hash


def test_manual_level_revision_change_changes_hash() -> None:
    baseline = _build_window()
    changed = _build_window(manual_level_revision=manual_level(revision_number=2))
    assert changed.content_hash != baseline.content_hash


@pytest.mark.parametrize(
    "field",
    ["fusion_policy_version", "finality_policy_version", "freshness_policy_version"],
)
def test_policy_version_change_changes_hash(field: str) -> None:
    baseline = _build_window()
    changed = _build_window(**{field: "mutated-policy/v9"})
    assert changed.content_hash != baseline.content_hash


def test_venue_or_instrument_change_changes_hash() -> None:
    baseline = _build_window()
    mutated_identity = first_slice_identity(timeframe=Timeframe.M15, replay=True).model_copy(
        update={
            "instrument": eth_instrument(),
            "venue": VenueId.BINANCE,
        }
    )
    changed = _build_window(evidence_identity=mutated_identity)
    assert changed.content_hash != baseline.content_hash
    assert changed.evidence_instrument != baseline.evidence_instrument


def test_adjacent_evidence_window_changes_hash() -> None:
    baseline = _build_window()
    adjacent = _build_window(
        interval=interval(
            start=TRIGGER_OPEN + timedelta(minutes=15),
            end=TRIGGER_OPEN + timedelta(minutes=30),
        )
    )
    assert adjacent.content_hash != baseline.content_hash


def test_watcher_detector_and_tradingview_converge() -> None:
    hashes = {
        evidence_window_from_assessment_command(
            assessment_command(
                adapter_kind=kind,
                correlation_id=uuid4(),
                presentation_label=kind.value,
            )
        ).content_hash
        for kind in (
            EvidenceAdapterKind.WATCHER,
            EvidenceAdapterKind.DETECTOR,
            EvidenceAdapterKind.TRADINGVIEW,
        )
    }
    assert len(hashes) == 1
    assert hashes.pop() == _build_window().content_hash


def test_observation_id_excluded_from_window_hash() -> None:
    baseline = _build_window()
    relabeled = []
    for item in baseline.selected_public_observations:
        relabeled.append(item.model_copy(update={"observation_id": uuid4()}))
    changed = _build_window(selected_public_observations=tuple(relabeled))
    assert changed.content_hash == baseline.content_hash


def test_downstream_paper_validation_candidate_is_not_uniqueness_key() -> None:
    ref = DownstreamPaperValidationCandidateRef(
        paper_validation_candidate_id=uuid4(),
        canonical_candidate_id=CANDIDATE_ID,
    )
    fields = set(CandidateUniquenessTuple.model_fields)
    assert "paper_validation_candidate_id" not in fields
    assert ref.canonical_candidate_id == CANDIDATE_ID


def test_required_tenant_assertion_changes_window_hash() -> None:
    baseline = _build_window()
    assertion = tenant_assertion()
    changed = _build_window(
        tenant_assertions=(
            TenantAssertionRef(
                assertion_id=assertion.assertion_id,
                content_hash=assertion.content_hash,
            ),
        )
    )
    assert changed.content_hash != baseline.content_hash
