"""Phase 1A slice 2 — READ_ONLY persistence firewall spy tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import PersistencePolicyError
from app.core.operation_policy import operation_scope
from app.core.persistence_firewall import install_persistence_firewall
from app.db.base import Base
from app.db.models import AuditLog, KillSwitchState, Organization, UsageEvent
from app.repositories.base import SQLAlchemyRepository
from app.schemas.agent import (
    Intent,
    IntentDecision,
    OperationClass,
    PrincipalRef,
    RequestedAction,
)
from app.schemas.common import ActorType, AuditEventType, AuditResult, CostSource, UsageStatus


class _KillSwitchRepo(SQLAlchemyRepository[KillSwitchState]):
    model = KillSwitchState


class _AuditRepo(SQLAlchemyRepository[AuditLog]):
    model = AuditLog


class _UsageRepo(SQLAlchemyRepository[UsageEvent]):
    model = UsageEvent


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    install_persistence_firewall()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as sess:
        org = Organization(id=uuid.uuid4(), name="phase1a-readonly")
        sess.add(org)
        sess.commit()
        yield sess
    engine.dispose()


def _read_only_decision() -> IntentDecision:
    return IntentDecision(
        intent=Intent.MARKET_ANALYSIS,
        operation_class=OperationClass.READ_ONLY,
        organization_id=uuid.uuid4(),
        principal=PrincipalRef(user_id=uuid.uuid4()),
        requested_action=RequestedAction.NONE,
    )


def test_readonly_forbidden_domain_writes_are_zero(session: Session) -> None:
    org = session.query(Organization).one()
    decision = _read_only_decision()
    writes_before = session.query(KillSwitchState).count()
    with operation_scope(decision), pytest.raises(PersistencePolicyError, match="READ_ONLY"):
        _KillSwitchRepo(session).add(
            KillSwitchState(organization_id=org.id, active=True, reason="should-not-write")
        )
    session.rollback()
    assert session.query(KillSwitchState).count() == writes_before


def test_readonly_allows_audit_and_usage_persistence(session: Session) -> None:
    decision = _read_only_decision()
    now = datetime.now(UTC)
    with operation_scope(decision):
        audit = _AuditRepo(session).add(
            AuditLog(
                actor="phase1a",
                actor_type=ActorType.SYSTEM,
                action=AuditEventType.TOOL_CALLED,
                resource_type="agent",
                result=AuditResult.SUCCESS,
                event_at=now,
            )
        )
        usage = _UsageRepo(session).add(
            UsageEvent(
                request_id="phase1a-usage",
                feature="agent_chat",
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                estimated_cost=Decimal("0"),
                cost_source=CostSource.UNAVAILABLE,
                event_at=now,
                status=UsageStatus.SUCCESS,
            )
        )
        session.commit()
    assert audit.id is not None
    assert usage.id is not None
    assert session.query(AuditLog).count() >= 1
    assert session.query(UsageEvent).count() >= 1
