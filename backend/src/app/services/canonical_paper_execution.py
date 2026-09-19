"""Canonical PAPER execution application layer.

EXECUTE_PAPER_PLAN for ``plan_authority=canonical`` must bind the exact approved
immutable TradePlanRevision and re-verify Candidate, ActionEligibility, plan,
approval, and account lineage immediately before the claim transaction.

RiskEngine BLOCK and the kill switch remain final inside PaperPlanClaimService.
This module never calls an exchange.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, TradingPolicyError
from app.core.paper_safety import assert_paper_execution_allowed
from app.db.canonical_trade_plans import PLAN_AUTHORITY_CANONICAL
from app.runtime.canonical import ProductionCanonicalRuntime
from app.schemas.approval import ApprovalAuthorization
from app.schemas.canonical_trade_plan import CanonicalTradePlanRevision
from app.schemas.common import JournalLifecycleEventType, TradeDirection
from app.schemas.execution_protocol import (
    ExecutePaperPlanRequest,
    ExecutePaperPlanResult,
    ExecutionCommandOutcome,
    UniqueFillResult,
)
from app.schemas.journal_lifecycle import JournalLifecycleEventInput, JournalLineagePayload
from app.schemas.trade_plan import EntrySide, TradePlanRevision
from app.services.audit_service import AuditService
from app.services.canonical_execution_journal import (
    CANONICAL_EXECUTION_SOURCE_SYSTEM,
    project_canonical_execution_event,
)
from app.services.canonical_trade_plan_errors import CanonicalTradePlanNotFoundError
from app.services.execution_claim import ExecutionClaimHooks, PaperPlanClaimService
from app.services.journal_lifecycle_projector import JournalLifecycleProjector
from app.services.safety_epoch import SafetyEpochService
from app.signal_fusion.enums import CandidateState

_TERMINAL_CANDIDATE_REASONS: dict[CandidateState, str] = {
    CandidateState.REJECTED: "candidate_rejected",
    CandidateState.SKIPPED: "candidate_skipped",
    CandidateState.EXPIRED: "candidate_expired",
    CandidateState.INVALIDATED: "candidate_invalidated",
}


class CanonicalPaperExecutionService:
    """Paper-only execution for canonical TradePlanRevision rows."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        audit_service: AuditService,
        runtime: ProductionCanonicalRuntime,
        *,
        safety_epochs: SafetyEpochService,
        clock: Callable[[], datetime],
        hooks: ExecutionClaimHooks | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._audit = audit_service
        self._runtime = runtime
        self._clock = clock
        self._projector = JournalLifecycleProjector(session, audit_service)
        claim_hooks = hooks or ExecutionClaimHooks()
        self._claim = PaperPlanClaimService(
            session,
            settings,
            safety_epochs,
            clock=clock,
            hooks=ExecutionClaimHooks(
                after_idempotency=claim_hooks.after_idempotency,
                after_epoch_lock=claim_hooks.after_epoch_lock,
                before_return=claim_hooks.before_return,
                revalidate=self._revalidate_canonical_lineage,
            ),
        )

    def execute(self, request: ExecutePaperPlanRequest) -> ExecutePaperPlanResult:
        assert_paper_execution_allowed(self._settings)
        with self._runtime.bind_session(self._session):
            result = self._claim.claim(request)
            if result.outcome is ExecutionCommandOutcome.ALLOW:
                self._project_approved_plan(request, result)
            return result

    def project_fill(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        account_id: UUID,
        command_id: UUID,
        fill: UniqueFillResult,
        revision_id: UUID,
    ) -> None:
        with self._runtime.bind_session(self._session):
            envelope = self._runtime.plans.get_scoped(
                revision_id,
                organization_id=organization_id,
                user_id=user_id,
            )
            payload = _instrument_payload(envelope.plan)
            if fill.weighted_price is not None:
                payload["entry_price"] = str(fill.weighted_price)
            payload["size"] = str(fill.filled_quantity)
            # Phase 1 paper claims do not create legacy Order rows. Command
            # identity is execution_lifecycle_id; linked_order_id stays unset.
            payload["lineage"] = _lineage_payload(envelope, command_id).model_dump(
                mode="json", exclude_none=True
            )
            project_canonical_execution_event(
                self._projector,
                event=JournalLifecycleEventInput(
                    event_type=JournalLifecycleEventType.FILL,
                    execution_lifecycle_id=command_id,
                    source_system=CANONICAL_EXECUTION_SOURCE_SYSTEM,
                    source_aggregate="execution-command",
                    source_event_id=str(fill.fill_id),
                    source_event_version=1,
                    account_id=account_id,
                    payload=payload,
                    correlation_id=str(envelope.plan.correlation_id),
                ),
                organization_id=organization_id,
                user_id=user_id,
            )

    def _revalidate_canonical_lineage(
        self,
        *,
        plan: TradePlanRevision,
        authorization: ApprovalAuthorization,
        request: ExecutePaperPlanRequest,
        at: datetime,
    ) -> str | None:
        try:
            envelope = self._runtime.plans.get_scoped(
                request.revision_id,
                organization_id=request.organization_id,
                user_id=request.user_id,
            )
        except CanonicalTradePlanNotFoundError as exc:
            raise NotFoundError(
                "Canonical trade plan revision is unknown in this tenant scope."
            ) from exc
        if envelope.plan.content_hash != plan.content_hash:
            return "canonical_plan_modified"
        if envelope.plan.content_hash != authorization.plan_content_hash:
            return "plan_hash_mismatch"
        if envelope.live_executable:
            return "live_execution_forbidden"
        if envelope.plan.account_id != request.account_id:
            return "account_mismatch"
        if envelope.plan.account_id != authorization.account_id:
            return "account_mismatch"
        if envelope.plan.revision_id != authorization.revision_id:
            return "plan_revision_mismatch"
        candidate = self._runtime.lifecycle.get_by_candidate_id(
            request.organization_id, envelope.lineage.candidate_id
        )
        if candidate is None:
            raise NotFoundError("Canonical Candidate is unknown in this organization.")
        if candidate.organization_id != request.organization_id:
            raise TradingPolicyError(
                "Canonical Candidate belongs to a different organization.",
                details={"reason": "tenant_isolation"},
            )
        if candidate.candidate_id != envelope.plan.candidate_id:
            return "canonical_lineage_mismatch"
        terminal = _TERMINAL_CANDIDATE_REASONS.get(candidate.state)
        if terminal is not None:
            return terminal
        if candidate.state is not CandidateState.PLAN_CREATED:
            return "candidate_not_plan_created"
        # PLAN_CREATED appends a transition; lineage identity hashes remain the
        # pre-transition Candidate digest.
        if candidate.valid_until <= at:
            return "candidate_expired"
        evaluation = self._runtime.eligibility.get(envelope.lineage.eligibility_uniqueness_hash)
        if evaluation is None:
            return "eligibility_not_found"
        if evaluation.eligibility.eligibility_id != envelope.lineage.eligibility_id:
            return "eligibility_mismatch"
        if evaluation.content_hash != envelope.lineage.eligibility_content_hash:
            return "canonical_lineage_mismatch"
        if evaluation.eligibility.account_id != request.account_id:
            return "account_mismatch"
        if evaluation.live_executable:
            return "live_execution_forbidden"
        if not evaluation.currently_paper_actionable(at):
            return "eligibility_not_actionable"
        return None

    def _project_approved_plan(
        self, request: ExecutePaperPlanRequest, result: ExecutePaperPlanResult
    ) -> None:
        envelope = self._runtime.plans.get_scoped(
            request.revision_id,
            organization_id=request.organization_id,
            user_id=request.user_id,
        )
        payload = _instrument_payload(envelope.plan)
        payload["lineage"] = _lineage_payload(envelope, result.command_id).model_dump(
            mode="json", exclude_none=True
        )
        project_canonical_execution_event(
            self._projector,
            event=JournalLifecycleEventInput(
                event_type=JournalLifecycleEventType.APPROVED_PLAN,
                execution_lifecycle_id=result.command_id,
                source_system=CANONICAL_EXECUTION_SOURCE_SYSTEM,
                source_aggregate="execution-command",
                source_event_id=str(result.command_id),
                source_event_version=1,
                account_id=request.account_id,
                payload=payload,
                correlation_id=str(envelope.plan.correlation_id),
            ),
            organization_id=request.organization_id,
            user_id=request.user_id,
        )


def is_canonical_plan_authority(plan_authority: str | None) -> bool:
    return plan_authority == PLAN_AUTHORITY_CANONICAL


def _instrument_payload(plan: TradePlanRevision) -> dict[str, object]:
    direction = TradeDirection.LONG if plan.side is EntrySide.BUY else TradeDirection.SHORT
    return {
        "symbol": plan.execution_instrument,
        "timeframe": plan.timeframe,
        "direction": direction.value,
        "thesis": "Canonical paper execution of an approved TradePlanRevision.",
        "planned_entry_price": str(plan.entry_zone.lower),
        "planned_stop_price": str(plan.risk_and_exits.stop.value),
        "planned_risk_amount": str(plan.risk_and_exits.risk_budget.value),
        "size": str(plan.quantity.value),
        "leverage": str(plan.risk_and_exits.leverage),
        "linked_proposal_id": str(plan.plan_id),
        "strategy_version_id": str(plan.strategy_version_id),
    }


def _lineage_payload(
    envelope: CanonicalTradePlanRevision, execution_lifecycle_id: UUID
) -> JournalLineagePayload:
    lineage = envelope.lineage
    return JournalLineagePayload(
        organization_id=envelope.plan.organization_id,
        account_id=envelope.plan.account_id,
        execution_lifecycle_id=execution_lifecycle_id,
        candidate_id=lineage.candidate_id,
        candidate_content_hash=lineage.candidate_content_hash,
        assessment_id=lineage.assessment_id,
        evidence_window_hash=lineage.evidence_window_hash,
        trade_plan_revision_id=envelope.plan.revision_id,
        trade_plan_content_hash=envelope.plan.content_hash,
        setup_definition_id=lineage.setup_definition_id,
        strategy_version_id=lineage.strategy_version_id,
        fusion_policy_version=lineage.fusion_policy_version,
        uniqueness_tuple_hash=envelope.uniqueness_hash,
    )
