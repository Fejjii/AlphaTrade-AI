"""Builders for Phase 7 learning-attribution tests."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ExecutionAccount, Membership, Organization, User
from app.learning_attribution.contracts import (
    AttributionCommand,
    LearningVenueMode,
    LineageSnapshot,
    TradePlanLineageRef,
)
from app.learning_attribution.memory import InMemoryAttributionStore
from app.learning_attribution.ports import AttributionStore
from app.market_contracts.first_slice import first_slice_identity
from app.schemas.common import JournalLifecycleEventType, MembershipRole, Timeframe, TradeDirection
from app.schemas.journal_lifecycle import JournalLifecycleEventInput
from app.schemas.trade_plan import AccountMode, ExecutionMode
from app.services.audit_service import AuditService
from app.services.journal_lifecycle_learning import JournalLifecycleLearningService
from app.signal_fusion.candidate import build_confirmed_candidate
from app.signal_fusion.enums import SetupAssessmentState
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    ASSESSMENT_ID,
    CANDIDATE_ID,
    CORRELATION_A,
    ORG_ID,
    STRATEGY_VERSION_ID,
    USER_ID,
    VALID_UNTIL,
    executable_setup,
    make_assessment,
    make_evidence_window,
)

OTHER_ORG = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa0")
OTHER_USER = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb0")
OTHER_ACCOUNT = UUID("cccccccc-cccc-cccc-cccc-ccccccccccc0")
PLAN_REVISION_ID = UUID("abcdef12-3456-7890-abcd-ef1234567890")
PLAN_CONTENT_HASH = "ab" * 32


def sqlite_factory() -> sessionmaker[Session]:
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
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def attribution_sessions() -> Iterator[sessionmaker[Session]]:
    maker = sqlite_factory()
    with maker() as session:
        session.add_all(
            [
                Organization(id=ORG_ID, name="Attribution Org"),
                Organization(id=OTHER_ORG, name="Other Org"),
                User(id=USER_ID, email="attr@test.example", hashed_password="not-a-real-hash"),
                User(id=OTHER_USER, email="other@test.example", hashed_password="not-a-real-hash"),
            ]
        )
        session.flush()
        session.add_all(
            [
                Membership(organization_id=ORG_ID, user_id=USER_ID, role=MembershipRole.TRADER),
                Membership(
                    organization_id=OTHER_ORG, user_id=OTHER_USER, role=MembershipRole.TRADER
                ),
                ExecutionAccount(
                    id=ACCOUNT_ID,
                    organization_id=ORG_ID,
                    user_id=USER_ID,
                    name="Paper A",
                    execution_mode=ExecutionMode.PAPER,
                    account_mode=AccountMode.NET,
                ),
                ExecutionAccount(
                    id=OTHER_ACCOUNT,
                    organization_id=OTHER_ORG,
                    user_id=OTHER_USER,
                    name="Paper B",
                    execution_mode=ExecutionMode.PAPER,
                    account_mode=AccountMode.NET,
                ),
            ]
        )
        session.commit()
    yield maker


def make_lineage(
    *,
    candidate_id: UUID = CANDIDATE_ID,
    organization_id: UUID = ORG_ID,
    assessment_state: SetupAssessmentState = SetupAssessmentState.CONFIRMED_SETUP,
    include_plan: bool = False,
    execution_lifecycle_id: UUID | None = None,
    account_id: UUID = ACCOUNT_ID,
) -> LineageSnapshot:
    window = make_evidence_window()
    assessment = make_assessment(
        window,
        state=assessment_state,
        organization_id=organization_id,
        assessment_id=ASSESSMENT_ID if candidate_id == CANDIDATE_ID else uuid4(),
    )
    identity = first_slice_identity(timeframe=Timeframe.M15, replay=True)
    candidate = build_confirmed_candidate(
        candidate_id=candidate_id,
        organization_id=organization_id,
        strategy_version_id=STRATEGY_VERSION_ID,
        executable_setup=executable_setup(),
        fusion_policy_version=window.fusion_policy_version,
        direction=TradeDirection.SHORT,
        assessment_id=assessment.assessment_id,
        evidence_window_hash=window.content_hash,
        evidence_identity=identity,
        evidence_venue=identity.venue,
        evidence_market=identity.market_type,
        evidence_instrument=identity.instrument.instrument_id,
        timeframe=Timeframe.M15,
        created_at=EVALUATED_AT,
        valid_until=VALID_UNTIL,
        idempotency_key=f"candidate-{candidate_id}",
        correlation_id=CORRELATION_A,
    )
    plan = None
    if include_plan:
        plan = TradePlanLineageRef(
            revision_id=PLAN_REVISION_ID,
            content_hash=PLAN_CONTENT_HASH,
            candidate_id=candidate.candidate_id,
            organization_id=organization_id,
            account_id=account_id,
            strategy_version_id=candidate.strategy_version_id,
            setup_definition_id=candidate.setup_definition_id,
        )
    return LineageSnapshot(
        assessment=assessment,
        candidate=candidate,
        account_id=account_id,
        execution_lifecycle_id=execution_lifecycle_id,
        trade_plan=plan,
    )


def instrument_payload(**extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": TradeDirection.SHORT.value,
        "thesis": "Bearish sweep at 4h resistance.",
        "planned_entry_price": "64000",
        "planned_stop_price": "64640",
    }
    payload.update(extra)
    return payload


def lifecycle_event(
    event_type: JournalLifecycleEventType,
    *,
    source_event_id: str,
    execution_lifecycle_id: UUID | None = None,
    account_id: UUID = ACCOUNT_ID,
    payload: dict[str, object] | None = None,
) -> JournalLifecycleEventInput:
    return JournalLifecycleEventInput(
        event_type=event_type,
        execution_lifecycle_id=execution_lifecycle_id,
        source_system="paper_internal",
        source_aggregate="execution-lifecycle",
        source_event_id=source_event_id,
        source_event_version=1,
        supersession=0,
        account_id=account_id,
        payload=payload or {},
    )


def command_for(
    event: JournalLifecycleEventInput,
    lineage: LineageSnapshot,
    *,
    organization_id: UUID = ORG_ID,
    user_id: UUID = USER_ID,
    narrative: str | None = None,
    learning_venue_mode: LearningVenueMode = LearningVenueMode.PAPER_INTERNAL,
) -> AttributionCommand:
    return AttributionCommand(
        organization_id=organization_id,
        user_id=user_id,
        event=event,
        lineage=lineage,
        narrative_explanation=narrative,
        learning_venue_mode=learning_venue_mode,
    )


def learning_service(
    session: Session, store: AttributionStore | None = None
) -> JournalLifecycleLearningService:
    return JournalLifecycleLearningService(
        session,
        AuditService(session, strict_mode=True),
        store=store if store is not None else InMemoryAttributionStore(),
    )
