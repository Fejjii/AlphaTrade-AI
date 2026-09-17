"""Deterministic ActionEligibility application service.

SetupAssessment remains market truth. This service only answers whether a
confirmed canonical Candidate may proceed toward paper TradePlan creation.
It does not create plans, reserve risk, consume approvals, call venues, or
mutate setup history.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from threading import RLock
from typing import Literal
from uuid import UUID, uuid5

from pydantic import AwareDatetime, Field, model_validator

from app.core.config import ExchangeMode, ExecutionMode
from app.market_contracts.enums import VenueId
from app.market_contracts.models import (
    CanonicalDecimal,
    CanonicalModel,
    NonNegativeCanonicalDecimal,
    PositiveCanonicalDecimal,
)
from app.schemas.common import TradeDirection
from app.schemas.risk import RiskCheckRequest
from app.services.canonical_serialization import canonical_sha256
from app.services.risk.engine import RiskEngine
from app.services.risk.rules import (
    RiskEvaluationContext,
    check_daily_loss_lock,
    check_kill_switch,
    check_weekly_loss,
)
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.eligibility import ActionEligibility, build_action_eligibility
from app.signal_fusion.enums import (
    ActionEligibilityState,
    CandidateState,
    EligibilityReasonCode,
    SetupAssessmentState,
)
from app.signal_fusion.errors import ActionEligibilityLineageError
from app.signal_fusion.evidence_window import (
    CanonicalEvidenceWindowV1,
    hash_canonical_evidence_window,
)
from app.signal_fusion.memory import FrozenClock, UtcClock
from app.signal_fusion.ports import Clock
from app.signal_fusion.types import Sha256Hex, hashed_model

ELIGIBILITY_IDENTITY_NAMESPACE = UUID("b22ea7de-0006-4000-8000-ac710e11e101")
PAPER_ELIGIBILITY_CONFIG_VERSION = "paper-execution/v1"
FIRST_SLICE_CROSS_VENUE_BASIS_THRESHOLD_BPS = Decimal("20")
_BPS = Decimal("10000")
_ELIGIBILITY_FALLBACK_TTL = timedelta(seconds=1)
_CAPACITY_PROBE_SIZE = Decimal("0.00000001")
_NON_CONFIRMED_SETUP = frozenset(
    {
        SetupAssessmentState.NO_SETUP,
        SetupAssessmentState.WATCH,
        SetupAssessmentState.PARTIAL_MATCH,
        SetupAssessmentState.INVALIDATED,
        SetupAssessmentState.EXPIRED,
    }
)


class AccountIdentity(CanonicalModel):
    """Acting organization / user / account for one eligibility evaluation."""

    organization_id: UUID
    user_id: UUID
    account_id: UUID
    account_active: bool = True


class PortfolioState(CanonicalModel):
    """Account portfolio facts used for capacity checks. Not a trade plan."""

    organization_id: UUID
    account_id: UUID
    account_equity: PositiveCanonicalDecimal
    open_exposure_notional: NonNegativeCanonicalDecimal = Decimal("0")


class RiskStateSnapshot(CanonicalModel):
    """Authoritative risk snapshot identity plus the facts RiskEngine consumes."""

    risk_snapshot_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    daily_locked: bool = False
    daily_loss_limit: CanonicalDecimal | None = None
    realized_pnl_today: CanonicalDecimal = Decimal("0")
    weekly_loss_pct: CanonicalDecimal | None = None
    cooldown_active: bool = False
    portfolio_conflict: bool = False
    trades_today: int = Field(default=0, ge=0)


class SafetyStateSnapshot(CanonicalModel):
    """Kill-switch and safety-epoch facts. Kill switch always dominates."""

    organization_id: UUID
    account_id: UUID
    safety_epoch: int = Field(ge=1)
    kill_switch_active: bool = False
    global_kill_switch_active: bool = False
    kill_switch_unavailable: bool = False


class MarketActionEvidence(CanonicalModel):
    """Action-time market evidence. Never written onto SetupAssessment."""

    venue_state_id: UUID
    evidence_venue: VenueId
    execution_venue: VenueId
    evidence_price: PositiveCanonicalDecimal
    execution_price: PositiveCanonicalDecimal | None = None
    basis_bps: CanonicalDecimal | None = None
    required_action_evidence_fresh: bool = True
    action_evidence_valid_until: AwareDatetime
    basis_fresh: bool = True
    symbol: str = Field(default="BTCUSDT", min_length=2, max_length=30)


class PaperExecutionConfiguration(CanonicalModel):
    """Paper execution posture for this evaluation. Live trading cannot pass."""

    execution_mode: ExecutionMode = ExecutionMode.PAPER
    enable_real_trading: bool = False
    exchange_mode: ExchangeMode = ExchangeMode.PAPER_INTERNAL
    configuration_version: str = Field(
        default=PAPER_ELIGIBILITY_CONFIG_VERSION, min_length=3, max_length=120
    )

    @property
    def is_paper_only(self) -> bool:
        return (
            self.execution_mode is ExecutionMode.PAPER
            and not self.enable_real_trading
            and self.exchange_mode is not ExchangeMode.TRADE_LIVE
        )


class ActionEligibilityCommand(CanonicalModel):
    """Inputs for one deterministic eligibility evaluation."""

    candidate: Candidate
    assessment: SetupAssessment
    evidence_window: CanonicalEvidenceWindowV1
    account: AccountIdentity
    portfolio: PortfolioState
    risk: RiskStateSnapshot
    safety: SafetyStateSnapshot
    market_action: MarketActionEvidence
    configuration: PaperExecutionConfiguration
    correlation_id: UUID


class ActionEligibilityEvaluation(CanonicalModel):
    """Immutable evaluation envelope around the frozen ActionEligibility contract."""

    eligibility: ActionEligibility
    evaluation_revision: int = Field(ge=1)
    evidence_window_hash: Sha256Hex
    candidate_content_hash: Sha256Hex
    setup_assessment_content_hash: Sha256Hex
    safety_epoch: int = Field(ge=1)
    configuration_version: str = Field(min_length=3, max_length=120)
    uniqueness_hash: Sha256Hex
    paper_actionable: bool
    live_executable: Literal[False] = False
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _paper_only_action(self) -> ActionEligibilityEvaluation:
        if self.live_executable:
            raise ValueError("ActionEligibility cannot be live-executable.")
        if self.paper_actionable and self.eligibility.state is not ActionEligibilityState.ELIGIBLE:
            raise ValueError("paper_actionable requires ELIGIBLE.")
        return self


def uniqueness_preimage(command: ActionEligibilityCommand) -> dict[str, object]:
    """Semantic identity for converge/reevaluate. Excludes clocks and correlation."""
    return {
        "account": command.account.model_dump(mode="python"),
        "assessment_content_hash": command.assessment.content_hash,
        "assessment_id": command.assessment.assessment_id,
        "candidate_content_hash": command.candidate.content_hash,
        "candidate_id": command.candidate.candidate_id,
        "candidate_revision": command.candidate.transition_version,
        "configuration": command.configuration.model_dump(mode="python"),
        "evidence_window_hash": command.evidence_window.content_hash,
        "market_action": command.market_action.model_dump(mode="python"),
        "portfolio": command.portfolio.model_dump(mode="python"),
        "risk": command.risk.model_dump(mode="python"),
        "safety": command.safety.model_dump(mode="python"),
    }


def uniqueness_hash(command: ActionEligibilityCommand) -> str:
    return canonical_sha256(uniqueness_preimage(command))


def deterministic_eligibility_id(digest: str) -> UUID:
    return uuid5(ELIGIBILITY_IDENTITY_NAMESPACE, digest)


def build_action_eligibility_evaluation(**kwargs: object) -> ActionEligibilityEvaluation:
    draft = ActionEligibilityEvaluation.model_validate({**kwargs, "content_hash": "0" * 64})
    return hashed_model(draft)


class InMemoryActionEligibilityStore:
    """Append-only eligibility history. Identical uniqueness converges."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_uniqueness: dict[str, ActionEligibilityEvaluation] = {}
        self._history: dict[tuple[UUID, UUID, UUID], list[ActionEligibilityEvaluation]] = {}

    def get(self, digest: str) -> ActionEligibilityEvaluation | None:
        with self._lock:
            return self._by_uniqueness.get(digest)

    def history(
        self, *, organization_id: UUID, account_id: UUID, candidate_id: UUID
    ) -> tuple[ActionEligibilityEvaluation, ...]:
        with self._lock:
            return tuple(self._history.get((organization_id, account_id, candidate_id), ()))

    def get_or_insert(
        self,
        digest: str,
        factory: Callable[[int], ActionEligibilityEvaluation],
        *,
        organization_id: UUID,
        account_id: UUID,
        candidate_id: UUID,
    ) -> ActionEligibilityEvaluation:
        lineage = (organization_id, account_id, candidate_id)
        with self._lock:
            existing = self._by_uniqueness.get(digest)
            if existing is not None:
                return existing
            history = self._history.setdefault(lineage, [])
            produced = factory(len(history) + 1)
            if produced.uniqueness_hash != digest:
                raise ActionEligibilityLineageError(
                    "Eligibility uniqueness hash drifted during insert."
                )
            self._by_uniqueness[digest] = produced
            history.append(produced)
            return produced


class ActionEligibilityService:
    """Single action-eligibility authority. Setup truth is an input, never an output."""

    def __init__(
        self,
        *,
        store: InMemoryActionEligibilityStore,
        clock: Clock,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._risk = risk_engine or RiskEngine()

    def evaluate(self, command: ActionEligibilityCommand) -> ActionEligibilityEvaluation:
        self._validate_lineage(command)
        digest = uniqueness_hash(command)
        return self._store.get_or_insert(
            digest,
            lambda revision: self._build_evaluation(command, digest, revision),
            organization_id=command.account.organization_id,
            account_id=command.account.account_id,
            candidate_id=command.candidate.candidate_id,
        )

    def history(
        self, *, organization_id: UUID, account_id: UUID, candidate_id: UUID
    ) -> tuple[ActionEligibilityEvaluation, ...]:
        return self._store.history(
            organization_id=organization_id,
            account_id=account_id,
            candidate_id=candidate_id,
        )

    def _build_evaluation(
        self,
        command: ActionEligibilityCommand,
        digest: str,
        revision: int,
    ) -> ActionEligibilityEvaluation:
        now = self._clock.now()
        reason = self._dominant_reason(command, now)
        if reason is None:
            state = ActionEligibilityState.ELIGIBLE
            reasons: tuple[EligibilityReasonCode, ...] = (EligibilityReasonCode.ELIGIBLE,)
        elif reason is EligibilityReasonCode.EXPIRED:
            state = ActionEligibilityState.EXPIRED
            reasons = (EligibilityReasonCode.EXPIRED,)
        else:
            state = ActionEligibilityState.BLOCKED
            reasons = (reason,)
        paper_actionable = (
            state is ActionEligibilityState.ELIGIBLE and command.configuration.is_paper_only
        )
        eligibility = build_action_eligibility(
            eligibility_id=deterministic_eligibility_id(digest),
            organization_id=command.account.organization_id,
            user_id=command.account.user_id,
            account_id=command.account.account_id,
            candidate_id=command.candidate.candidate_id,
            candidate_revision=command.candidate.transition_version,
            assessment_id=command.assessment.assessment_id,
            risk_snapshot_id=command.risk.risk_snapshot_id,
            venue_state_id=command.market_action.venue_state_id,
            state=state,
            reason_codes=reasons,
            checked_at=now,
            valid_until=self._valid_until(command, now),
            correlation_id=command.correlation_id,
        )
        return build_action_eligibility_evaluation(
            eligibility=eligibility,
            evaluation_revision=revision,
            evidence_window_hash=command.evidence_window.content_hash,
            candidate_content_hash=command.candidate.content_hash,
            setup_assessment_content_hash=command.assessment.content_hash,
            safety_epoch=command.safety.safety_epoch,
            configuration_version=command.configuration.configuration_version,
            uniqueness_hash=digest,
            paper_actionable=paper_actionable,
            live_executable=False,
        )

    def _dominant_reason(
        self, command: ActionEligibilityCommand, now: datetime
    ) -> EligibilityReasonCode | None:
        if self._kill_switch_blocks(command):
            return EligibilityReasonCode.BLOCKED_KILL_SWITCH
        if not command.configuration.is_paper_only:
            return EligibilityReasonCode.BLOCKED_CONFIGURATION
        if command.assessment.state in _NON_CONFIRMED_SETUP:
            return EligibilityReasonCode.BLOCKED_SETUP_NOT_CONFIRMED
        if command.candidate.state is not CandidateState.ACTIVE:
            return EligibilityReasonCode.BLOCKED_CANDIDATE_TTL
        if command.candidate.valid_until <= now or command.assessment.valid_until <= now:
            return EligibilityReasonCode.EXPIRED
        if self._tenant_mismatch(command):
            return EligibilityReasonCode.BLOCKED_ACCOUNT_STATE
        if self._account_mismatch(command):
            return EligibilityReasonCode.BLOCKED_ACCOUNT_STATE
        if not command.account.account_active:
            return EligibilityReasonCode.BLOCKED_ACCOUNT_STATE
        if self._action_evidence_stale(command, now):
            return EligibilityReasonCode.BLOCKED_DATA_QUALITY
        basis_reason = self._basis_reason(command)
        if basis_reason is not None:
            return basis_reason
        return self._risk_reason(command)

    def _kill_switch_blocks(self, command: ActionEligibilityCommand) -> bool:
        safety = command.safety
        if safety.kill_switch_unavailable:
            return True
        if safety.kill_switch_active or safety.global_kill_switch_active:
            return True
        request, context = self._risk_inputs(command)
        return check_kill_switch(request, self._risk.limits, context) is not None

    def _risk_reason(self, command: ActionEligibilityCommand) -> EligibilityReasonCode | None:
        request, context = self._risk_inputs(command)
        if check_daily_loss_lock(request, self._risk.limits, context) is not None:
            return EligibilityReasonCode.BLOCKED_DAILY_LOSS
        if check_weekly_loss(request, self._risk.limits, context) is not None:
            return EligibilityReasonCode.BLOCKED_DAILY_LOSS
        if command.risk.cooldown_active:
            return EligibilityReasonCode.BLOCKED_COOLDOWN
        if command.risk.portfolio_conflict:
            return EligibilityReasonCode.BLOCKED_PORTFOLIO_CONFLICT
        max_notional = command.portfolio.account_equity * (
            self._risk.limits.max_position_pct_of_equity / Decimal("100")
        )
        if command.portfolio.open_exposure_notional >= max_notional:
            return EligibilityReasonCode.BLOCKED_EXPOSURE
        return None

    def _risk_inputs(
        self, command: ActionEligibilityCommand
    ) -> tuple[RiskCheckRequest, RiskEvaluationContext]:
        price = command.market_action.evidence_price
        if command.candidate.direction is TradeDirection.SHORT:
            stop = price * Decimal("101") / Decimal("100")
        else:
            stop = price * Decimal("99") / Decimal("100")
        request = RiskCheckRequest(
            symbol=command.market_action.symbol,
            direction=command.candidate.direction,
            entry_price=price,
            stop_loss=stop,
            position_size=_CAPACITY_PROBE_SIZE,
            leverage=Decimal("1"),
            account_equity=command.portfolio.account_equity,
        )
        safety = command.safety
        context = RiskEvaluationContext(
            daily_locked=command.risk.daily_locked,
            realized_pnl_today=command.risk.realized_pnl_today,
            daily_loss_limit=command.risk.daily_loss_limit,
            weekly_loss_pct=command.risk.weekly_loss_pct,
            trades_today=command.risk.trades_today,
            kill_switch_active=(safety.kill_switch_active or safety.global_kill_switch_active),
            is_weekend=False,
            open_exposure_notional=command.portfolio.open_exposure_notional,
        )
        return request, context

    @staticmethod
    def _tenant_mismatch(command: ActionEligibilityCommand) -> bool:
        orgs = {
            command.account.organization_id,
            command.candidate.organization_id,
            command.assessment.organization_id,
            command.evidence_window.organization_id,
            command.portfolio.organization_id,
            command.risk.organization_id,
            command.safety.organization_id,
        }
        return len(orgs) != 1

    @staticmethod
    def _account_mismatch(command: ActionEligibilityCommand) -> bool:
        if command.risk.user_id != command.account.user_id:
            return True
        accounts = {
            command.account.account_id,
            command.portfolio.account_id,
            command.risk.account_id,
            command.safety.account_id,
        }
        return len(accounts) != 1

    @staticmethod
    def _action_evidence_stale(command: ActionEligibilityCommand, now: datetime) -> bool:
        market = command.market_action
        if not market.required_action_evidence_fresh:
            return True
        if market.action_evidence_valid_until <= now:
            return True
        return not market.basis_fresh

    @staticmethod
    def _basis_reason(command: ActionEligibilityCommand) -> EligibilityReasonCode | None:
        market = command.market_action
        cross_venue = market.evidence_venue is not market.execution_venue
        if market.basis_bps is not None:
            bps = market.basis_bps
        elif market.execution_price is not None:
            bps = abs(market.execution_price - market.evidence_price) / market.evidence_price * _BPS
        elif cross_venue:
            return EligibilityReasonCode.BLOCKED_VENUE_STATE
        else:
            bps = Decimal("0")
        if bps > FIRST_SLICE_CROSS_VENUE_BASIS_THRESHOLD_BPS:
            return EligibilityReasonCode.BLOCKED_BASIS
        return None

    @staticmethod
    def _valid_until(command: ActionEligibilityCommand, now: datetime) -> datetime:
        bounds = (
            command.candidate.valid_until,
            command.assessment.valid_until,
            command.market_action.action_evidence_valid_until,
        )
        future = [bound for bound in bounds if bound > now]
        if future:
            return min(future)
        return now + _ELIGIBILITY_FALLBACK_TTL

    @staticmethod
    def _validate_lineage(command: ActionEligibilityCommand) -> None:
        window = command.evidence_window
        assessment = command.assessment
        candidate = command.candidate
        if hash_canonical_evidence_window(window) != window.content_hash:
            raise ActionEligibilityLineageError(
                "CanonicalEvidenceWindowV1 content hash is not the §26 preimage digest."
            )
        if candidate.assessment_id != assessment.assessment_id:
            raise ActionEligibilityLineageError(
                "Candidate assessment_id must match the supplied SetupAssessment."
            )
        if candidate.evidence_window_hash != window.content_hash:
            raise ActionEligibilityLineageError(
                "Candidate evidence_window_hash must match CanonicalEvidenceWindowV1."
            )
        if assessment.evidence_window_hash != window.content_hash:
            raise ActionEligibilityLineageError(
                "SetupAssessment evidence_window_hash must match CanonicalEvidenceWindowV1."
            )


def in_memory_action_eligibility(
    *,
    now: datetime | None = None,
    store: InMemoryActionEligibilityStore | None = None,
    risk_engine: RiskEngine | None = None,
) -> ActionEligibilityService:
    """Factory for tests and local paper use. No network, no PostgreSQL."""
    clock: Clock = FrozenClock(now) if now is not None else UtcClock()
    return ActionEligibilityService(
        store=store or InMemoryActionEligibilityStore(),
        clock=clock,
        risk_engine=risk_engine,
    )


__all__ = [
    "ELIGIBILITY_IDENTITY_NAMESPACE",
    "FIRST_SLICE_CROSS_VENUE_BASIS_THRESHOLD_BPS",
    "PAPER_ELIGIBILITY_CONFIG_VERSION",
    "AccountIdentity",
    "ActionEligibilityCommand",
    "ActionEligibilityEvaluation",
    "ActionEligibilityService",
    "InMemoryActionEligibilityStore",
    "MarketActionEvidence",
    "PaperExecutionConfiguration",
    "PortfolioState",
    "RiskStateSnapshot",
    "SafetyStateSnapshot",
    "build_action_eligibility_evaluation",
    "deterministic_eligibility_id",
    "in_memory_action_eligibility",
    "uniqueness_hash",
    "uniqueness_preimage",
]
