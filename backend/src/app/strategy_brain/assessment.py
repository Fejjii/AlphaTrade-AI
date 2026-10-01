"""Nested family adapter within the canonical evaluate_setup boundary."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid5

from app.market_contracts.enums import Finality, FreshnessState, MarketType
from app.market_contracts.identity import interval_timedelta
from app.schemas.nested_continuation import BrainSetupState, NestedContinuationSpec
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.adapters import AssessmentCommand, evidence_window_from_assessment_command
from app.signal_fusion.assessment import SetupAssessment, build_setup_assessment
from app.signal_fusion.enums import AssessmentReasonCode, SetupAssessmentState
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.policy import FusionPolicy
from app.signal_fusion.types import RuleResult
from app.strategy_brain.detector import NAMESPACE, detect_nested


def evaluate_nested_setup(
    *,
    policy: FusionPolicy,
    command: AssessmentCommand,
    evidence: FirstSliceEvidenceBundle,
    evaluated_at: datetime,
    spec: object,
) -> SetupAssessment:
    spec = NestedContinuationSpec.model_validate(spec)
    window = evidence_window_from_assessment_command(command)
    bars = evidence.bars_15m
    events = detect_nested(bars, spec, evaluated_at=evaluated_at)
    latest = events[-1] if events else None
    delta = interval_timedelta(spec.trigger_timeframe)
    identity_ok = (
        command.evidence_identity.instrument.provider_symbol == spec.symbol
        and command.evidence_identity.market_type is MarketType.PERPETUAL
        and command.direction == spec.direction
        and command.evidence_identity.timeframe == spec.trigger_timeframe
    )
    fresh = bool(bars) and timedelta(0) <= evaluated_at - bars[-1].interval_end < delta
    final = bool(bars) and all(
        b.finality is Finality.FINAL and b.provider_complete and b.interval_end <= evaluated_at
        for b in bars
    )
    bound = bool(bars) and command.trigger.natural_event_id == bars[-1].source_event_id
    observations_ok = (
        bool(bars)
        and len(command.public_observations) == 2
        and all(
            o.freshness_state is FreshnessState.FRESH
            and o.finality is Finality.FINAL
            and o.identity == command.evidence_identity
            for o in command.public_observations
        )
    )
    if observations_ok:
        trigger_obs, history_obs = command.public_observations
        observations_ok = (
            trigger_obs.payload_content_hash == bars[-1].content_hash
            and trigger_obs.source_event_id == bars[-1].source_event_id
            and history_obs.payload_content_hash == canonical_sha256([b.content_hash for b in bars])
        )
    policy_ok = (
        policy.required_roles == command.mandatory_evidence_roles
        and policy.strategy_version_id == command.strategy_version_id
        and policy.executable_setup == command.executable_setup
        and policy.organization_id == command.organization_id
    )
    rules = tuple(
        RuleResult(
            rule_id=name,
            passed=passed,
            reason_code=None if passed else name,
            weight=Decimal(1),
        )
        for name, passed in (
            ("market_identity", identity_ok),
            ("fresh_closed_ohlcv", fresh),
            ("final_causal_series", final),
            ("trigger_binding", bound),
            ("required_observation_binding", observations_ok),
            ("compiled_policy_binding", policy_ok),
            (
                "nested_confirmation",
                latest is not None
                and latest.state is BrainSetupState.CONFIRMED
                and latest.confirmed_index == len(bars) - 1,
            ),
        )
    )
    quality = identity_ok and fresh and final and bound and observations_ok and policy_ok
    mapping = {
        BrainSetupState.WATCH: SetupAssessmentState.WATCH,
        BrainSetupState.FORMING: SetupAssessmentState.PARTIAL_MATCH,
        BrainSetupState.CONFIRMED: SetupAssessmentState.CONFIRMED_SETUP,
        BrainSetupState.INVALIDATED: SetupAssessmentState.INVALIDATED,
        BrainSetupState.EXPIRED: SetupAssessmentState.EXPIRED,
    }
    state = mapping[latest.state] if latest and quality else SetupAssessmentState.NO_SETUP
    if state is SetupAssessmentState.CONFIRMED_SETUP and latest.confirmed_index != len(bars) - 1:
        state = SetupAssessmentState.WATCH
    reason = (
        AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED
        if state is SetupAssessmentState.CONFIRMED_SETUP
        else AssessmentReasonCode.PRECONDITIONS_PASSED
    )
    if not quality:
        reason = (
            AssessmentReasonCode.REQUIRED_SOURCE_STALE
            if not fresh
            else AssessmentReasonCode.MARKET_DISQUALIFIER
        )
    # Terminal formations cannot become candidates; wall clock never extends validity.
    validity = (
        latest.expires_at
        if latest and latest.expires_at > evaluated_at
        else evaluated_at + timedelta(seconds=1)
    )
    return build_setup_assessment(
        assessment_id=uuid5(NAMESPACE, f"assessment:{window.content_hash}:{state}"),
        organization_id=command.organization_id,
        strategy_version_id=command.strategy_version_id,
        executable_setup=command.executable_setup,
        fusion_policy_version=command.fusion_policy_version,
        observation_ids=tuple(o.observation_id for o in command.public_observations),
        assessment_window=window.interval,
        state=state,
        rule_results=rules,
        threshold=Decimal(1),
        reason_codes=(reason,),
        explanation=(
            "Operational Nested Continuation; "
            + (", ".join(latest.reason_codes) if latest else "no setup")
            + "; insufficient history"
        )[:500],
        evidence_window_hash=window.content_hash,
        assessed_at=evaluated_at,
        valid_until=validity,
        correlation_id=command.correlation_id
        or uuid5(NAMESPACE, f"correlation:{window.content_hash}"),
    )
