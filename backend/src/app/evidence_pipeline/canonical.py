"""First-slice FusionPolicy + AssessmentCommand projection for assembled evidence."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from app.analysis.wilder_atr_v1 import FINALITY_POLICY_VERSION
from app.market_contracts.coverage import TradeWindowCoverageProof
from app.market_contracts.cvd import CvdWindow
from app.market_contracts.enums import FreshnessState, SourceFamily
from app.market_contracts.first_slice import FIRST_SLICE_PATTERN_NAME
from app.market_contracts.flow import SignedQuoteFlow
from app.market_contracts.freshness import FIRST_SLICE_FRESHNESS_POLICY_VERSION
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.observation import (
    observation_from_coverage,
    observation_from_cvd,
    observation_from_ohlcv,
    observation_from_signed_flow,
)
from app.market_contracts.ohlcv import OhlcvBar
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.adapters import AssessmentCommand
from app.signal_fusion.enums import EvidenceAdapterKind, EvidenceRole, SetupIdentityKind
from app.signal_fusion.observation import TenantExternalAssertion
from app.signal_fusion.policy import (
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
    RuleWeight,
    SemanticSourceIdentity,
    TriggerIdentity,
)

FIRST_SLICE_READ_STRATEGY_VERSION_ID = UUID("0a064000-0000-4000-8000-000000000001")
FIRST_SLICE_READ_SETUP_DEFINITION_ID = UUID("0a064000-0000-4000-8000-000000000002")
FIRST_SLICE_READ_SETUP_CONTENT_HASH = sha256(
    b"first-slice-read-projection/v1:" + FIRST_SLICE_PATTERN_NAME.encode()
).hexdigest()

MANDATORY_ROLES: tuple[EvidenceRole, ...] = (
    EvidenceRole.TRIGGER_OHLCV,
    EvidenceRole.CONTEXT_OHLCV,
    EvidenceRole.CVD_WINDOW,
    EvidenceRole.SIGNED_FLOW,
    EvidenceRole.TRADE_EVENT,
)


def is_first_slice_read_projection(
    *,
    strategy_version_id: UUID | None = None,
    setup_definition_id: UUID | None = None,
) -> bool:
    """True when identity is the GET/read projection placeholder, not a stored version."""

    return strategy_version_id == FIRST_SLICE_READ_STRATEGY_VERSION_ID or (
        setup_definition_id == FIRST_SLICE_READ_SETUP_DEFINITION_ID
    )


def first_slice_read_setup() -> ExecutableSetupRef:
    return ExecutableSetupRef(
        setup_definition_id=FIRST_SLICE_READ_SETUP_DEFINITION_ID,
        kind=SetupIdentityKind.COMPILED_SETUP_DEFINITION,
        content_hash=FIRST_SLICE_READ_SETUP_CONTENT_HASH,
    )


def first_slice_read_policy(
    organization_id: UUID,
    *,
    strategy_version_id: UUID = FIRST_SLICE_READ_STRATEGY_VERSION_ID,
) -> FusionPolicy:
    """Tenant-scoped first-slice policy used for read/projection identity.

    This does not mint a Candidate and is not Watcher activation.
    """
    return build_fusion_policy(
        policy_version=DEFAULT_FUSION_POLICY_VERSION,
        organization_id=organization_id,
        strategy_version_id=strategy_version_id,
        executable_setup=first_slice_read_setup(),
        required_roles=MANDATORY_ROLES,
        thresholds=FusionThresholds(
            confirmation_score=Decimal("1"),
            weights=(RuleWeight(rule_id="mandatory_evidence", weight=Decimal("1")),),
        ),
        freshness_policy_version=FIRST_SLICE_FRESHNESS_POLICY_VERSION,
        finality_policy_version=FINALITY_POLICY_VERSION,
        role_timeframes=first_slice_role_timeframes(),
    )


def semantic_source_from_identity(identity: EvidenceMarketIdentity) -> SemanticSourceIdentity:
    family = identity.source.family
    if family is SourceFamily.REPLAY_FIXTURE:
        public_family = SourceFamily.REPLAY_FIXTURE
    elif family is SourceFamily.OKX_USDT_SWAP_PUBLIC:
        public_family = SourceFamily.OKX_USDT_SWAP_PUBLIC
    else:
        public_family = SourceFamily.BINANCE_USDM_FUTURES_PUBLIC
    return SemanticSourceIdentity(
        venue=identity.venue,
        market_type=identity.market_type,
        source_family=public_family,
    )


def build_first_slice_assessment_command(
    *,
    organization_id: UUID,
    policy: FusionPolicy,
    trigger: OhlcvBar,
    context: OhlcvBar,
    trigger_identity: EvidenceMarketIdentity,
    context_identity: EvidenceMarketIdentity,
    evaluated_at: datetime,
    freshness_state: FreshnessState,
    adapter_kind: EvidenceAdapterKind,
    cvd: CvdWindow,
    signed_flow: SignedQuoteFlow,
    coverage: TradeWindowCoverageProof,
    tenant_assertions: tuple[TenantExternalAssertion, ...] = (),
    manual_level_revision: ManualLevelRevisionRef | None = None,
) -> AssessmentCommand:
    """Project assembled OHLCV + CVD/flow/coverage into AssessmentCommand.

    Closed-bar observation freshness is the final-bar envelope, not live-mark
    age. Adapter kind is not hashed. CVD, signed flow, and coverage use the
    existing public observation contract and payload content hashes.
    """
    closed_state = FreshnessState.FRESH
    trigger_obs = observation_from_ohlcv(
        trigger,
        identity=trigger_identity,
        observed_at=evaluated_at,
        receive_time=evaluated_at,
        freshness_state=closed_state,
    )
    context_obs = observation_from_ohlcv(
        context,
        identity=context_identity,
        observed_at=evaluated_at,
        receive_time=evaluated_at,
        freshness_state=closed_state,
    )
    cvd_obs = observation_from_cvd(
        cvd,
        observed_at=evaluated_at,
        receive_time=evaluated_at,
        freshness_state=closed_state,
    )
    flow_obs = observation_from_signed_flow(
        signed_flow,
        observed_at=evaluated_at,
        receive_time=evaluated_at,
        freshness_state=closed_state,
    )
    coverage_obs = observation_from_coverage(
        coverage,
        observed_at=evaluated_at,
        receive_time=evaluated_at,
        freshness_state=closed_state,
    )
    del freshness_state
    return AssessmentCommand(
        organization_id=organization_id,
        strategy_version_id=policy.strategy_version_id,
        executable_setup=policy.executable_setup,
        fusion_policy_version=policy.policy_version,
        finality_policy_version=policy.finality_policy_version,
        freshness_policy_version=policy.freshness_policy_version,
        direction=TradeDirection.SHORT,
        evidence_identity=trigger_identity,
        interval=HalfOpenInterval(start=trigger.interval_start, end=trigger.interval_end),
        trigger=TriggerIdentity(
            natural_event_id=trigger.source_event_id,
            revision=trigger.revision,
        ),
        mandatory_evidence_roles=MANDATORY_ROLES,
        public_observations=(trigger_obs, context_obs, cvd_obs, flow_obs, coverage_obs),
        selected_roles=(
            EvidenceRole.TRIGGER_OHLCV,
            EvidenceRole.CONTEXT_OHLCV,
            EvidenceRole.CVD_WINDOW,
            EvidenceRole.SIGNED_FLOW,
            EvidenceRole.TRADE_EVENT,
        ),
        tenant_assertions=tenant_assertions,
        source_set=(semantic_source_from_identity(trigger_identity),),
        manual_level_revision=manual_level_revision,
        adapter_kind=adapter_kind,
        role_timeframes=policy.role_timeframes,
        correction_selection_policy=policy.correction_selection_policy,
        required_assertion_roles=policy.required_assertion_roles,
        identity_assertion_roles=policy.identity_assertion_roles,
    )


def timeframe_identity(
    identity: EvidenceMarketIdentity, timeframe: Timeframe
) -> EvidenceMarketIdentity:
    if identity.timeframe is timeframe:
        return identity
    return identity.model_copy(update={"timeframe": timeframe})
