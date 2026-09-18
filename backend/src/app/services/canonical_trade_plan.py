"""Canonical Candidate + ActionEligibility → immutable TradePlanRevision.

This is the sole first-slice plan-creation authority. It does not evaluate
setup truth, does not issue approvals, and does not execute. PostgreSQL binding
is deferred to Agent 1; persistence is the typed in-memory port.
"""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import NoReturn
from uuid import UUID, uuid5

from app.core.operation_policy import PersistenceKind, assert_write_allowed
from app.market_contracts.enums import MarketType as EvidenceMarketType
from app.market_contracts.hashing import CONTENT_HASH_EXCLUDE, semantic_content_hash
from app.market_contracts.models import CanonicalModel
from app.repositories.canonical_trade_plans import (
    CanonicalTradePlanStore,
    InMemoryCanonicalTradePlanStore,
)
from app.schemas.canonical_trade_plan import (
    CanonicalTradePlanCommand,
    CanonicalTradePlanLineage,
    CanonicalTradePlanRevision,
)
from app.schemas.common import TradeDirection
from app.schemas.trade_plan import (
    EntrySide,
    TradePlanRevision,
    TradePlanRevisionSemantic,
)
from app.schemas.trade_plan import (
    MarketType as PlanMarketType,
)
from app.services.canonical_serialization import canonical_sha256
from app.services.canonical_trade_plan_errors import (
    CanonicalTradePlanAuthorityError,
    CanonicalTradePlanImmutableError,
    CanonicalTradePlanLineageError,
    CanonicalTradePlanNotEligibleError,
    CanonicalTradePlanNotFoundError,
    ConflictingTradePlanIdempotencyError,
    LegacyPaperValidationCannotMintPlanError,
)
from app.signal_fusion.action_eligibility import (
    ActionEligibilityEvaluation,
    ActionEligibilityService,
)
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.enums import (
    ActionEligibilityState,
    CandidateReasonCode,
    CandidateState,
)
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.signal_fusion.memory import FrozenClock, UtcClock
from app.signal_fusion.ports import Clock

PLAN_IDENTITY_NAMESPACE = UUID("c33ea7de-0007-4000-8000-71ade01a0001")
REVISION_IDENTITY_NAMESPACE = UUID("c33ea7de-0007-4000-8000-71ade01a0002")
PLAN_CREATED_TRANSITION_NAMESPACE = UUID("c33ea7de-0007-4000-8000-71ade01a0003")

_DIRECTION_TO_SIDE: dict[TradeDirection, EntrySide] = {
    TradeDirection.LONG: EntrySide.BUY,
    TradeDirection.SHORT: EntrySide.SELL,
}
_PLAN_MARKET: dict[EvidenceMarketType, PlanMarketType] = {
    EvidenceMarketType.PERPETUAL: PlanMarketType.PERPETUAL,
    EvidenceMarketType.SPOT: PlanMarketType.SPOT,
}


class CanonicalTradePlanService:
    """Create immutable paper TradePlanRevisions from ACTIVE + ELIGIBLE inputs."""

    def __init__(
        self,
        *,
        store: CanonicalTradePlanStore,
        lifecycle: CandidateLifecycleService,
        eligibility: ActionEligibilityService,
        clock: Clock,
    ) -> None:
        self._store = store
        self._lifecycle = lifecycle
        self._eligibility = eligibility
        self._clock = clock
        self._lock = RLock()

    def create(self, command: CanonicalTradePlanCommand) -> CanonicalTradePlanRevision:
        assert_write_allowed(PersistenceKind.TRADE_PLAN)
        with self._lock:
            return self._create_locked(command)

    def _create_locked(self, command: CanonicalTradePlanCommand) -> CanonicalTradePlanRevision:
        candidate = self._require_candidate(command)
        evaluation = self._require_eligibility(command, candidate)
        self._validate_identity_lineage(command, candidate, evaluation)
        lineage = _lineage_from(candidate, evaluation)
        digest = uniqueness_hash(command, lineage)
        existing = self._store.get_by_uniqueness(digest)
        if existing is not None:
            self._store.bind_idempotency(
                organization_id=command.organization_id,
                idempotency_key=command.idempotency_key,
                digest=digest,
            )
            self._transition_plan_created(command, digest)
            return existing
        self._reject_idempotency_conflict(command, digest)
        occupied = self._store.get_by_candidate_scope(
            organization_id=command.organization_id,
            user_id=command.user_id,
            account_id=command.account_id,
            candidate_id=command.candidate_id,
        )
        if occupied is not None:
            raise ConflictingTradePlanIdempotencyError(
                "This candidate/account already has a canonical plan with different "
                "executable semantics."
            )
        self._validate_insert_gates(command, candidate, evaluation)
        revision = self._build_revision(command, lineage, digest)
        self._store.insert(digest, revision, idempotency_key=command.idempotency_key)
        try:
            self._transition_plan_created(command, digest)
        except BaseException:
            self._store.discard(digest)
            raise
        return revision

    def create_from_paper_validation_candidate(self, source: object) -> NoReturn:
        """Legacy queue records cannot mint canonical plan authority."""
        del source
        raise LegacyPaperValidationCannotMintPlanError(
            "PaperValidationCandidate is a downstream validation/evaluation queue "
            "and cannot mint canonical TradePlanRevision authority."
        )

    def get_scoped(
        self,
        revision_id: UUID,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> CanonicalTradePlanRevision:
        revision = self._store.get_by_revision(
            organization_id=organization_id,
            user_id=user_id,
            revision_id=revision_id,
        )
        if revision is None:
            raise CanonicalTradePlanNotFoundError(
                "Canonical trade plan revision is unknown in this tenant scope."
            )
        return revision

    def assert_approval_preserves_semantics(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        revision_id: UUID,
        plan_content_hash: str,
        modified_fields: dict[str, object] | None = None,
    ) -> CanonicalTradePlanRevision:
        """Approval may bind this revision and hash only. It cannot change semantics."""
        revision = self.get_scoped(
            revision_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if modified_fields:
            raise CanonicalTradePlanImmutableError(
                "Approval cannot change executable plan semantics."
            )
        if plan_content_hash != revision.plan.content_hash:
            raise CanonicalTradePlanImmutableError(
                "Approval must bind the exact immutable plan content hash."
            )
        return revision

    def _require_candidate(self, command: CanonicalTradePlanCommand) -> Candidate:
        candidate = self._lifecycle.get_by_candidate_id(
            command.organization_id, command.candidate_id
        )
        if candidate is None:
            raise CanonicalTradePlanNotFoundError(
                "Canonical Candidate is unknown in this organization."
            )
        _require_model_content_hash(candidate, "Candidate")
        if candidate.organization_id != command.organization_id:
            raise CanonicalTradePlanLineageError(
                "Candidate organization_id must match the plan command."
            )
        if candidate.candidate_id != command.candidate_id:
            raise CanonicalTradePlanLineageError("Loaded Candidate id must match the plan command.")
        return candidate

    def _require_eligibility(
        self, command: CanonicalTradePlanCommand, candidate: Candidate
    ) -> ActionEligibilityEvaluation:
        history = self._eligibility.history(
            organization_id=command.organization_id,
            account_id=command.account_id,
            candidate_id=command.candidate_id,
        )
        matches = [
            item for item in history if item.eligibility.eligibility_id == command.eligibility_id
        ]
        if not matches:
            raise CanonicalTradePlanNotEligibleError(
                "ActionEligibility was not issued by the eligibility authority for this "
                "organization, account, and candidate."
            )
        evaluation = matches[-1]
        _require_model_content_hash(evaluation, "ActionEligibilityEvaluation")
        _require_model_content_hash(evaluation.eligibility, "ActionEligibility")
        if (
            candidate.state is CandidateState.ACTIVE
            and evaluation.candidate_content_hash != candidate.content_hash
        ):
            raise CanonicalTradePlanLineageError(
                "ActionEligibility candidate_content_hash must match the Candidate digest."
            )
        eligibility = evaluation.eligibility
        if eligibility.candidate_id != candidate.candidate_id:
            raise CanonicalTradePlanLineageError(
                "ActionEligibility candidate_id must match the Candidate."
            )
        if eligibility.organization_id != command.organization_id:
            raise CanonicalTradePlanLineageError(
                "ActionEligibility organization_id must match the plan command."
            )
        if eligibility.user_id != command.user_id:
            raise CanonicalTradePlanLineageError(
                "ActionEligibility user_id must match the plan command."
            )
        if eligibility.account_id != command.account_id:
            raise CanonicalTradePlanLineageError(
                "ActionEligibility account_id must match the plan command."
            )
        if eligibility.assessment_id != candidate.assessment_id:
            raise CanonicalTradePlanLineageError(
                "ActionEligibility assessment_id must match the Candidate."
            )
        if evaluation.evidence_window_hash != candidate.evidence_window_hash:
            raise CanonicalTradePlanLineageError(
                "ActionEligibility evidence_window_hash must match the Candidate."
            )
        return evaluation

    def _validate_insert_gates(
        self,
        command: CanonicalTradePlanCommand,
        candidate: Candidate,
        evaluation: ActionEligibilityEvaluation,
    ) -> None:
        now = self._clock.now()
        if candidate.state is not CandidateState.ACTIVE:
            raise CanonicalTradePlanAuthorityError(
                "Only an ACTIVE canonical Candidate may create a TradePlanRevision."
            )
        if candidate.valid_until <= now:
            raise CanonicalTradePlanAuthorityError(
                "Elapsed Candidate validity cannot create a TradePlanRevision."
            )
        if command.terms.valid_until <= now:
            raise CanonicalTradePlanNotEligibleError("Plan validity has already elapsed.")
        if not evaluation.paper_actionable or not evaluation.currently_paper_actionable(now):
            raise CanonicalTradePlanNotEligibleError(
                "ActionEligibility must be currently paper-actionable to create a plan."
            )

    def _validate_identity_lineage(
        self,
        command: CanonicalTradePlanCommand,
        candidate: Candidate,
        evaluation: ActionEligibilityEvaluation,
    ) -> None:
        eligibility = evaluation.eligibility
        if evaluation.live_executable:
            raise CanonicalTradePlanNotEligibleError(
                "Canonical TradePlanRevision cannot be live-executable."
            )
        if eligibility.state is not ActionEligibilityState.ELIGIBLE:
            raise CanonicalTradePlanNotEligibleError(
                "ActionEligibility must be ELIGIBLE to create a TradePlanRevision."
            )
        if candidate.state not in {CandidateState.ACTIVE, CandidateState.PLAN_CREATED}:
            raise CanonicalTradePlanAuthorityError(
                "Terminal Candidate states cannot create a TradePlanRevision."
            )
        if eligibility.candidate_revision != candidate.transition_version:
            if candidate.state is not CandidateState.PLAN_CREATED:
                raise CanonicalTradePlanLineageError(
                    "ActionEligibility candidate_revision must match the Candidate "
                    "transition_version."
                )
            if eligibility.candidate_revision != candidate.transition_version - 1:
                raise CanonicalTradePlanLineageError(
                    "PLAN_CREATED Candidate must remain bound to the eligible revision."
                )
        terms = command.terms
        if terms.account_id != command.account_id:
            raise CanonicalTradePlanLineageError(
                "Plan account_id must match the command and ActionEligibility account."
            )
        if terms.candidate_id != candidate.candidate_id:
            raise CanonicalTradePlanLineageError(
                "Plan candidate_id must bind the exact canonical Candidate identity."
            )
        if terms.strategy_version_id != candidate.strategy_version_id:
            raise CanonicalTradePlanLineageError(
                "Plan strategy_version_id must match the Candidate."
            )
        if terms.setup_definition_id != candidate.setup_definition_id:
            raise CanonicalTradePlanLineageError(
                "Plan setup_definition_id must match the Candidate compiled setup."
            )
        if terms.timeframe != candidate.timeframe.value:
            raise CanonicalTradePlanLineageError(
                "Plan timeframe must match the Candidate timeframe exactly."
            )
        if terms.evidence_venue != candidate.evidence_venue.value:
            raise CanonicalTradePlanLineageError(
                "Plan evidence_venue must match the Candidate evidence venue exactly."
            )
        expected_market = _plan_market_type(candidate.evidence_market)
        if terms.evidence_market is not expected_market:
            raise CanonicalTradePlanLineageError(
                "Plan evidence_market must match the Candidate evidence market."
            )
        if terms.evidence_instrument != candidate.evidence_instrument:
            raise CanonicalTradePlanLineageError(
                "Plan evidence_instrument must match the Candidate evidence instrument."
            )
        expected_side = _DIRECTION_TO_SIDE[candidate.direction]
        if terms.side is not expected_side:
            raise CanonicalTradePlanLineageError(
                "Plan side must match Candidate direction (LONG→BUY, SHORT→SELL)."
            )
        if terms.valid_until > candidate.valid_until:
            raise CanonicalTradePlanLineageError("Plan valid_until cannot outlive the Candidate.")
        if terms.valid_until > eligibility.valid_until:
            raise CanonicalTradePlanLineageError(
                "Plan valid_until cannot outlive ActionEligibility."
            )

    def _build_revision(
        self,
        command: CanonicalTradePlanCommand,
        lineage: CanonicalTradePlanLineage,
        digest: str,
    ) -> CanonicalTradePlanRevision:
        plan_id = deterministic_plan_id(command)
        revision_id = deterministic_revision_id(digest)
        semantic = TradePlanRevisionSemantic(
            plan_id=plan_id,
            revision_id=revision_id,
            organization_id=command.organization_id,
            user_id=command.user_id,
            **command.terms.semantic_terms(),
        )
        plan = TradePlanRevision(
            **semantic.model_dump(mode="python"),
            correlation_id=command.correlation_id,
            content_hash=canonical_sha256(semantic),
            created_at=self._clock.now(),
            presentation_metadata=command.terms.presentation_metadata,
        )
        return CanonicalTradePlanRevision(
            plan=plan,
            lineage=lineage,
            uniqueness_hash=digest,
            paper_actionable=True,
            live_executable=False,
            content_hash=_envelope_hash(plan.content_hash, lineage, digest),
        )

    def _transition_plan_created(
        self, command: CanonicalTradePlanCommand, digest: str
    ) -> Candidate:
        return self._lifecycle.transition(
            organization_id=command.organization_id,
            candidate_id=command.candidate_id,
            new_state=CandidateState.PLAN_CREATED,
            reason_codes=(CandidateReasonCode.PLAN_CREATED,),
            idempotency_key=_plan_created_idempotency_key(digest),
            correlation_id=_plan_created_correlation_id(digest),
        )

    def _reject_idempotency_conflict(self, command: CanonicalTradePlanCommand, digest: str) -> None:
        bound = self._store.get_by_idempotency(
            organization_id=command.organization_id,
            idempotency_key=command.idempotency_key,
        )
        if bound is not None and bound.uniqueness_hash != digest:
            raise ConflictingTradePlanIdempotencyError(
                "Plan idempotency key is already bound to a different canonical uniqueness "
                "fingerprint."
            )


def uniqueness_preimage(
    command: CanonicalTradePlanCommand, lineage: CanonicalTradePlanLineage
) -> dict[str, object]:
    """Semantic identity for converge/conflict. Excludes clocks, correlation, presentation."""
    return {
        "account_id": command.account_id,
        "eligibility_id": command.eligibility_id,
        "lineage": lineage.model_dump(mode="python"),
        "organization_id": command.organization_id,
        "terms": command.terms.semantic_terms(),
        "user_id": command.user_id,
    }


def uniqueness_hash(command: CanonicalTradePlanCommand, lineage: CanonicalTradePlanLineage) -> str:
    return canonical_sha256(uniqueness_preimage(command, lineage))


def deterministic_plan_id(command: CanonicalTradePlanCommand) -> UUID:
    material = (
        f"{command.organization_id}:{command.user_id}:{command.account_id}:{command.candidate_id}"
    )
    return uuid5(PLAN_IDENTITY_NAMESPACE, material)


def deterministic_revision_id(digest: str) -> UUID:
    return uuid5(REVISION_IDENTITY_NAMESPACE, digest)


def in_memory_canonical_trade_plan(
    *,
    now: datetime | None = None,
    lifecycle: CandidateLifecycleService | None = None,
    eligibility: ActionEligibilityService | None = None,
    store: CanonicalTradePlanStore | None = None,
) -> CanonicalTradePlanService:
    """Factory for tests and local paper use. No network, no PostgreSQL."""
    from app.signal_fusion.action_eligibility import in_memory_action_eligibility
    from app.signal_fusion.lifecycle import in_memory_candidate_lifecycle

    clock: Clock = FrozenClock(now) if now is not None else UtcClock()
    return CanonicalTradePlanService(
        store=store or InMemoryCanonicalTradePlanStore(),
        lifecycle=lifecycle or in_memory_candidate_lifecycle(now=now),
        eligibility=eligibility or in_memory_action_eligibility(now=now),
        clock=clock,
    )


def _lineage_from(
    candidate: Candidate, evaluation: ActionEligibilityEvaluation
) -> CanonicalTradePlanLineage:
    return CanonicalTradePlanLineage(
        candidate_id=candidate.candidate_id,
        candidate_revision=evaluation.eligibility.candidate_revision,
        candidate_content_hash=evaluation.candidate_content_hash,
        assessment_id=candidate.assessment_id,
        eligibility_id=evaluation.eligibility.eligibility_id,
        eligibility_content_hash=evaluation.content_hash,
        eligibility_uniqueness_hash=evaluation.uniqueness_hash,
        eligibility_state=ActionEligibilityState.ELIGIBLE,
        evidence_window_hash=evaluation.evidence_window_hash,
        strategy_version_id=candidate.strategy_version_id,
        setup_definition_id=candidate.setup_definition_id,
        compiled_setup_content_hash=candidate.executable_setup.content_hash,
        fusion_policy_version=candidate.fusion_policy_version,
    )


def _plan_market_type(market: EvidenceMarketType) -> PlanMarketType:
    mapped = _PLAN_MARKET.get(market)
    if mapped is None:
        raise CanonicalTradePlanLineageError(
            f"Candidate evidence market {market.value} cannot occupy a trade plan."
        )
    return mapped


def _plan_created_idempotency_key(digest: str) -> str:
    return f"canonical-plan:{digest[:32]}"


def _plan_created_correlation_id(digest: str) -> UUID:
    return uuid5(PLAN_CREATED_TRANSITION_NAMESPACE, digest)


def _envelope_hash(plan_content_hash: str, lineage: CanonicalTradePlanLineage, digest: str) -> str:
    return canonical_sha256(
        {
            "lineage": lineage.model_dump(mode="python"),
            "plan_content_hash": plan_content_hash,
            "uniqueness_hash": digest,
        }
    )


def _require_model_content_hash(value: CanonicalModel, label: str) -> None:
    digest = semantic_content_hash(value, extra_exclude=CONTENT_HASH_EXCLUDE)
    claimed = value.model_dump()["content_hash"]
    if claimed != digest:
        raise CanonicalTradePlanLineageError(
            f"{label} content hash is not the canonical semantic digest."
        )


__all__ = [
    "PLAN_IDENTITY_NAMESPACE",
    "REVISION_IDENTITY_NAMESPACE",
    "CanonicalTradePlanService",
    "deterministic_plan_id",
    "deterministic_revision_id",
    "in_memory_canonical_trade_plan",
    "uniqueness_hash",
    "uniqueness_preimage",
]
