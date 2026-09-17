"""Builders for Phase 6 signal-fusion contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.analysis.wilder_atr_v1 import FINALITY_POLICY_VERSION
from app.market_contracts.enums import Finality, FreshnessState, SourceFamily, VenueId
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.freshness import FIRST_SLICE_FRESHNESS_POLICY_VERSION
from app.market_contracts.identity import (
    EvidenceMarketIdentity,
    canonical_instrument_id,
    interval_timedelta,
)
from app.market_contracts.observation import PublicMarketObservation, observation_from_ohlcv
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.adapters import AssessmentCommand
from app.signal_fusion.enums import (
    AssertionSource,
    EvidenceAdapterKind,
    EvidenceRole,
    SetupIdentityKind,
    TenantAssertionRole,
)
from app.signal_fusion.observation import TenantExternalAssertion, build_tenant_external_assertion
from app.signal_fusion.policy import (
    DEFAULT_CORRECTION_SELECTION_POLICY,
    DEFAULT_FUSION_POLICY_VERSION,
    FusionPolicy,
    FusionThresholds,
    build_fusion_policy,
    first_slice_role_timeframes,
)
from app.signal_fusion.types import (
    ExecutableSetupRef,
    HalfOpenInterval,
    ManualLevelRevisionRef,
    PresentationEvidenceRef,
    RoleTimeframeBinding,
    RuleWeight,
    SemanticSourceIdentity,
    TriggerIdentity,
    selected_observation_from_public,
)
from tests.support.phase5_market import (
    EVALUATED_AT,
    TRIGGER_OPEN,
    closed_bar,
    eth_instrument,
    identity,
)

ORG_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ACCOUNT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
STRATEGY_VERSION_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
COMPILED_SETUP_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
LEVEL_ID = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
ASSESSMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
CANDIDATE_ID = UUID("22222222-2222-2222-2222-222222222222")
CORRELATION_A = UUID("33333333-3333-3333-3333-333333333333")
CORRELATION_B = UUID("44444444-4444-4444-4444-444444444444")
SCAN_ID = UUID("55555555-5555-5555-5555-555555555555")
ACTION_ID = UUID("66666666-6666-6666-6666-666666666666")
ASSERTION_ID = UUID("77777777-7777-7777-7777-777777777777")
ELIGIBILITY_ID = UUID("88888888-8888-8888-8888-888888888888")
RISK_SNAPSHOT_ID = UUID("99999999-9999-9999-9999-999999999999")
VENUE_STATE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
SETUP_CONTENT_HASH = "11" * 32
MANUAL_LEVEL_HASH = "22" * 32
INTERVAL_END = TRIGGER_OPEN + timedelta(minutes=15)
VALID_UNTIL = EVALUATED_AT + timedelta(minutes=15)

MANDATORY_ROLES: tuple[EvidenceRole, ...] = (
    EvidenceRole.TRIGGER_OHLCV,
    EvidenceRole.CONTEXT_OHLCV,
    EvidenceRole.CVD_WINDOW,
)


def executable_setup(*, content_hash: str = SETUP_CONTENT_HASH) -> ExecutableSetupRef:
    return ExecutableSetupRef(
        setup_definition_id=COMPILED_SETUP_ID,
        kind=SetupIdentityKind.COMPILED_SETUP_DEFINITION,
        content_hash=content_hash,
    )


def public_observation(
    *,
    index: int = 0,
    timeframe: Timeframe = Timeframe.M15,
    market_identity: EvidenceMarketIdentity | None = None,
    revision: int = 1,
) -> PublicMarketObservation:
    frame = market_identity or identity(timeframe=timeframe)
    open_time = TRIGGER_OPEN - (interval_timedelta(timeframe) * index)
    bar = closed_bar(
        index=index,
        timeframe=timeframe,
        open_time=open_time,
        instrument=frame.instrument,
        revision=revision,
    )
    assert bar.finality is Finality.FINAL
    return observation_from_ohlcv(
        bar,
        identity=frame,
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )


def eth_evidence_identity(timeframe: Timeframe = Timeframe.M15) -> EvidenceMarketIdentity:
    return identity(timeframe=timeframe).model_copy(update={"instrument": eth_instrument()})


def blofin_evidence_identity(timeframe: Timeframe = Timeframe.M15) -> EvidenceMarketIdentity:
    base = identity(timeframe=timeframe)
    instrument = base.instrument.model_copy(
        update={
            "venue": VenueId.BLOFIN,
            "instrument_id": canonical_instrument_id(
                venue=VenueId.BLOFIN,
                product_family=base.instrument.product_family,
                market_type=base.instrument.market_type,
                symbol=base.instrument.provider_symbol,
            ),
        }
    )
    return base.model_copy(update={"venue": VenueId.BLOFIN, "instrument": instrument})


def semantic_sources() -> tuple[SemanticSourceIdentity, ...]:
    inst = identity()
    return (
        SemanticSourceIdentity(
            venue=inst.venue,
            market_type=inst.market_type,
            source_family=SourceFamily.BINANCE_USDM_FUTURES_PUBLIC,
        ),
    )


def trigger_for(observation: PublicMarketObservation) -> TriggerIdentity:
    return TriggerIdentity(
        natural_event_id=observation.source_event_id, revision=observation.revision
    )


def manual_level(
    *, revision_number: int = 1, content_hash: str = MANUAL_LEVEL_HASH
) -> ManualLevelRevisionRef:
    return ManualLevelRevisionRef(
        level_id=LEVEL_ID,
        revision_number=revision_number,
        content_hash=content_hash,
    )


def fusion_policy(
    *,
    threshold: Decimal = Decimal("1.0"),
    policy_version: str = DEFAULT_FUSION_POLICY_VERSION,
    required_assertion_roles: tuple[TenantAssertionRole, ...] = (),
    identity_assertion_roles: tuple[TenantAssertionRole, ...] = (),
    role_timeframes: tuple[RoleTimeframeBinding, ...] | None = None,
) -> FusionPolicy:
    return build_fusion_policy(
        policy_version=policy_version,
        organization_id=ORG_ID,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=executable_setup(),
        required_roles=MANDATORY_ROLES,
        thresholds=FusionThresholds(
            confirmation_score=threshold,
            weights=(RuleWeight(rule_id="mandatory_evidence", weight=threshold),),
        ),
        freshness_policy_version=FIRST_SLICE_FRESHNESS_POLICY_VERSION,
        finality_policy_version=FINALITY_POLICY_VERSION,
        role_timeframes=(
            first_slice_role_timeframes() if role_timeframes is None else role_timeframes
        ),
        required_assertion_roles=required_assertion_roles,
        identity_assertion_roles=identity_assertion_roles,
    )


def window_kwargs() -> dict[str, object]:
    trigger_obs = public_observation(index=0)
    context_obs = public_observation(index=1, timeframe=Timeframe.H4)
    cvd_obs = public_observation(index=2)
    return {
        "organization_id": ORG_ID,
        "strategy_version_id": STRATEGY_VERSION_ID,
        "compiled_setup_definition_id": COMPILED_SETUP_ID,
        "compiled_setup_content_hash": SETUP_CONTENT_HASH,
        "fusion_policy_version": DEFAULT_FUSION_POLICY_VERSION,
        "finality_policy_version": FINALITY_POLICY_VERSION,
        "freshness_policy_version": FIRST_SLICE_FRESHNESS_POLICY_VERSION,
        "direction": TradeDirection.SHORT,
        "evidence_identity": first_slice_identity(timeframe=Timeframe.M15, replay=True),
        "interval": HalfOpenInterval(start=TRIGGER_OPEN, end=INTERVAL_END),
        "trigger": trigger_for(trigger_obs),
        "mandatory_evidence_roles": MANDATORY_ROLES,
        "selected_public_observations": (
            selected_observation_from_public(trigger_obs, role=EvidenceRole.TRIGGER_OHLCV),
            selected_observation_from_public(context_obs, role=EvidenceRole.CONTEXT_OHLCV),
            selected_observation_from_public(cvd_obs, role=EvidenceRole.CVD_WINDOW),
        ),
        "source_set": semantic_sources(),
        "manual_level_revision": manual_level(),
        "correction_selection_policy": DEFAULT_CORRECTION_SELECTION_POLICY,
    }


def tenant_assertion(
    *,
    assertion_id: UUID = ASSERTION_ID,
    source: AssertionSource = AssertionSource.TRADINGVIEW,
    source_event_id: str = "tv-alert-1",
) -> TenantExternalAssertion:
    inst = identity().instrument
    return build_tenant_external_assertion(
        assertion_id=assertion_id,
        organization_id=ORG_ID,
        user_id=USER_ID,
        source=source,
        source_event_id=source_event_id,
        venue=inst.venue,
        market_type=inst.market_type,
        instrument_id=inst.instrument_id,
        received_at=EVALUATED_AT,
        recorded_at=EVALUATED_AT + timedelta(seconds=1),
    )


def presentation_evidence(label: str = "chart-overlay") -> PresentationEvidenceRef:
    return PresentationEvidenceRef(label=label, content_hash="33" * 32, note="UI only")


def assessment_command(
    *,
    adapter_kind: EvidenceAdapterKind,
    correlation_id: UUID = CORRELATION_A,
    presentation_label: str = "chart-overlay",
    public_observations: tuple[PublicMarketObservation, ...] | None = None,
    selected_roles: tuple[EvidenceRole, ...] | None = None,
    tenant_assertions: tuple[TenantExternalAssertion, ...] = (),
    assertion_roles: tuple[TenantAssertionRole, ...] = (),
    required_assertion_roles: tuple[TenantAssertionRole, ...] = (),
    identity_assertion_roles: tuple[TenantAssertionRole, ...] = (),
    role_timeframes: tuple[RoleTimeframeBinding, ...] | None = None,
) -> AssessmentCommand:
    kwargs = window_kwargs()
    observations = public_observations or (
        public_observation(index=0),
        public_observation(index=1, timeframe=Timeframe.H4),
        public_observation(index=2),
    )
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "strategy_version_id": STRATEGY_VERSION_ID,
        "executable_setup": executable_setup(),
        "fusion_policy_version": DEFAULT_FUSION_POLICY_VERSION,
        "finality_policy_version": FINALITY_POLICY_VERSION,
        "freshness_policy_version": FIRST_SLICE_FRESHNESS_POLICY_VERSION,
        "direction": TradeDirection.SHORT,
        "evidence_identity": first_slice_identity(timeframe=Timeframe.M15, replay=True),
        "interval": kwargs["interval"],
        "trigger": kwargs["trigger"],
        "mandatory_evidence_roles": MANDATORY_ROLES,
        "public_observations": observations,
        "selected_roles": selected_roles
        or (
            EvidenceRole.TRIGGER_OHLCV,
            EvidenceRole.CONTEXT_OHLCV,
            EvidenceRole.CVD_WINDOW,
        ),
        "tenant_assertions": tenant_assertions,
        "assertion_roles": assertion_roles,
        "required_assertion_roles": required_assertion_roles,
        "identity_assertion_roles": identity_assertion_roles,
        "source_set": semantic_sources(),
        "manual_level_revision": manual_level(),
        "adapter_kind": adapter_kind,
        "scan_id": SCAN_ID,
        "action_id": ACTION_ID,
        "correlation_id": correlation_id,
        "presentation_evidence": (presentation_evidence(presentation_label),),
    }
    if role_timeframes is not None:
        payload["role_timeframes"] = role_timeframes
    return AssessmentCommand(**payload)  # type: ignore[arg-type]


def interval(*, start: datetime = TRIGGER_OPEN, end: datetime = INTERVAL_END) -> HalfOpenInterval:
    return HalfOpenInterval(start=start, end=end)
