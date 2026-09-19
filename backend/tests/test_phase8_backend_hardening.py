"""AT-059 adversarial backend hardening: attribution, UoW, risk authority, safety."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFoundError, TradingPolicyError
from app.db.learning_attribution import LearningAttributionRecordRow
from app.db.models import (
    ApprovalAuthorization,
    ExecutionCommand,
    JournalLifecycleEvent,
    JournalTrade,
    Membership,
    UsageEvent,
)
from app.db.session import get_session
from app.learning_attribution.errors import (
    CrossTenantAttributionError,
    LearningAttributionIncompleteError,
)
from app.main import create_app
from app.schemas.common import JournalLifecycleEventType, MembershipRole
from app.schemas.execution_protocol import ExecutionCommandOutcome
from app.schemas.trade_plan import AuthorizationState
from app.security.tokens import create_access_token
from app.services.audit_service import AuditService
from app.services.canonical_execution_learning import require_canonical_attribution_lineage
from app.services.canonical_reads import CanonicalReadService
from app.services.execution_claim import ExecutionClaimHooks
from app.services.execution_service import ExecutionService
from tests.support.phase6_fusion import ORG_ID, USER_ID
from tests.support.phase8_runtime import (
    EXECUTE_AT,
    build_runtime,
    canonical_execute_request,
    canonical_execution_service,
    phase8_settings,
    prepared_authorized_canonical,
)
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres


def _factory() -> sessionmaker[Session]:
    return phase7_plan_session_factory()


def _envelope(*, organization_id=ORG_ID) -> SimpleNamespace:
    return SimpleNamespace(
        plan=SimpleNamespace(organization_id=organization_id),
        lineage=SimpleNamespace(candidate_id=uuid4(), eligibility_uniqueness_hash="a" * 64),
    )


def test_missing_candidate_fails_closed_with_explicit_reason() -> None:
    runtime = SimpleNamespace(
        lifecycle=SimpleNamespace(get_by_candidate_id=lambda *_a, **_k: None),
        eligibility=SimpleNamespace(get=lambda *_a, **_k: object()),
    )
    with pytest.raises(LearningAttributionIncompleteError) as exc:
        require_canonical_attribution_lineage(
            runtime=runtime,  # type: ignore[arg-type]
            organization_id=ORG_ID,
            envelope=_envelope(),  # type: ignore[arg-type]
        )
    assert exc.value.details["reason"] == "missing_candidate"
    assert exc.value.code == "learning_attribution_incomplete"


def test_missing_eligibility_fails_closed_with_explicit_reason() -> None:
    runtime = SimpleNamespace(
        lifecycle=SimpleNamespace(get_by_candidate_id=lambda *_a, **_k: object()),
        eligibility=SimpleNamespace(get=lambda *_a, **_k: None),
    )
    with pytest.raises(LearningAttributionIncompleteError) as exc:
        require_canonical_attribution_lineage(
            runtime=runtime,  # type: ignore[arg-type]
            organization_id=ORG_ID,
            envelope=_envelope(),  # type: ignore[arg-type]
        )
    assert exc.value.details["reason"] == "missing_eligibility"


def test_blank_assessment_hash_is_required_lineage_failure() -> None:
    runtime = SimpleNamespace(
        lifecycle=SimpleNamespace(get_by_candidate_id=lambda *_a, **_k: object()),
        eligibility=SimpleNamespace(
            get=lambda *_a, **_k: SimpleNamespace(setup_assessment_content_hash="   ")
        ),
    )
    with pytest.raises(LearningAttributionIncompleteError) as exc:
        require_canonical_attribution_lineage(
            runtime=runtime,  # type: ignore[arg-type]
            organization_id=ORG_ID,
            envelope=_envelope(),  # type: ignore[arg-type]
        )
    assert exc.value.details["reason"] == "missing_required_lineage"


def test_cross_tenant_envelope_fails_closed() -> None:
    runtime = SimpleNamespace(
        lifecycle=SimpleNamespace(get_by_candidate_id=lambda *_a, **_k: object()),
        eligibility=SimpleNamespace(
            get=lambda *_a, **_k: SimpleNamespace(setup_assessment_content_hash="b" * 64)
        ),
    )
    with pytest.raises(CrossTenantAttributionError):
        require_canonical_attribution_lineage(
            runtime=runtime,  # type: ignore[arg-type]
            organization_id=ORG_ID,
            envelope=_envelope(organization_id=uuid4()),  # type: ignore[arg-type]
        )


@requires_postgres
def test_allow_rolls_back_when_candidate_disappears_before_attribution() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:

        def _hide_candidate() -> None:
            runtime.lifecycle.get_by_candidate_id = (  # type: ignore[method-assign]
                lambda _organization_id, _candidate_id: None
            )

        service = canonical_execution_service(session, runtime)
        with pytest.raises(LearningAttributionIncompleteError) as exc:
            service.execute_paper_plan(
                canonical_execute_request(envelope, authorization, key="hide-candidate"),
                clock=lambda: EXECUTE_AT,
                hooks=ExecutionClaimHooks(before_return=_hide_candidate),
            )
        assert exc.value.details["reason"] == "missing_candidate"
        session.rollback()
        assert session.scalars(select(LearningAttributionRecordRow)).first() is None
        assert session.scalars(select(JournalLifecycleEvent)).first() is None
        assert session.scalars(select(JournalTrade)).first() is None
        assert session.scalars(select(ExecutionCommand)).first() is None
        auth = session.get(ApprovalAuthorization, authorization.authorization_id)
        assert auth is not None
        assert auth.state is AuthorizationState.AVAILABLE
    finally:
        session.close()


@requires_postgres
def test_allow_rolls_back_when_eligibility_disappears_before_journal() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:

        def _hide_eligibility() -> None:
            runtime.eligibility.get = lambda _digest: None  # type: ignore[method-assign]

        service = canonical_execution_service(session, runtime)
        with pytest.raises(LearningAttributionIncompleteError) as exc:
            service.execute_paper_plan(
                canonical_execute_request(envelope, authorization, key="hide-eligibility"),
                clock=lambda: EXECUTE_AT,
                hooks=ExecutionClaimHooks(before_return=_hide_eligibility),
            )
        assert exc.value.details["reason"] == "missing_eligibility"
        session.rollback()
        assert session.scalars(select(LearningAttributionRecordRow)).first() is None
        assert session.scalars(select(JournalLifecycleEvent)).first() is None
        auth = session.get(ApprovalAuthorization, authorization.authorization_id)
        assert auth is not None
        assert auth.state is AuthorizationState.AVAILABLE
    finally:
        session.close()


@requires_postgres
def test_crash_before_commit_leaves_no_execution_journal_or_learning() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:
        service = canonical_execution_service(session, runtime)
        result = service.execute_paper_plan(
            canonical_execute_request(envelope, authorization, key="crash-before-commit"),
            clock=lambda: EXECUTE_AT,
        )
        assert result.outcome is ExecutionCommandOutcome.ALLOW
        session.rollback()
    finally:
        session.close()
    session = factory()
    try:
        assert session.scalars(select(ExecutionCommand)).first() is None
        assert session.scalars(select(JournalLifecycleEvent)).first() is None
        assert session.scalars(select(LearningAttributionRecordRow)).first() is None
        auth = session.get(ApprovalAuthorization, authorization.authorization_id)
        assert auth is not None
        assert auth.state is AuthorizationState.AVAILABLE
    finally:
        session.close()


@requires_postgres
def test_claim_time_risk_authority_is_predicate_not_legacy_gate() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:
        service = canonical_execution_service(session, runtime)

        def _boom(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("PaperExecutionRiskGate must not run on EXECUTE_PAPER_PLAN")

        service._risk_gate.evaluate = _boom  # type: ignore[method-assign]
        result = service.execute_paper_plan(
            canonical_execute_request(envelope, authorization, key="predicate-not-gate"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        assert result.outcome is ExecutionCommandOutcome.ALLOW
        assert result.replayed is False
        assert session.scalars(select(LearningAttributionRecordRow)).one() is not None
    finally:
        session.close()


@requires_postgres
def test_canonical_fill_without_runtime_fails_closed() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:
        service = canonical_execution_service(session, runtime)
        result = service.execute_paper_plan(
            canonical_execute_request(envelope, authorization, key="fill-unbound"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        assert result.outcome is ExecutionCommandOutcome.ALLOW
        command_id = result.command_id
    finally:
        session.close()

    session = factory()
    try:
        bare = ExecutionService(session, phase8_settings(), AuditService(session))
        with pytest.raises(TradingPolicyError) as exc:
            bare.apply_paper_plan_fill(
                command_id=command_id,
                fill_quantity=Decimal("1"),
                fill_price=Decimal("100000"),
                source_identity="unbound-fill",
                occurred_at=EXECUTE_AT,
            )
        assert exc.value.details["reason"] == "canonical_runtime_unbound"
        session.rollback()
        assert session.scalar(select(func.count()).select_from(JournalLifecycleEvent)) == 1
        events = session.scalars(select(JournalLifecycleEvent)).all()
        assert all(item.event_type is not JournalLifecycleEventType.FILL for item in events)
    finally:
        session.close()


@requires_postgres
def test_fill_without_command_fails_closed() -> None:
    factory = _factory()
    session = factory()
    try:
        service = ExecutionService(
            session,
            phase8_settings(),
            AuditService(session),
            canonical_runtime=build_runtime(factory),
        )
        with pytest.raises(NotFoundError, match="Execution command not found"):
            service.apply_paper_plan_fill(
                command_id=uuid4(),
                fill_quantity=Decimal("1"),
                fill_price=Decimal("100000"),
                source_identity="missing-command",
                occurred_at=EXECUTE_AT,
            )
    finally:
        session.close()


@requires_postgres
def test_execution_receipt_command_org_mismatch_is_not_found() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:
        service = canonical_execution_service(session, runtime)
        result = service.execute_paper_plan(
            canonical_execute_request(envelope, authorization, key="receipt-org"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        reads = CanonicalReadService(session, runtime)
        with pytest.raises(NotFoundError):
            reads.get_execution_receipt(
                organization_id=uuid4(), receipt_id=result.receipt.receipt_id
            )
        visible = reads.get_execution_receipt(
            organization_id=ORG_ID, receipt_id=result.receipt.receipt_id
        )
        assert visible.receipt.command_id == result.command_id
    finally:
        session.close()


@requires_postgres
def test_http_replay_commits_without_double_usage() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    runtime = build_runtime(factory)
    session = factory()
    try:
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        service = canonical_execution_service(session, runtime)
        first = service.execute_paper_plan(
            canonical_execute_request(envelope, authorization, key="http-hardening-replay"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        assert first.outcome is ExecutionCommandOutcome.ALLOW
        command_id = first.command_id
    finally:
        session.close()

    settings = phase8_settings()
    app = create_app(settings)

    def _override() -> object:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_session] = _override
    token, _expires = create_access_token(
        user_id=USER_ID,
        organization_id=ORG_ID,
        email="hardening@example.com",
        settings=settings,
    )
    payload = {
        "account_id": str(envelope.plan.account_id),
        "authorization_id": str(authorization.authorization_id),
        "revision_id": str(envelope.plan.revision_id),
        "idempotency_key": "http-hardening-replay",
    }
    with TestClient(app) as client:
        app.state.canonical_runtime = build_runtime(factory)
        client.headers.update({"Authorization": f"Bearer {token}"})
        replay = client.post("/execution/paper-plan", json=payload)
        assert replay.status_code == 200
        body = replay.json()
        assert body["outcome"] == "ALLOW"
        assert body["replayed"] is True
        assert body["command_id"] == str(command_id)
        second = client.post("/execution/paper-plan", json=payload)
        assert second.status_code == 200
        assert second.json()["replayed"] is True
        learning = client.get(f"/canonical/learning/records/{envelope.lineage.candidate_id}")
        assert learning.status_code == 200
        candidate = client.get(f"/canonical/candidates/{envelope.lineage.candidate_id}")
        assert candidate.status_code == 200

    verify = factory()
    try:
        assert verify.scalar(select(func.count()).select_from(UsageEvent)) == 0
        assert verify.scalar(select(func.count()).select_from(LearningAttributionRecordRow)) == 1
        assert verify.scalar(select(func.count()).select_from(ExecutionCommand)) == 1
    finally:
        verify.close()
