"""Phase 4 — canonical JournalTrade uniqueness, venue facts, legacy parity."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import PersistencePolicyError
from app.core.operation_policy import operation_scope
from app.core.persistence_firewall import install_persistence_firewall
from app.db.base import Base
from app.db.journal_immutability import JournalHistoryImmutabilityError
from app.db.models import (
    JournalLifecycleEvent,
    JournalProjectionReceipt,
    JournalTrade,
    JournalTradeObservation,
    JournalTradeVenueCorrection,
    Membership,
    Organization,
    TradeJournal,
    User,
    UserStrategyVersion,
)
from app.schemas.agent import Intent, IntentDecision, OperationClass, PrincipalRef, RequestedAction
from app.schemas.common import (
    JournalLifecycleEventType,
    JournalObservationCategory,
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    StrategyId,
    TradeDirection,
    TradeResult,
)
from app.schemas.journal_lifecycle import JournalLifecycleEventInput
from app.schemas.journal_trades import JournalTradeUpdate
from app.schemas.rag import IngestDocumentRequest, IngestDocumentResponse
from app.services.audit_service import AuditService
from app.services.human_vs_system_service import HumanVsSystemService
from app.services.journal_backfill_service import JournalBackfillService
from app.services.journal_lifecycle_projector import JournalLifecycleProjector
from app.services.journal_rag_sync_service import JournalRagSyncService
from app.services.journal_trade_service import JournalTradeService, VenueFactImmutableError

ORG_A = uuid.UUID("00000000-0000-0000-0000-00000000d001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-00000000d002")
USER_A = uuid.UUID("00000000-0000-0000-0000-00000000d011")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000d012")


class _FakeRag:
    def __init__(self) -> None:
        self.by_uri: dict[str, IngestDocumentRequest] = {}

    def upsert_linked_document(self, request: IngestDocumentRequest) -> IngestDocumentResponse:
        assert request.source_uri is not None
        self.by_uri[request.source_uri] = request
        return IngestDocumentResponse(
            document_id=uuid.uuid4(),
            source_hash="a" * 64,
            chunk_count=1,
            version=1,
        )


class _FakeSettings:
    journal_rag_sync_enabled = True


def _engine() -> sessionmaker[Session]:
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
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    maker = _engine()
    with maker() as session:
        session.add_all(
            [
                Organization(id=ORG_A, name="Phase4 Org A"),
                Organization(id=ORG_B, name="Phase4 Org B"),
                User(id=USER_A, email="phase4-a@test.example", hashed_password="not-a-real-hash"),
                User(id=USER_B, email="phase4-b@test.example", hashed_password="not-a-real-hash"),
            ]
        )
        session.flush()
        session.add_all(
            [
                Membership(organization_id=ORG_A, user_id=USER_A, role=MembershipRole.TRADER),
                Membership(organization_id=ORG_B, user_id=USER_B, role=MembershipRole.TRADER),
            ]
        )
        session.commit()
    yield maker


def _audit(session: Session) -> AuditService:
    return AuditService(session, strict_mode=True)


def _projector(session: Session) -> JournalLifecycleProjector:
    return JournalLifecycleProjector(session, _audit(session))


def _event(
    event_type: JournalLifecycleEventType,
    *,
    source_event_id: str,
    execution_lifecycle_id: uuid.UUID | None = None,
    source_aggregate: str = "account-a",
    payload: dict[str, object] | None = None,
) -> JournalLifecycleEventInput:
    return JournalLifecycleEventInput(
        event_type=event_type,
        execution_lifecycle_id=execution_lifecycle_id,
        source_system="paper_internal",
        source_aggregate=source_aggregate,
        source_event_id=source_event_id,
        source_event_version=1,
        payload=payload or {},
    )


def _instrument_payload(**extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": TradeDirection.SHORT.value,
        "thesis": "Bearish sweep at 4h resistance.",
    }
    payload.update(extra)
    return payload


def test_candidate_creates_no_journal_trade(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        result = _projector(session).project(
            _event(JournalLifecycleEventType.CANDIDATE_CONFIRMED, source_event_id="cand-1"),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert result.journal_trade_id is None
        assert result.skipped_reason == "non_creating_lifecycle_event"
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0
        assert session.scalar(select(func.count()).select_from(JournalLifecycleEvent)) == 1


def test_reject_creates_no_journal_trade(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        _projector(session).project(
            _event(JournalLifecycleEventType.REJECT, source_event_id="rej-1"),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0


def test_skip_creates_no_journal_trade(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        _projector(session).project(
            _event(JournalLifecycleEventType.SKIP, source_event_id="skip-1"),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0


def test_one_execution_lifecycle_creates_exactly_one_journal_trade(
    factory: sessionmaker[Session],
) -> None:
    lifecycle_id = uuid.uuid4()
    with factory() as session:
        projector = _projector(session)
        first = projector.project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-1",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        second = projector.project(
            _event(
                JournalLifecycleEventType.FILL,
                source_event_id="fill-1",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(entry_price="64000", size="0.1"),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert first.created_journal_trade is True
        assert second.created_journal_trade is False
        assert first.journal_trade_id == second.journal_trade_id
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1
        trade = session.scalars(select(JournalTrade)).one()
        assert trade.execution_lifecycle_id == lifecycle_id
        assert trade.entry_price == Decimal("64000")
        assert trade.status is JournalTradeStatus.OPEN


def test_same_source_event_replay_is_idempotent(factory: sessionmaker[Session]) -> None:
    lifecycle_id = uuid.uuid4()
    event = _event(
        JournalLifecycleEventType.APPROVED_PLAN,
        source_event_id="plan-replay",
        execution_lifecycle_id=lifecycle_id,
        payload=_instrument_payload(),
    )
    with factory() as session:
        projector = _projector(session)
        first = projector.project(event, organization_id=ORG_A, user_id=USER_A)
        replay = projector.project(event, organization_id=ORG_A, user_id=USER_A)
        session.commit()
        assert first.created_journal_trade is True
        assert replay.replayed is True
        assert replay.journal_trade_id == first.journal_trade_id
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1
        assert session.scalar(select(func.count()).select_from(JournalProjectionReceipt)) == 1


def test_same_source_identity_isolated_across_accounts(factory: sessionmaker[Session]) -> None:
    lifecycle_a = uuid.uuid4()
    lifecycle_b = uuid.uuid4()
    with factory() as session:
        projector = _projector(session)
        a = projector.project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="shared-event",
                execution_lifecycle_id=lifecycle_a,
                source_aggregate="account-a",
                payload=_instrument_payload(),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        b = projector.project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="shared-event",
                execution_lifecycle_id=lifecycle_b,
                source_aggregate="account-b",
                payload=_instrument_payload(),
            ),
            organization_id=ORG_B,
            user_id=USER_B,
        )
        session.commit()
        assert a.journal_trade_id != b.journal_trade_id
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 2


def test_database_uniqueness_on_execution_lifecycle(factory: sessionmaker[Session]) -> None:
    lifecycle_id = uuid.uuid4()
    with factory() as session:
        session.add(
            JournalTrade(
                organization_id=ORG_A,
                user_id=USER_A,
                source=JournalTradeSource.PAPER_EXECUTION,
                symbol="BTCUSDT",
                timeframe="15m",
                direction=TradeDirection.SHORT,
                execution_lifecycle_id=lifecycle_id,
                tags=[],
                planned_targets=[],
            )
        )
        session.flush()
        session.add(
            JournalTrade(
                organization_id=ORG_A,
                user_id=USER_A,
                source=JournalTradeSource.PAPER_EXECUTION,
                symbol="BTCUSDT",
                timeframe="15m",
                direction=TradeDirection.SHORT,
                execution_lifecycle_id=lifecycle_id,
                tags=[],
                planned_targets=[],
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_concurrent_lifecycle_events_converge(factory: sessionmaker[Session]) -> None:
    """Plan, fill, and close for one lifecycle resolve a single JournalTrade."""
    lifecycle_id = uuid.uuid4()
    with factory() as session:
        projector = _projector(session)
        plan = projector.project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-c",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        fill = projector.project(
            _event(
                JournalLifecycleEventType.FILL,
                source_event_id="fill-c",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(entry_price="64000", size="0.2"),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        close = projector.project(
            _event(
                JournalLifecycleEventType.CLOSE,
                source_event_id="close-c",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(
                    exit_price="63000",
                    net_pnl="200",
                    result=TradeResult.WIN.value,
                ),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert plan.journal_trade_id == fill.journal_trade_id == close.journal_trade_id
        trades = list(session.scalars(select(JournalTrade)).all())
        assert len(trades) == 1
        assert trades[0].execution_lifecycle_id == lifecycle_id
        assert trades[0].entry_price == Decimal("64000")
        assert trades[0].exit_price == Decimal("63000")
        assert trades[0].status is JournalTradeStatus.CLOSED


def test_reflective_edit_cannot_alter_venue_facts(factory: sessionmaker[Session]) -> None:
    lifecycle_id = uuid.uuid4()
    with factory() as session:
        result = _projector(session).project(
            _event(
                JournalLifecycleEventType.FILL,
                source_event_id="fill-lock",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(entry_price="64000", size="0.1"),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert result.journal_trade_id is not None
        service = JournalTradeService(session, _audit(session))
        updated = service.update(
            result.journal_trade_id,
            JournalTradeUpdate(notes="felt rushed"),
            organization_id=ORG_A,
        )
        assert updated.notes == "felt rushed"
        assert updated.entry_price == Decimal("64000")
        with pytest.raises(VenueFactImmutableError):
            service.update(
                result.journal_trade_id,
                JournalTradeUpdate(entry_price=Decimal("1")),
                organization_id=ORG_A,
            )
        session.commit()
        trade = session.get(JournalTrade, result.journal_trade_id)
        assert trade is not None
        assert trade.entry_price == Decimal("64000")


def test_manual_trade_without_lifecycle_still_allows_venue_edit(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        row = JournalTrade(
            organization_id=ORG_A,
            user_id=USER_A,
            source=JournalTradeSource.MANUAL,
            symbol="ETHUSDT",
            timeframe="1h",
            direction=TradeDirection.LONG,
            tags=[],
            planned_targets=[],
        )
        session.add(row)
        session.commit()
        service = JournalTradeService(session, _audit(session))
        updated = service.update(
            row.id,
            JournalTradeUpdate(entry_price=Decimal("3000"), fees=Decimal("1.5")),
            organization_id=ORG_A,
        )
        assert updated.entry_price == Decimal("3000")
        assert updated.fees == Decimal("1.5")


def test_authoritative_correction_is_append_only(factory: sessionmaker[Session]) -> None:
    lifecycle_id = uuid.uuid4()
    with factory() as session:
        result = _projector(session).project(
            _event(
                JournalLifecycleEventType.FILL,
                source_event_id="fill-correct",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(entry_price="64000", fees="2"),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert result.journal_trade_id is not None
        service = JournalTradeService(session, _audit(session))
        service.correct_venue_facts(
            result.journal_trade_id,
            organization_id=ORG_A,
            actor_user_id=USER_A,
            reason="Venue fill restatement",
            fields={"entry_price": Decimal("63950"), "fees": Decimal("2.25")},
        )
        session.commit()
        trade = session.get(JournalTrade, result.journal_trade_id)
        assert trade is not None
        assert trade.entry_price == Decimal("63950")
        corrections = list(session.scalars(select(JournalTradeVenueCorrection)).all())
        assert len(corrections) == 2
        first = corrections[0]
        with pytest.raises(JournalHistoryImmutabilityError):
            first.reason = "rewrite history"
            session.flush()


def test_legacy_migration_dry_run_and_apply(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        entry = TradeJournal(
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="BTCUSDT",
            timeframe="15m",
            direction=TradeDirection.SHORT,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            entry_rationale="Sweep exhaustion",
            exit_rationale="Target hit",
            emotions=["calm"],
            mistakes=["late entry"],
            lessons="Wait for close.",
            improvement_rule="Only after 15m confirmation.",
            result=TradeResult.WIN,
            pnl=Decimal("120"),
            tags=["discipline"],
            screenshot_refs=["https://img.example/sweep.png"],
        )
        session.add(entry)
        session.commit()
        legacy_id = entry.id

    with factory() as session:
        service = JournalBackfillService(session, _audit(session))
        dry = service.backfill(organization_id=ORG_A, dry_run=True)
        session.rollback()
        assert dry.created == 1
        assert session.scalars(select(JournalTrade)).all() == []

        applied = service.backfill(organization_id=ORG_A, dry_run=False)
        session.commit()
        assert applied.created == 1
        replay = service.backfill(organization_id=ORG_A, dry_run=False)
        session.commit()
        assert replay.created == 0
        assert replay.skipped_existing == 1
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1
        assert session.scalar(select(func.count()).select_from(TradeJournal)) == 1

        parity = service.parity_report(organization_id=ORG_A)
        assert parity.row_count_parity is True
        assert parity.emotion_parity is True
        assert parity.mistake_parity is True
        assert parity.attachment_parity is True

        trade = session.scalars(select(JournalTrade)).one()
        assert trade.linked_journal_entry_id == legacy_id
        observations = list(session.scalars(select(JournalTradeObservation)).all())
        categories = {obs.category for obs in observations}
        assert JournalObservationCategory.EMOTIONAL in categories
        assert JournalObservationCategory.MISTAKE in categories
        assert JournalObservationCategory.LESSON in categories
        assert session.scalar(select(func.count()).select_from(UserStrategyVersion)) == 0


def test_human_vs_system_parity_and_legacy_read(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        entry = TradeJournal(
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TradeDirection.LONG,
            entry_rationale="Followed plan",
            exit_rationale="Closed early",
            emotions=["fomo"],
            mistakes=["early exit"],
            lessons="Hold to invalidation.",
            result=TradeResult.WIN,
            pnl=Decimal("50"),
        )
        session.add(entry)
        session.commit()
        legacy_id = entry.id
        JournalBackfillService(session, _audit(session)).backfill(
            organization_id=ORG_A, dry_run=False
        )
        session.commit()
        trade = session.scalars(select(JournalTrade)).one()
        hvs = HumanVsSystemService(session)
        via_legacy = hvs.compare(legacy_id, organization_id=ORG_A, user_id=USER_A)
        via_canonical = hvs.compare(trade.id, organization_id=ORG_A, user_id=USER_A)
        assert via_legacy.compatibility_fallback is False
        assert via_canonical.compatibility_fallback is False
        assert via_legacy.canonical_journal_trade_id == trade.id
        assert via_canonical.canonical_journal_trade_id == trade.id
        assert via_legacy.emotion_tags == via_canonical.emotion_tags
        assert via_legacy.plan_adherence_score == via_canonical.plan_adherence_score
        leftover = session.get(TradeJournal, legacy_id)
        assert leftover is not None


def test_rag_lineage_parity(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        entry = TradeJournal(
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TradeDirection.LONG,
            entry_rationale="Lineage trade",
            emotions=["calm"],
            result=TradeResult.OPEN,
        )
        session.add(entry)
        session.commit()
        JournalBackfillService(session, _audit(session)).backfill(
            organization_id=ORG_A, dry_run=False
        )
        session.commit()
        trade = session.scalars(select(JournalTrade)).one()
        observations = list(session.scalars(select(JournalTradeObservation)).all())
        rag = _FakeRag()
        sync = JournalRagSyncService(rag, _FakeSettings())  # type: ignore[arg-type]
        ids = sync.sync_journal_trade(trade, observations=observations)
        assert len(ids) == 2
        assert f"journal-trade://{trade.id}" in rag.by_uri
        assert f"journal://{entry.id}" in rag.by_uri
        assert "Lineage trade" in (rag.by_uri[f"journal-trade://{trade.id}"].text)


def test_read_only_cannot_project(factory: sessionmaker[Session]) -> None:
    decision = IntentDecision(
        intent=Intent.MARKET_ANALYSIS,
        operation_class=OperationClass.READ_ONLY,
        organization_id=ORG_A,
        principal=PrincipalRef(user_id=USER_A),
        requested_action=RequestedAction.NONE,
    )
    with (
        factory() as session,
        operation_scope(decision),
        pytest.raises(PersistencePolicyError),
    ):
        _projector(session).project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="ro-1",
                execution_lifecycle_id=uuid.uuid4(),
                payload=_instrument_payload(),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )


def test_approved_plan_without_lifecycle_creates_no_trade(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        result = _projector(session).project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-no-claim",
                payload=_instrument_payload(),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert result.journal_trade_id is None
        assert result.skipped_reason == "missing_execution_lifecycle"
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0


def test_unresolved_reconciliation_does_not_finalize(factory: sessionmaker[Session]) -> None:
    lifecycle_id = uuid.uuid4()
    with factory() as session:
        projector = _projector(session)
        projector.project(
            _event(
                JournalLifecycleEventType.APPROVED_PLAN,
                source_event_id="plan-recon",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        closed = projector.project(
            _event(
                JournalLifecycleEventType.CLOSE,
                source_event_id="close-hold",
                execution_lifecycle_id=lifecycle_id,
                payload=_instrument_payload(
                    reconciliation_status="RECONCILIATION_REQUIRED",
                    exit_price="63000",
                ),
            ),
            organization_id=ORG_A,
            user_id=USER_A,
        )
        session.commit()
        assert closed.skipped_reason == "unresolved_reconciliation"
        trade = session.scalars(select(JournalTrade)).one()
        assert trade.status is JournalTradeStatus.PLANNED
        assert trade.exit_price is None
