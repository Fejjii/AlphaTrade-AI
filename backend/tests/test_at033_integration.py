"""AT-033 — cross-workstream integration (import + backfill + auto-journal + stats)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    JournalImportBatch,
    JournalTrade,
    Membership,
    Organization,
    Position,
    TradeJournal,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.repositories.journal_trades import JournalImportBatchRepository
from app.schemas.common import (
    MembershipRole,
    PositionStatus,
    StrategyId,
    TradeDirection,
    TradeResult,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter
from app.services.audit_service import AuditService
from app.services.journal_backfill_service import JournalBackfillService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000033401")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000033411")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "at033-integration-test-secret-32char",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "alert_delivery_enabled": False,
    "telegram_alerts_enabled": False,
    "worker_enabled": False,
    "market_watcher_enabled": False,
}


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@contextmanager
def _build_client(
    **settings_overrides: object,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(**{**_BASE, **settings_overrides})

    with factory() as session:
        session.add(Organization(id=ORG_A, name="Integration Org"))
        session.add(
            User(
                id=USER_A,
                email="integration@test.example",
                hashed_password=hash_password("SecurePass123!", settings),
                email_verified=True,
            )
        )
        session.flush()
        session.add(Membership(user_id=USER_A, organization_id=ORG_A, role=MembershipRole.OWNER))
        session.commit()

    app = create_app(settings=settings)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as test_client:
        yield test_client, factory

    app.dependency_overrides.clear()
    engine.dispose()


def _auth(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": "integration@test.example", "password": "SecurePass123!"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}


def _import_rows(client: TestClient, headers: dict[str, str], rows: list[dict], mode: str) -> dict:
    resp = client.post(
        "/journal/trades/import",
        json={"mode": mode, "source_label": "integration", "rows": rows},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _closed_import_row(ref: str, pnl: str) -> dict:
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "direction": "long",
        "status": "closed",
        "entry_price": "64000",
        "entry_time": "2026-06-01T10:00:00Z",
        "exit_time": "2026-06-01T18:00:00Z",
        "net_pnl": pnl,
        "external_ref": ref,
    }


def _seed_legacy_entry(factory: sessionmaker[Session]) -> uuid.UUID:
    with factory() as session:
        entry = TradeJournal(
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="ETHUSDT",
            timeframe="4h",
            direction=TradeDirection.SHORT,
            strategy_id=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
            entry_rationale="Sweep of highs into supply.",
            result=TradeResult.LOSS,
            pnl=Decimal("-80"),
            tags=["legacy"],
        )
        session.add(entry)
        session.commit()
        return entry.id


def _run_backfill(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        audit = AuditService(session, strict_mode=True, session_factory=factory)
        JournalBackfillService(session, audit).backfill(dry_run=False)
        session.commit()


def _seed_and_close_position(
    client: TestClient, headers: dict[str, str], factory: sessionmaker[Session]
) -> None:
    with factory() as session:
        position = Position(
            organization_id=ORG_A,
            user_id=USER_A,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            symbol="SOLUSDT",
            direction=TradeDirection.LONG,
            size=Decimal("10"),
            entry_price=Decimal("150"),
            leverage=Decimal("2"),
            stop_loss=Decimal("140"),
            status=PositionStatus.OPEN,
            opened_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        )
        session.add(position)
        session.commit()
        position_id = position.id
    resp = client.post(
        f"/positions/{position_id}/close-paper",
        json={"exit_price": "160", "reason": "integration"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def test_entry_method_statistics_separate_all_creation_paths() -> None:
    """Human-vs-system end to end: manual, import, backfill, and auto buckets."""
    with _build_client(journal_auto_from_position_close=True) as (client, factory):
        headers = _auth(client)

        # Manual closed trade via API (entry_method=manual).
        manual = client.post(
            "/journal/trades",
            json={
                "source": "manual",
                "status": "closed",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "direction": "long",
                "net_pnl": "120",
                "result": "win",
            },
            headers=headers,
        )
        assert manual.status_code == 201, manual.text

        # Bulk import (entry_method=import).
        result = _import_rows(
            client,
            headers,
            [_closed_import_row("int-1", "50"), _closed_import_row("int-2", "-20")],
            mode="commit",
        )
        assert result["committed"] is True and result["created_count"] == 2

        # Legacy backfill (entry_method=backfill).
        _seed_legacy_entry(factory)
        _run_backfill(factory)

        # Auto-journal on paper close (entry_method=auto).
        _seed_and_close_position(client, headers, factory)

        stats = client.get(
            "/journal/statistics", params={"group_by": "entry_method"}, headers=headers
        )
        assert stats.status_code == 200, stats.text
        body = stats.json()
        assert body["overall"]["trade_count"] == 5
        buckets = {bucket["key"]: bucket["metrics"]["trade_count"] for bucket in body["buckets"]}
        assert buckets == {"manual": 1, "import": 2, "backfill": 1, "auto": 1}

        # Filtering by a single entry method narrows the aggregate.
        filtered = client.get(
            "/journal/statistics", params={"entry_method": "import"}, headers=headers
        ).json()
        assert filtered["overall"]["trade_count"] == 2


def test_backfill_then_import_with_same_external_ref_does_not_duplicate() -> None:
    with _build_client() as (client, factory):
        headers = _auth(client)
        entry_id = _seed_legacy_entry(factory)
        _run_backfill(factory)

        result = _import_rows(
            client,
            headers,
            [
                {
                    "symbol": "ETHUSDT",
                    "timeframe": "4h",
                    "direction": "short",
                    "external_ref": f"legacy-journal:{entry_id}",
                }
            ],
            mode="commit",
        )
        assert result["duplicate_count"] == 1
        assert result["created_count"] == 0

        with factory() as session:
            assert len(session.scalars(select(JournalTrade)).all()) == 1


def test_failed_commit_leaves_no_partial_rows_and_rerun_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All-or-nothing recovery: injected failure after trades are staged."""
    with _build_client() as (client, factory):
        headers = _auth(client)
        rows = [_closed_import_row("recover-1", "10"), _closed_import_row("recover-2", "20")]

        def _boom(self: object, entity: object) -> object:
            raise RuntimeError("simulated batch persistence failure")

        monkeypatch.setattr(JournalImportBatchRepository, "add", _boom)
        with pytest.raises(RuntimeError, match="simulated batch persistence failure"):
            client.post(
                "/journal/trades/import",
                json={"mode": "commit", "rows": rows},
                headers=headers,
            )

        with factory() as session:
            assert session.scalars(select(JournalTrade)).all() == []
            assert session.scalars(select(JournalImportBatch)).all() == []

        monkeypatch.undo()
        result = _import_rows(client, headers, rows, mode="commit")
        assert result["committed"] is True
        assert result["created_count"] == 2

        with factory() as session:
            assert len(session.scalars(select(JournalTrade)).all()) == 2
            assert len(session.scalars(select(JournalImportBatch)).all()) == 1
