"""Canonical Candidate + ActionEligibility → immutable TradePlanRevision."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.db.models import TradePlanRevision as TradePlanRevisionModel
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.canonical_trade_plan import CanonicalTradePlanCommand
from app.schemas.common import ApprovalAction
from app.schemas.trade_plan import TradePlanRevisionSemantic
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.canonical_serialization import canonical_sha256
from app.services.canonical_trade_plan import (
    CanonicalTradePlanService,
    in_memory_canonical_trade_plan,
)
from app.services.canonical_trade_plan_binding import (
    REQUIRED_CANONICAL_TRADE_PLAN_DATABASE_BINDINGS,
    UnboundSqlAlchemyCanonicalTradePlanAdapter,
)
from app.services.canonical_trade_plan_errors import (
    CanonicalTradePlanAuthorityError,
    CanonicalTradePlanImmutableError,
    CanonicalTradePlanLineageError,
    CanonicalTradePlanNotEligibleError,
    CanonicalTradePlanNotFoundError,
    CanonicalTradePlanPersistenceNotBoundError,
    ConflictingTradePlanIdempotencyError,
    LegacyPaperValidationCannotMintPlanError,
)
from app.services.proposal_service import ProposalService
from app.signal_fusion.action_eligibility import in_memory_action_eligibility
from app.signal_fusion.adapters import DownstreamPaperValidationCandidateRef
from app.signal_fusion.enums import ActionEligibilityState, CandidateReasonCode, CandidateState
from app.signal_fusion.lifecycle import in_memory_candidate_lifecycle
from tests.support.phase1_plan_fixtures import (
    persist_plan,
    plan_request,
    seed_support,
    sqlite_session,
)
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_eligibility import (
    ACCOUNT_B,
    ORG_B,
    USER_B,
    eligibility_command,
    paper_configuration,
    safety_snapshot,
)
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    CORRELATION_A,
    CORRELATION_B,
    ORG_ID,
    USER_ID,
    make_assessment,
    make_creation_command,
    make_evidence_window,
)
from tests.support.phase7_trade_plan import make_world, plan_command, plan_terms, unused_uuid

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture
def session() -> Iterator[Session]:
    yield from sqlite_session()


def test_active_eligible_candidate_creates_immutable_plan() -> None:
    world = make_world()
    created = world.plans.create(plan_command(world))
    assert created.live_executable is False
    assert created.paper_actionable is True
    assert created.plan.candidate_id == world.candidate.candidate_id
    assert created.lineage.candidate_id == world.candidate.candidate_id
    assert created.lineage.candidate_content_hash == world.candidate.content_hash
    assert created.lineage.eligibility_id == world.evaluation.eligibility.eligibility_id
    assert created.lineage.eligibility_state is ActionEligibilityState.ELIGIBLE
    assert created.plan.organization_id == ORG_ID
    assert created.plan.user_id == USER_ID
    assert created.plan.account_id == ACCOUNT_ID
    semantic = TradePlanRevisionSemantic.model_validate(
        created.plan.model_dump(
            mode="python",
            exclude={"correlation_id", "content_hash", "created_at", "presentation_metadata"},
        )
    )
    assert canonical_sha256(semantic) == created.plan.content_hash
    projected = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert projected is not None
    assert projected.state is CandidateState.PLAN_CREATED
    history = world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)
    assert len(history) == 1
    assert history[0].new_state is CandidateState.PLAN_CREATED


def test_identical_requests_converge_including_after_plan_created() -> None:
    world = make_world()
    first = world.plans.create(plan_command(world))
    second = world.plans.create(plan_command(world, idempotency_key="canonical-plan-create-2"))
    third = world.plans.create(
        plan_command(
            world,
            correlation_id=CORRELATION_B,
            terms=plan_terms(world.candidate, presentation_metadata={"display_title": "other"}),
        )
    )
    assert first.plan.revision_id == second.plan.revision_id == third.plan.revision_id
    assert first.content_hash == second.content_hash == third.content_hash
    assert first.plan.correlation_id == third.plan.correlation_id
    assert first.plan.presentation_metadata.display_title == "BTC setup"
    projected = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert projected is not None
    assert projected.state is CandidateState.PLAN_CREATED
    assert len(world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)) == 1


def test_conflicting_idempotency_fails_closed() -> None:
    world = make_world()
    world.plans.create(plan_command(world))
    with pytest.raises(ConflictingTradePlanIdempotencyError):
        world.plans.create(
            plan_command(
                world,
                terms=plan_terms(world.candidate, quantity={"value": "3.000", "unit": "CONTRACTS"}),
            )
        )
    projected = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert projected is not None
    assert projected.state is CandidateState.PLAN_CREATED


def test_conflicting_semantics_for_same_candidate_fail_closed() -> None:
    world = make_world()
    world.plans.create(plan_command(world))
    with pytest.raises(ConflictingTradePlanIdempotencyError):
        world.plans.create(
            plan_command(
                world,
                idempotency_key="canonical-plan-create-other",
                terms=plan_terms(world.candidate, quantity={"value": "3.000", "unit": "CONTRACTS"}),
            )
        )


def test_failed_create_does_not_transition_candidate() -> None:
    world = make_world()
    with pytest.raises(CanonicalTradePlanLineageError):
        world.plans.create(
            plan_command(world, terms=plan_terms(world.candidate, candidate_id=unused_uuid()))
        )
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE
    assert world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id) == ()


def test_paper_validation_candidate_cannot_mint_canonical_plan() -> None:
    world = make_world()
    with pytest.raises(LegacyPaperValidationCannotMintPlanError):
        world.plans.create_from_paper_validation_candidate(
            DownstreamPaperValidationCandidateRef(
                paper_validation_candidate_id=uuid4(),
                canonical_candidate_id=world.candidate.candidate_id,
            )
        )
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE


def test_legacy_proposal_path_still_cannot_create_executable_plan(session: Session) -> None:
    ids = seed_support(session)
    with pytest.raises(ValidationAppError, match="ANALYSIS_ONLY_CANNOT_CREATE_EXECUTABLE_PLAN"):
        ProposalService(session, AuditService(session)).create_revision(
            ids["proposal_id"],
            plan_request(ids),
            organization_id=ids["organization"].id,
            user_id=ids["user"].id,
        )
    assert session.query(TradePlanRevisionModel).count() == 0


def test_blocked_eligibility_cannot_create_plan() -> None:
    window = make_evidence_window()
    assessment = make_assessment(window)
    lifecycle = in_memory_candidate_lifecycle(now=EVALUATED_AT)
    candidate = lifecycle.create_from_confirmed_setup(
        make_creation_command(window=window, assessment=assessment)
    )
    eligibility = in_memory_action_eligibility(now=EVALUATED_AT)
    blocked = eligibility.evaluate(
        eligibility_command(
            window=window,
            assessment=assessment,
            candidate=candidate,
            safety=safety_snapshot(kill_switch_active=True),
        )
    )
    assert blocked.eligibility.state is not ActionEligibilityState.ELIGIBLE
    plans = in_memory_canonical_trade_plan(
        now=EVALUATED_AT, lifecycle=lifecycle, eligibility=eligibility
    )

    with pytest.raises(CanonicalTradePlanNotEligibleError):
        plans.create(
            CanonicalTradePlanCommand(
                organization_id=ORG_ID,
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                candidate_id=candidate.candidate_id,
                eligibility_id=blocked.eligibility.eligibility_id,
                terms=plan_terms(candidate),
                idempotency_key="blocked-plan-create-1",
                correlation_id=CORRELATION_A,
            )
        )
    stored = lifecycle.get_by_candidate_id(ORG_ID, candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE


def test_unknown_eligibility_fails_closed() -> None:
    world = make_world()
    with pytest.raises(CanonicalTradePlanNotEligibleError):
        world.plans.create(plan_command(world, eligibility_id=unused_uuid()))
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE


def test_scope_mismatch_fails_closed() -> None:
    world = make_world()
    with pytest.raises(CanonicalTradePlanNotEligibleError):
        world.plans.create(plan_command(world, account_id=ACCOUNT_B))
    with pytest.raises(CanonicalTradePlanNotFoundError):
        world.plans.create(plan_command(world, organization_id=ORG_B))
    with pytest.raises(CanonicalTradePlanLineageError):
        world.plans.create(plan_command(world, user_id=USER_B))
    with pytest.raises(CanonicalTradePlanLineageError):
        world.plans.create(
            plan_command(world, terms=plan_terms(world.candidate, account_id=ACCOUNT_B))
        )


def test_plan_terms_must_bind_canonical_candidate_identity() -> None:
    world = make_world()
    with pytest.raises(CanonicalTradePlanLineageError, match="candidate_id"):
        world.plans.create(
            plan_command(world, terms=plan_terms(world.candidate, candidate_id=unused_uuid()))
        )
    with pytest.raises(CanonicalTradePlanLineageError, match="evidence_venue"):
        world.plans.create(
            plan_command(world, terms=plan_terms(world.candidate, evidence_venue="BINANCE"))
        )
    with pytest.raises(CanonicalTradePlanLineageError, match="side"):
        world.plans.create(plan_command(world, terms=plan_terms(world.candidate, side="BUY")))


def test_rejected_candidate_cannot_create_plan() -> None:
    world = make_world()
    world.lifecycle.transition(
        organization_id=ORG_ID,
        candidate_id=world.candidate.candidate_id,
        new_state=CandidateState.REJECTED,
        reason_codes=(CandidateReasonCode.REJECTED,),
        idempotency_key="reject-before-plan",
        correlation_id=world.candidate.correlation_id,
    )
    with pytest.raises(CanonicalTradePlanAuthorityError):
        world.plans.create(plan_command(world))


def test_approval_cannot_change_executable_semantics() -> None:
    world = make_world()
    created = world.plans.create(plan_command(world))
    preserved = world.plans.assert_approval_preserves_semantics(
        organization_id=ORG_ID,
        user_id=USER_ID,
        revision_id=created.plan.revision_id,
        plan_content_hash=created.plan.content_hash,
        modified_fields=None,
    )
    assert preserved.content_hash == created.content_hash
    with pytest.raises(CanonicalTradePlanImmutableError):
        world.plans.assert_approval_preserves_semantics(
            organization_id=ORG_ID,
            user_id=USER_ID,
            revision_id=created.plan.revision_id,
            plan_content_hash=created.plan.content_hash,
            modified_fields={"quantity": "3"},
        )
    with pytest.raises(CanonicalTradePlanImmutableError):
        world.plans.assert_approval_preserves_semantics(
            organization_id=ORG_ID,
            user_id=USER_ID,
            revision_id=created.plan.revision_id,
            plan_content_hash="00" * 32,
        )
        with pytest.raises((AttributeError, ValidationError)):
            created.plan.quantity = created.plan.quantity  # type: ignore[misc]


def test_phase1_approval_still_rejects_modified_fields(session: Session) -> None:
    ids = seed_support(session)
    plan = persist_plan(session, ids)
    clock = datetime(2026, 9, 15, 14, 1, tzinfo=UTC)
    service = ApprovalService(session, AuditService(session), clock=lambda: clock)
    approval = service.create_for_plan_revision(
        revision_id=plan.revision_id,
        organization_id=plan.organization_id,
        user_id=plan.user_id,
        authorization_expires_at=clock + timedelta(minutes=10),
    )
    with pytest.raises(ValidationAppError, match="cannot modify immutable plan"):
        service.decide(
            approval.id,
            ApprovalDecisionRequest(
                action=ApprovalAction.APPROVE,
                modified_fields={"quantity": "3"},
            ),
            principal_organization_id=plan.organization_id,
            principal_user_id=plan.user_id,
        )


def test_sqlalchemy_adapter_refuses_canonical_persist() -> None:
    world = make_world()
    created = world.plans.create(plan_command(world))
    adapter = UnboundSqlAlchemyCanonicalTradePlanAdapter()
    with pytest.raises(CanonicalTradePlanPersistenceNotBoundError, match="never writes"):
        adapter.persist(created)
    artifacts = {item.artifact for item in adapter.required_bindings()}
    assert "trade_plan_revisions.candidate_id" in artifacts
    assert len(REQUIRED_CANONICAL_TRADE_PLAN_DATABASE_BINDINGS) >= 6


def test_orm_canonical_plan_does_not_reuse_pvc_fk() -> None:
    candidate_fks = list(TradePlanRevisionModel.__table__.c.candidate_id.foreign_keys)
    assert candidate_fks == []
    canonical_fks = list(TradePlanRevisionModel.__table__.c.canonical_candidate_id.foreign_keys)
    assert len(canonical_fks) == 1
    assert canonical_fks[0].column.table.name == "canonical_candidates"
    compiled_fks = list(
        TradePlanRevisionModel.__table__.c.compiled_setup_definition_id.foreign_keys
    )
    assert compiled_fks[0].column.table.name == "compiled_setup_definitions"
    mapper = inspect(TradePlanRevisionModel)
    column_names = {column.key for column in mapper.columns}
    assert "plan_authority" in column_names
    assert "canonical_candidate_id" in column_names
    assert "eligibility_id" not in column_names
    assert "candidate_content_hash" not in column_names


def test_service_has_no_execution_surface() -> None:
    assert not hasattr(CanonicalTradePlanService, "execute")
    assert not hasattr(CanonicalTradePlanService, "dispatch")
    assert not hasattr(CanonicalTradePlanService, "place_order")
    assert not hasattr(CanonicalTradePlanService, "submit")


def test_concurrent_identical_creates_converge() -> None:
    world = make_world()
    command = plan_command(world)

    def _run(_: int) -> str:
        return world.plans.create(command).content_hash

    with ThreadPoolExecutor(max_workers=8) as pool:
        hashes = list(pool.map(_run, range(16)))
    assert len(set(hashes)) == 1
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.PLAN_CREATED
    assert len(world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)) == 1


def test_canonical_layer_does_not_import_execution_dispatch() -> None:
    text = (SRC / "app/services/canonical_trade_plan.py").read_text(encoding="utf-8")
    assert "execution_claim" not in text
    assert "venue_submit_dispatcher" not in text
    assert "from app.db.models import PaperValidationCandidate" not in text
    assert "execution_service" not in text


def test_tenant_isolation_on_get() -> None:
    world = make_world()
    created = world.plans.create(plan_command(world))
    with pytest.raises(CanonicalTradePlanNotFoundError):
        world.plans.get_scoped(
            created.plan.revision_id,
            organization_id=ORG_B,
            user_id=USER_ID,
        )


def test_live_configuration_eligibility_cannot_create_plan() -> None:
    window = make_evidence_window()
    assessment = make_assessment(window)
    lifecycle = in_memory_candidate_lifecycle(now=EVALUATED_AT)
    candidate = lifecycle.create_from_confirmed_setup(
        make_creation_command(window=window, assessment=assessment)
    )
    eligibility = in_memory_action_eligibility(now=EVALUATED_AT)
    blocked = eligibility.evaluate(
        eligibility_command(
            window=window,
            assessment=assessment,
            candidate=candidate,
            configuration=paper_configuration(enable_real_trading=True),
        )
    )
    plans = in_memory_canonical_trade_plan(
        now=EVALUATED_AT, lifecycle=lifecycle, eligibility=eligibility
    )

    with pytest.raises(CanonicalTradePlanNotEligibleError):
        plans.create(
            CanonicalTradePlanCommand(
                organization_id=ORG_ID,
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                candidate_id=candidate.candidate_id,
                eligibility_id=blocked.eligibility.eligibility_id,
                terms=plan_terms(candidate),
                idempotency_key="live-config-plan-create-1",
                correlation_id=CORRELATION_A,
            )
        )
