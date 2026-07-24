"""AT-033 — TradeJournal → journal_trades backfill (idempotent, dry-run first)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AuditLog,
    JournalTrade,
    JournalTradeEvidence,
    Membership,
    Organization,
    TradeJournal,
    User,
)
from app.schemas.common import (
    AuditEventType,
    JournalEntryMethod,
    JournalTradeSource,
    JournalTradeStatus,
    MembershipRole,
    StrategyId,
    TradeDirection,
    TradeResult,
)
from app.security.passwords import hash_password
from app.services.audit_service import AuditService
from app.services.journal_backfill_service import JournalBackfillService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000033101")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000033102")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000033111")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000033112")

_SETTINGS = {
    "environment": "local",
    "log_json": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "journal-backfill-test-secret-32chars",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
}


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
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
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(**_SETTINGS)

    with maker() as session:
        session.add(Organization(id=ORG_A, name="Backfill Org A"))
        session.add(Organization(id=ORG_B, name="Backfill Org B"))
        for user_id, email in ((USER_A, "bf-a@test.example"), (USER_B, "bf-b@test.example")):
            session.add(
                User(
                    id=user_id,
                    email=email,
                    hashed_password=hash_password("SecurePass123!", settings),
                    email_verified=True,
                )
            )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.add(Membership(user_id=USER_B, organization_id=ORG_B, role=MembershipRole.OWNER))
        session.commit()

    yield maker
    engine.dispose()


def _seed_legacy(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID = ORG_A,
    user_id: uuid.UUID = USER_A,
    result: TradeResult = TradeResult.WIN,
    pnl: str | None = "150",
    screenshots: list[str] | None = None,
) -> uuid.UUID:
    with factory() as session:
        entry = TradeJournal(
            organization_id=organization_id,
            user_id=user_id,
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TradeDirection.LONG,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            entry_rationale="Pullback into HTF demand.",
            exit_rationale="TP1 hit, closed remainder at breakeven.",
            emotions=["calm"],
            mistakes=["late entry"],
            lessons="Wait for the sweep.",
            improvement_rule="Only enter after 1h confirmation.",
            result=result,
            pnl=Decimal(pnl) if pnl is not None else None,
            tags=["backfill-test"],
            screenshot_refs=screenshots or [],
        )
        session.add(entry)
        session.commit()
        return entry.id


def _run(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID | None = None,
    dry_run: bool = True,
) -> object:
    with factory() as session:
        audit = AuditService(session, strict_mode=True, session_factory=factory)
        service = JournalBackfillService(session, audit)
        summary = service.backfill(organization_id=organization_id, dry_run=dry_run)
        if dry_run:
            session.rollback()
        else:
            session.commit()
        return summary


def test_dry_run_creates_nothing(factory: sessionmaker[Session]) -> None:
    _seed_legacy(factory)
    summary = _run(factory, dry_run=True)
    assert summary.dry_run is True
    assert summary.total_legacy == 1
    assert summary.created == 1  # would create
    assert summary.skipped_existing == 0

    with factory() as session:
        assert session.scalars(select(JournalTrade)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


def test_commit_maps_legacy_fields(factory: sessionmaker[Session]) -> None:
    entry_id = _seed_legacy(factory, screenshots=["https://img.example/1.png"])
    summary = _run(factory, dry_run=False)
    assert summary.created == 1

    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        assert trade.source is JournalTradeSource.IMPORTED
        assert trade.entry_method is JournalEntryMethod.BACKFILL
        assert trade.status is JournalTradeStatus.CLOSED
        assert trade.symbol == "BTCUSDT"
        assert trade.timeframe == "1h"
        assert trade.direction is TradeDirection.LONG
        assert trade.strategy_label == StrategyId.HTF_TREND_PULLBACK.value
        assert trade.thesis == "Pullback into HTF demand."
        assert trade.net_pnl == Decimal("150")
        assert trade.result is TradeResult.WIN
        assert trade.linked_journal_entry_id == entry_id
        assert trade.external_ref == f"legacy-journal:{entry_id}"
        assert trade.tags == ["backfill-test"]
        assert trade.notes is not None
        assert "Exit rationale:" in trade.notes
        assert "Lessons:" in trade.notes
        assert "Improvement rule:" in trade.notes
        assert "Emotions: calm" in trade.notes
        assert "Mistakes: late entry" in trade.notes

        evidence = session.scalars(select(JournalTradeEvidence)).all()
        assert len(evidence) == 1
        assert evidence[0].ref == "https://img.example/1.png"
        assert evidence[0].journal_trade_id == trade.id

        audit = session.scalars(
            select(AuditLog).where(AuditLog.action == AuditEventType.JOURNAL_BACKFILL_COMPLETED)
        ).all()
        assert len(audit) == 1
        assert audit[0].organization_id == ORG_A


def test_open_legacy_entry_stays_open(factory: sessionmaker[Session]) -> None:
    _seed_legacy(factory, result=TradeResult.OPEN, pnl=None)
    _run(factory, dry_run=False)
    with factory() as session:
        trade = session.scalars(select(JournalTrade)).one()
        assert trade.status is JournalTradeStatus.OPEN
        assert trade.result is TradeResult.OPEN
        assert trade.net_pnl is None


def test_backfill_is_idempotent(factory: sessionmaker[Session]) -> None:
    _seed_legacy(factory)
    first = _run(factory, dry_run=False)
    assert first.created == 1
    second = _run(factory, dry_run=False)
    assert second.created == 0
    assert second.skipped_existing == 1

    with factory() as session:
        assert len(session.scalars(select(JournalTrade)).all()) == 1
        # No second backfill audit event when nothing was created.
        audit = session.scalars(
            select(AuditLog).where(AuditLog.action == AuditEventType.JOURNAL_BACKFILL_COMPLETED)
        ).all()
        assert len(audit) == 1


def test_manually_linked_entries_are_skipped(factory: sessionmaker[Session]) -> None:
    entry_id = _seed_legacy(factory)
    with factory() as session:
        session.add(
            JournalTrade(
                organization_id=ORG_A,
                user_id=USER_A,
                source=JournalTradeSource.MANUAL,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                linked_journal_entry_id=entry_id,
                tags=[],
                planned_targets=[],
            )
        )
        session.commit()

    summary = _run(factory, dry_run=False)
    assert summary.created == 0
    assert summary.skipped_existing == 1


def test_org_scoped_backfill(factory: sessionmaker[Session]) -> None:
    _seed_legacy(factory, organization_id=ORG_A, user_id=USER_A)
    _seed_legacy(factory, organization_id=ORG_B, user_id=USER_B)

    summary = _run(factory, organization_id=ORG_A, dry_run=False)
    assert summary.total_legacy == 1
    assert summary.created == 1

    with factory() as session:
        trades = session.scalars(select(JournalTrade)).all()
        assert len(trades) == 1
        assert trades[0].organization_id == ORG_A
