"""Builders for Phase 6 ActionEligibility tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.config import ExchangeMode, ExecutionMode
from app.market_contracts.enums import VenueId
from app.market_contracts.first_slice import first_slice_identity
from app.schemas.common import Timeframe
from app.signal_fusion.action_eligibility import (
    PAPER_ELIGIBILITY_CONFIG_VERSION,
    AccountIdentity,
    ActionEligibilityCommand,
    MarketActionEvidence,
    PaperExecutionConfiguration,
    PortfolioState,
    RiskStateSnapshot,
    SafetyStateSnapshot,
)
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate, build_confirmed_candidate
from app.signal_fusion.enums import SetupAssessmentState
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.signal_fusion.lifecycle import (
    deterministic_candidate_id,
    in_memory_candidate_lifecycle,
    uniqueness_from_confirmed,
)
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    CORRELATION_A,
    ORG_ID,
    RISK_SNAPSHOT_ID,
    USER_ID,
    VALID_UNTIL,
    VENUE_STATE_ID,
    make_assessment,
    make_creation_command,
    make_evidence_window,
)

EVIDENCE_PRICE = Decimal("100000")
DEFAULT_EQUITY = Decimal("10000")
ORG_B = UUID("aaaaaaaa-bbbb-cccc-dddd-aaaaaaaaaaaa")
ACCOUNT_B = UUID("cccccccc-cccc-cccc-cccc-000000000002")
USER_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-000000000002")
RISK_SNAPSHOT_B = UUID("99999999-9999-9999-9999-000000000002")
VENUE_STATE_B = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1")


def account_identity(
    *,
    organization_id: UUID = ORG_ID,
    user_id: UUID = USER_ID,
    account_id: UUID = ACCOUNT_ID,
    account_active: bool = True,
) -> AccountIdentity:
    return AccountIdentity(
        organization_id=organization_id,
        user_id=user_id,
        account_id=account_id,
        account_active=account_active,
    )


def portfolio_state(
    *,
    organization_id: UUID = ORG_ID,
    account_id: UUID = ACCOUNT_ID,
    account_equity: Decimal = DEFAULT_EQUITY,
    open_exposure_notional: Decimal = Decimal("0"),
) -> PortfolioState:
    return PortfolioState(
        organization_id=organization_id,
        account_id=account_id,
        account_equity=account_equity,
        open_exposure_notional=open_exposure_notional,
    )


def risk_snapshot(
    *,
    risk_snapshot_id: UUID = RISK_SNAPSHOT_ID,
    organization_id: UUID = ORG_ID,
    user_id: UUID = USER_ID,
    account_id: UUID = ACCOUNT_ID,
    daily_locked: bool = False,
    daily_loss_limit: Decimal | None = Decimal("200"),
    realized_pnl_today: Decimal = Decimal("0"),
    weekly_loss_pct: Decimal | None = None,
    cooldown_active: bool = False,
    portfolio_conflict: bool = False,
) -> RiskStateSnapshot:
    return RiskStateSnapshot(
        risk_snapshot_id=risk_snapshot_id,
        organization_id=organization_id,
        user_id=user_id,
        account_id=account_id,
        daily_locked=daily_locked,
        daily_loss_limit=daily_loss_limit,
        realized_pnl_today=realized_pnl_today,
        weekly_loss_pct=weekly_loss_pct,
        cooldown_active=cooldown_active,
        portfolio_conflict=portfolio_conflict,
    )


def safety_snapshot(
    *,
    organization_id: UUID = ORG_ID,
    account_id: UUID = ACCOUNT_ID,
    safety_epoch: int = 1,
    kill_switch_active: bool = False,
    global_kill_switch_active: bool = False,
    kill_switch_unavailable: bool = False,
) -> SafetyStateSnapshot:
    return SafetyStateSnapshot(
        organization_id=organization_id,
        account_id=account_id,
        safety_epoch=safety_epoch,
        kill_switch_active=kill_switch_active,
        global_kill_switch_active=global_kill_switch_active,
        kill_switch_unavailable=kill_switch_unavailable,
    )


def market_action(
    *,
    venue_state_id: UUID = VENUE_STATE_ID,
    evidence_venue: VenueId = VenueId.BINANCE,
    execution_venue: VenueId = VenueId.BINANCE,
    evidence_price: Decimal = EVIDENCE_PRICE,
    execution_price: Decimal | None = EVIDENCE_PRICE,
    basis_bps: Decimal | None = None,
    required_action_evidence_fresh: bool = True,
    basis_fresh: bool = True,
    action_evidence_valid_until: datetime = VALID_UNTIL,
) -> MarketActionEvidence:
    return MarketActionEvidence(
        venue_state_id=venue_state_id,
        evidence_venue=evidence_venue,
        execution_venue=execution_venue,
        evidence_price=evidence_price,
        execution_price=execution_price,
        basis_bps=basis_bps,
        required_action_evidence_fresh=required_action_evidence_fresh,
        action_evidence_valid_until=action_evidence_valid_until,
        basis_fresh=basis_fresh,
    )


def paper_configuration(
    *,
    execution_mode: ExecutionMode = ExecutionMode.PAPER,
    enable_real_trading: bool = False,
    exchange_mode: ExchangeMode = ExchangeMode.PAPER_INTERNAL,
    configuration_version: str = PAPER_ELIGIBILITY_CONFIG_VERSION,
) -> PaperExecutionConfiguration:
    return PaperExecutionConfiguration(
        execution_mode=execution_mode,
        enable_real_trading=enable_real_trading,
        exchange_mode=exchange_mode,
        configuration_version=configuration_version,
    )


def confirmed_bundle() -> tuple[CanonicalEvidenceWindowV1, SetupAssessment, Candidate]:
    window = make_evidence_window()
    assessment = make_assessment(window)
    lifecycle = in_memory_candidate_lifecycle(now=EVALUATED_AT)
    candidate = lifecycle.create_from_confirmed_setup(
        make_creation_command(window=window, assessment=assessment)
    )
    return window, assessment, candidate


def synthetic_candidate(
    assessment: SetupAssessment,
    window: CanonicalEvidenceWindowV1,
) -> Candidate:
    uniqueness = uniqueness_from_confirmed(assessment, window, assessment.executable_setup)
    identity = first_slice_identity(timeframe=Timeframe.M15, replay=True)
    return build_confirmed_candidate(
        candidate_id=deterministic_candidate_id(uniqueness),
        organization_id=assessment.organization_id,
        strategy_version_id=assessment.strategy_version_id,
        executable_setup=assessment.executable_setup,
        fusion_policy_version=assessment.fusion_policy_version,
        direction=window.direction,
        assessment_id=assessment.assessment_id,
        evidence_window_hash=window.content_hash,
        evidence_identity=identity,
        evidence_venue=window.evidence_venue,
        evidence_market=window.evidence_market,
        evidence_instrument=window.evidence_instrument,
        timeframe=window.timeframe,
        created_at=assessment.assessed_at,
        valid_until=assessment.valid_until,
        idempotency_key="eligibility-synthetic-1",
        correlation_id=CORRELATION_A,
    )


def eligibility_command(
    *,
    window: CanonicalEvidenceWindowV1 | None = None,
    assessment: SetupAssessment | None = None,
    candidate: Candidate | None = None,
    account: AccountIdentity | None = None,
    portfolio: PortfolioState | None = None,
    risk: RiskStateSnapshot | None = None,
    safety: SafetyStateSnapshot | None = None,
    market: MarketActionEvidence | None = None,
    configuration: PaperExecutionConfiguration | None = None,
    correlation_id: UUID = CORRELATION_A,
) -> ActionEligibilityCommand:
    resolved_window = window
    resolved_assessment = assessment
    resolved_candidate = candidate
    if resolved_window is None or resolved_assessment is None or resolved_candidate is None:
        bundled_window, bundled_assessment, bundled_candidate = confirmed_bundle()
        resolved_window = resolved_window or bundled_window
        resolved_assessment = resolved_assessment or bundled_assessment
        resolved_candidate = resolved_candidate or bundled_candidate
    return ActionEligibilityCommand(
        candidate=resolved_candidate,
        assessment=resolved_assessment,
        evidence_window=resolved_window,
        account=account or account_identity(),
        portfolio=portfolio or portfolio_state(),
        risk=risk or risk_snapshot(),
        safety=safety or safety_snapshot(),
        market_action=market or market_action(),
        configuration=configuration or paper_configuration(),
        correlation_id=correlation_id,
    )


def non_confirmed_command(state: SetupAssessmentState) -> ActionEligibilityCommand:
    window = make_evidence_window()
    previous = None if state is SetupAssessmentState.NO_SETUP else SetupAssessmentState.WATCH
    assessment = make_assessment(window, state=state, previous_state=previous)
    candidate = synthetic_candidate(assessment, window)
    return eligibility_command(window=window, assessment=assessment, candidate=candidate)
