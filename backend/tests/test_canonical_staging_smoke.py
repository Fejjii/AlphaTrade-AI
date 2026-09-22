"""Synthetic HTTP smoke for the canonical paper staging path.

Seeds Candidate/TradePlan via existing Phase 7/8 services (no HTTP mint, no
exchange credentials) then drives authentication, canonical reads, approval,
paper execution, journal, learning, kill switch, risk BLOCK, and cross-tenant
rejection over FastAPI.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.dependencies import (
    AuditServiceDep,
    CanonicalRuntimeDep,
    KillSwitchServiceDep,
    MarketDataServiceDep,
    RiskServiceDep,
    RiskSettingsServiceDep,
    SessionDep,
    SettingsDep,
    get_approval_service,
    get_execution_service,
)
from app.db.models import AccountRiskAccountingState, Membership, Organization, User
from app.db.session import get_session
from app.main import create_app
from app.providers.exchange.factory import resolve_exchange_execution_provider
from app.schemas.common import MembershipRole
from app.security.tokens import create_access_token
from app.services.approval_service import ApprovalService
from app.services.execution_claim import conservative_reservation
from app.services.execution_service import ExecutionService
from tests.support.phase6_fusion import ORG_ID, USER_ID
from tests.support.phase8_runtime import (
    APPROVE_AT,
    EXECUTE_AT,
    build_runtime,
    phase8_settings,
    prepared_authorized_canonical,
    prepared_unapproved_canonical,
)
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres


def _factory() -> sessionmaker[Session]:
    return phase7_plan_session_factory()


def _bind_session(factory: sessionmaker[Session]) -> object:
    def _override() -> Iterator[object]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    return _override


def _owner_client(factory: sessionmaker[Session]) -> TestClient:
    settings = phase8_settings()
    app = create_app(settings)
    app.dependency_overrides[get_session] = _bind_session(factory)

    def _approval(
        session: SessionDep,
        audit_service: AuditServiceDep,
        canonical_runtime: CanonicalRuntimeDep,
    ) -> ApprovalService:
        return ApprovalService(
            session,
            audit_service,
            clock=lambda: APPROVE_AT,
            plans=canonical_runtime.plans,
        )

    def _execution(
        session: SessionDep,
        settings_dep: SettingsDep,
        audit_service: AuditServiceDep,
        market_data_service: MarketDataServiceDep,
        risk_service: RiskServiceDep,
        risk_settings: RiskSettingsServiceDep,
        kill_switch: KillSwitchServiceDep,
        canonical_runtime: CanonicalRuntimeDep,
    ) -> ExecutionService:
        service = ExecutionService(
            session,
            settings_dep,
            audit_service,
            exchange_execution=resolve_exchange_execution_provider(settings_dep),
            risk_service=risk_service,
            risk_settings=risk_settings,
            market_data_service=market_data_service,
            kill_switch=kill_switch,
            canonical_runtime=canonical_runtime,
        )
        original = service.execute_paper_plan

        def _timed(
            request: object,
            *,
            hooks: object = None,
            clock: object = None,
        ) -> object:
            return original(request, hooks=hooks, clock=clock or (lambda: EXECUTE_AT))  # type: ignore[arg-type,misc]

        service.execute_paper_plan = _timed  # type: ignore[method-assign]
        return service

    app.dependency_overrides[get_approval_service] = _approval
    app.dependency_overrides[get_execution_service] = _execution
    token, _expires = create_access_token(
        user_id=USER_ID,
        organization_id=ORG_ID,
        email="canonical-smoke@example.com",
        settings=settings,
    )
    client = TestClient(app)
    client.__enter__()
    app.state.canonical_runtime = build_runtime(factory)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _other_tenant_token(factory: sessionmaker[Session]) -> tuple[object, object]:
    other_org = uuid4()
    other_user = uuid4()
    session = factory()
    try:
        session.add(Organization(id=other_org, name=f"Smoke other {other_org}"))
        session.add(
            User(
                id=other_user,
                email=f"smoke-other-{other_user}@example.com",
                hashed_password="not-a-real-hash",
            )
        )
        session.flush()
        session.add(
            Membership(
                user_id=other_user,
                organization_id=other_org,
                role=MembershipRole.OWNER,
            )
        )
        session.commit()
    finally:
        session.close()
    token, _expires = create_access_token(
        user_id=other_user,
        organization_id=other_org,
        email=f"smoke-other-{other_user}@example.com",
        settings=phase8_settings(),
    )
    return token, other_org


@requires_postgres
def test_canonical_http_smoke_auth_reads_approval_execution_journal_learning() -> None:
    factory = _factory()
    world, envelope = prepared_unapproved_canonical(factory)
    client = _owner_client(factory)
    try:
        health = client.get("/health")
        assert health.status_code == 200
        posture = health.json()
        assert posture["execution_mode"] == "paper"
        assert posture["real_trading_enabled"] is False
        assert posture["exchange_mode"] == "paper_internal"
        assert posture["market_watcher_enabled"] is False
        assert posture["watcher_orchestration_enabled"] is False
        assert posture["telegram_alerts_enabled"] is False
        assert posture["telegram_interaction_enabled"] is False

        unauth = client.get("/canonical/candidates", headers={"Authorization": ""})
        assert unauth.status_code == 401
        unauth_exec = client.post(
            "/execution/paper-plan",
            headers={"Authorization": ""},
            json={
                "account_id": str(envelope.plan.account_id),
                "authorization_id": str(uuid4()),
                "revision_id": str(envelope.plan.revision_id),
                "idempotency_key": "unauth",
            },
        )
        assert unauth_exec.status_code == 401

        candidates = client.get("/canonical/candidates")
        assert candidates.status_code == 200
        listed = candidates.json()
        assert listed["total"] == 1
        candidate_id = listed["items"][0]["candidate"]["candidate_id"]
        assert candidate_id == str(world.candidate.candidate_id)

        detail = client.get(f"/canonical/candidates/{candidate_id}")
        assert detail.status_code == 200
        eligibility = client.get(f"/canonical/candidates/{candidate_id}/eligibility")
        assert eligibility.status_code == 200
        assert eligibility.json()["evaluation"]["live_executable"] is False
        assessment = client.get(f"/canonical/setup-assessments/{world.candidate.assessment_id}")
        assert assessment.status_code == 200

        blocked_proposal = client.get(f"/proposals/{envelope.plan.plan_id}")
        assert blocked_proposal.status_code in {400, 403, 404, 409, 422}

        created = client.post(
            f"/approvals/plan-revisions/{envelope.plan.revision_id}",
            json={"reason": "synthetic staging smoke"},
        )
        assert created.status_code == 200, created.text
        approval_id = created.json()["id"]
        decided = client.post(f"/approvals/{approval_id}/approve", json={})
        assert decided.status_code == 200, decided.text
        authorization = decided.json()["authorization"]
        assert authorization is not None
        authorization_id = authorization["authorization_id"]

        forbidden = client.post(
            "/execution/paper-plan",
            json={
                "account_id": str(envelope.plan.account_id),
                "authorization_id": authorization_id,
                "revision_id": str(envelope.plan.revision_id),
                "idempotency_key": "canonical-smoke-exec",
                "side": "sell",
            },
        )
        assert forbidden.status_code == 422

        executed = client.post(
            "/execution/paper-plan",
            json={
                "account_id": str(envelope.plan.account_id),
                "authorization_id": authorization_id,
                "revision_id": str(envelope.plan.revision_id),
                "idempotency_key": "canonical-smoke-exec",
            },
        )
        assert executed.status_code == 200, executed.text
        body = executed.json()
        assert body["outcome"] == "ALLOW"
        assert body["replayed"] is False
        receipt_id = body["receipt"]["receipt_id"]

        receipt = client.get(f"/canonical/executions/{receipt_id}")
        assert receipt.status_code == 200
        trades = client.get("/journal/trades")
        assert trades.status_code == 200
        assert trades.json()["total"] >= 1
        learning = client.get(f"/canonical/learning/records/{candidate_id}")
        assert learning.status_code == 200
        assert learning.json()["record"]["facts"]["strategy_pattern"]["plan_approved"] is True
        stats = client.get("/canonical/learning/strategy-stats")
        assert stats.status_code == 200
        assert stats.json()["snapshot"]["human_vs_system"]["human_approvals"] == 1
        evaluation = client.get("/canonical/paper-evaluation/summary")
        assert evaluation.status_code == 200
        evaluation_body = evaluation.json()
        assert evaluation_body["watcher_activated"] is False
        assert evaluation_body["live_executable"] is False
        assert evaluation_body["summary"]["authority"] == "paper_evaluation_measurement"
        assert evaluation_body["summary"]["facts"]["live_executable"] is False
        assert evaluation_body["summary"]["facts"]["watcher_orchestration_enabled"] is False
        assert all(
            item["activate"] is False and item["auto_activate"] is False
            for item in evaluation_body["summary"]["refinements"]
        )

        risk_block = client.post(
            "/risk/check",
            json={
                "symbol": "BTCUSDT",
                "direction": "long",
                "entry_price": "60000",
                "position_size": "0.005",
                "leverage": "3",
                "account_equity": "10000",
            },
        )
        assert risk_block.status_code == 200
        assert risk_block.json()["action"] == "block"

        other_token, _other_org = _other_tenant_token(factory)
        hidden = client.get(
            f"/canonical/candidates/{candidate_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert hidden.status_code == 404
        hidden_learning = client.get(
            f"/canonical/learning/records/{candidate_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert hidden_learning.status_code == 404
        other_list = client.get(
            "/canonical/candidates",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert other_list.status_code == 200
        assert other_list.json()["total"] == 0
    finally:
        client.__exit__(None, None, None)


@requires_postgres
def test_canonical_http_smoke_kill_switch_blocks_paper_plan() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    session = factory()
    try:
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        session.commit()
    finally:
        session.close()
    client = _owner_client(factory)
    try:
        status = client.get("/risk/kill-switch")
        assert status.status_code == 200
        assert status.json()["execution_blocked"] is False
        activated = client.post(
            "/risk/kill-switch/activate",
            json={"confirm": True, "reason": "synthetic smoke halt"},
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["execution_blocked"] is True
        blocked = client.post(
            "/execution/paper-plan",
            json={
                "account_id": str(envelope.plan.account_id),
                "authorization_id": str(authorization.authorization_id),
                "revision_id": str(envelope.plan.revision_id),
                "idempotency_key": "canonical-smoke-kill",
            },
        )
        assert blocked.status_code == 200, blocked.text
        body = blocked.json()
        assert body["outcome"] == "BLOCKED"
        assert body["blocked_reason_code"] == "safety_epoch_blocking"
        deactivated = client.post(
            "/risk/kill-switch/deactivate",
            json={"confirm": True, "reason": "restore after smoke"},
        )
        assert deactivated.status_code == 200
    finally:
        client.__exit__(None, None, None)


@requires_postgres
def test_canonical_http_smoke_risk_capacity_blocks_paper_plan() -> None:
    factory = _factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    intent = conservative_reservation(envelope.plan)
    session = factory()
    try:
        session.add(Membership(user_id=USER_ID, organization_id=ORG_ID, role=MembershipRole.OWNER))
        row = session.scalar(
            select(AccountRiskAccountingState).where(
                AccountRiskAccountingState.account_id == envelope.plan.account_id
            )
        )
        assert row is not None
        row.max_notional = intent.pending_notional / Decimal("2")
        row.max_symbol_notional = intent.pending_notional
        session.commit()
    finally:
        session.close()
    client = _owner_client(factory)
    try:
        blocked = client.post(
            "/execution/paper-plan",
            json={
                "account_id": str(envelope.plan.account_id),
                "authorization_id": str(authorization.authorization_id),
                "revision_id": str(envelope.plan.revision_id),
                "idempotency_key": "canonical-smoke-risk",
            },
        )
        assert blocked.status_code == 200, blocked.text
        body = blocked.json()
        assert body["outcome"] == "BLOCKED"
        assert body["blocked_reason_code"] == "insufficient_total_exposure"
        missing = client.get(f"/canonical/learning/records/{envelope.lineage.candidate_id}")
        assert missing.status_code == 404
    finally:
        client.__exit__(None, None, None)
