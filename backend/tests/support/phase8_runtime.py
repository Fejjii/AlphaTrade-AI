"""Helpers for Phase 8 canonical PAPER runtime execution tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import AccountRiskAccountingState
from app.runtime.canonical import ProductionCanonicalRuntime, build_production_canonical_runtime
from app.schemas.approval import ApprovalAuthorization, ApprovalDecisionRequest
from app.schemas.canonical_trade_plan import CanonicalTradePlanRevision
from app.schemas.common import ApprovalAction
from app.schemas.execution_protocol import ExecutePaperPlanRequest
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.canonical_trade_plan import CanonicalTradePlanService
from app.services.execution_service import ExecutionService
from app.signal_fusion.memory import FrozenClock
from tests.support.phase1_plan_fixtures import paper_settings
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import VALID_UNTIL
from tests.support.phase7_postgres import postgres_plan_world
from tests.support.phase7_trade_plan import CanonicalPlanWorld, plan_command
from tests.support.postgres_persistence import POSTGRES_URL

APPROVE_AT = EVALUATED_AT + timedelta(minutes=1)
EXECUTE_AT = EVALUATED_AT + timedelta(minutes=2)
AUTH_EXPIRES_AT = EVALUATED_AT + timedelta(minutes=5)
AFTER_AUTH_EXPIRY = EVALUATED_AT + timedelta(minutes=6)
AFTER_PLAN_EXPIRY = VALID_UNTIL + timedelta(seconds=1)


def phase8_settings() -> Settings:
    return paper_settings(database_url=POSTGRES_URL)


def build_runtime(factory: sessionmaker[Session]) -> ProductionCanonicalRuntime:
    return build_production_canonical_runtime(
        factory,
        settings=phase8_settings(),
        clock=FrozenClock(EVALUATED_AT),
    )


def authorize_canonical_plan(
    session: Session,
    envelope: CanonicalTradePlanRevision,
    *,
    plans: CanonicalTradePlanService,
    clock: datetime = APPROVE_AT,
    authorization_expires_at: datetime | None = None,
) -> ApprovalAuthorization:
    service = ApprovalService(
        session,
        AuditService(session),
        clock=lambda: clock,
        plans=plans,
    )
    approval = service.create_for_plan_revision(
        revision_id=envelope.plan.revision_id,
        organization_id=envelope.plan.organization_id,
        user_id=envelope.plan.user_id,
        authorization_expires_at=authorization_expires_at,
    )
    decided = service.decide(
        approval.id,
        ApprovalDecisionRequest(action=ApprovalAction.APPROVE),
        principal_organization_id=envelope.plan.organization_id,
        principal_user_id=envelope.plan.user_id,
    )
    assert decided.authorization is not None
    return decided.authorization


def seed_paper_capacity(
    session: Session,
    envelope: CanonicalTradePlanRevision,
    *,
    max_notional: Decimal = Decimal("1000000000"),
) -> None:
    session.add(
        AccountRiskAccountingState(
            organization_id=envelope.plan.organization_id,
            account_id=envelope.plan.account_id,
            reserved_notional=Decimal("0"),
            reserved_daily_loss=Decimal("0"),
            reserved_trade_slots=0,
            actual_notional=Decimal("0"),
            actual_daily_loss=Decimal("0"),
            actual_trade_count=0,
            symbol_reserved={},
            symbol_actual={},
            max_notional=max_notional,
            max_daily_loss=Decimal("1000000"),
            max_trade_slots=20,
            max_symbol_notional=max_notional,
            daily_locked=False,
            exposure_unit="USDT",
            version=1,
        )
    )


def prepared_authorized_canonical(
    factory: sessionmaker[Session],
    *,
    authorization_expires_at: datetime | None = None,
) -> tuple[CanonicalPlanWorld, CanonicalTradePlanRevision, ApprovalAuthorization]:
    world = postgres_plan_world(factory)
    envelope = world.plans.create(plan_command(world))
    session = factory()
    try:
        authorization = authorize_canonical_plan(
            session,
            envelope,
            plans=world.plans,
            authorization_expires_at=authorization_expires_at,
        )
        seed_paper_capacity(session, envelope)
        session.commit()
    finally:
        session.close()
    return world, envelope, authorization


def canonical_execute_request(
    envelope: CanonicalTradePlanRevision,
    authorization: ApprovalAuthorization,
    *,
    key: str,
) -> ExecutePaperPlanRequest:
    return ExecutePaperPlanRequest(
        organization_id=envelope.plan.organization_id,
        user_id=envelope.plan.user_id,
        account_id=envelope.plan.account_id,
        authorization_id=authorization.authorization_id,
        revision_id=envelope.plan.revision_id,
        idempotency_key=key,
    )


def canonical_execution_service(
    session: Session,
    runtime: ProductionCanonicalRuntime,
) -> ExecutionService:
    return ExecutionService(
        session,
        phase8_settings(),
        AuditService(session),
        canonical_runtime=runtime,
    )
