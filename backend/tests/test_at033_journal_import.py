"""AT-033 — bulk journal import (dedup, dry-run, all-or-nothing commit)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AuditLog,
    JournalImportBatch,
    JournalTrade,
    Membership,
    Organization,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import (
    AuditEventType,
    JournalEntryMethod,
    JournalTradeSource,
    MembershipRole,
    TradeDirection,
)
from app.security.passwords import hash_password
from app.security.rate_limit import reset_rate_limiter

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000033001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000033002")
USER_A = uuid.UUID("00000000-0000-0000-0000-000000033011")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000033012")
VIEWER_A = uuid.UUID("00000000-0000-0000-0000-000000033013")

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "journal-import-test-secret-abc-32ch",
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


@pytest.fixture
def client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
    settings = Settings(**_BASE)

    with factory() as session:
        session.add(Organization(id=ORG_A, name="Import Org A"))
        session.add(Organization(id=ORG_B, name="Import Org B"))
        for user_id, email in (
            (USER_A, "import-a@test.example"),
            (USER_B, "import-b@test.example"),
            (VIEWER_A, "import-viewer@test.example"),
        ):
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
        session.add(Membership(user_id=VIEWER_A, organization_id=ORG_A, role=MembershipRole.VIEWER))
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


def _auth(client: TestClient, email: str, password: str = "SecurePass123!") -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "direction": "long",
        "status": "closed",
        "entry_price": "64500",
        "entry_time": "2026-06-01T10:00:00Z",
        "exit_price": "65500",
        "exit_time": "2026-06-01T18:00:00Z",
        "size": "0.5",
        "fees": "3.2",
        "net_pnl": "496.8",
        "external_ref": "exchange-x:1001",
        "tags": ["import-test"],
    }
    row.update(overrides)
    return row


def _import(
    client: TestClient,
    headers: dict[str, str],
    rows: list[dict[str, object]],
    *,
    mode: str = "dry_run",
    source_label: str | None = "unit-test",
) -> dict[str, object]:
    resp = client.post(
        "/journal/trades/import",
        json={"mode": mode, "source_label": source_label, "rows": rows},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Auth / RBAC
# --------------------------------------------------------------------------- #


def test_import_requires_auth(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    resp = test_client.post("/journal/trades/import", json={"mode": "dry_run", "rows": [_row()]})
    assert resp.status_code == 401


def test_viewer_cannot_import_but_can_read_history(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    viewer = _auth(test_client, "import-viewer@test.example")
    resp = test_client.post(
        "/journal/trades/import",
        json={"mode": "dry_run", "rows": [_row()]},
        headers=viewer,
    )
    assert resp.status_code == 403
    assert test_client.get("/journal/imports", headers=viewer).status_code == 200


# --------------------------------------------------------------------------- #
# Dry-run
# --------------------------------------------------------------------------- #


def test_dry_run_previews_without_persisting(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    body = _import(
        test_client,
        headers,
        [_row(), _row(external_ref="exchange-x:1002"), _row(symbol="??bad??")],
    )
    assert body["mode"] == "dry_run"
    assert body["committed"] is False
    assert body["batch_id"] is None
    assert body["created_count"] == 2
    assert body["invalid_count"] == 1
    outcomes = [r["outcome"] for r in body["results"]]
    assert outcomes == ["would_create", "would_create", "invalid"]
    assert body["results"][2]["errors"]

    with factory() as session:
        assert session.scalars(select(JournalTrade)).all() == []
        assert session.scalars(select(JournalImportBatch)).all() == []


# --------------------------------------------------------------------------- #
# Commit, dedup, idempotency
# --------------------------------------------------------------------------- #


def test_commit_creates_trades_batch_and_audit(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    body = _import(
        test_client,
        headers,
        [_row(), _row(external_ref="exchange-x:1002", net_pnl="-120")],
        mode="commit",
    )
    assert body["committed"] is True
    assert body["created_count"] == 2
    assert body["batch_id"] is not None

    with factory() as session:
        trades = session.scalars(
            select(JournalTrade).order_by(JournalTrade.external_ref.asc())
        ).all()
        assert len(trades) == 2
        assert all(t.source is JournalTradeSource.IMPORTED for t in trades)
        assert all(t.entry_method is JournalEntryMethod.IMPORT for t in trades)
        assert all(t.organization_id == ORG_A for t in trades)
        assert trades[0].external_ref == "exchange-x:1001"
        # Derived result from net_pnl sign.
        assert trades[0].result.value == "win"
        assert trades[1].result.value == "loss"

        batch = session.scalars(select(JournalImportBatch)).one()
        assert batch.created_count == 2
        assert batch.status.value == "committed"
        assert len(batch.row_report) == 2

        audit = session.scalars(
            select(AuditLog).where(AuditLog.action == AuditEventType.JOURNAL_IMPORT_COMPLETED)
        ).all()
        assert len(audit) == 1
        assert audit[0].resource_id == body["batch_id"]


def test_reimport_is_idempotent_via_external_ref(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    first = _import(test_client, headers, [_row()], mode="commit")
    created_id = first["results"][0]["journal_trade_id"]

    second = _import(test_client, headers, [_row()], mode="commit")
    assert second["created_count"] == 0
    assert second["duplicate_count"] == 1
    assert second["results"][0]["outcome"] == "duplicate"
    assert second["results"][0]["journal_trade_id"] == created_id

    with factory() as session:
        assert len(session.scalars(select(JournalTrade)).all()) == 1


def test_intra_batch_duplicates_are_skipped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    body = _import(test_client, headers, [_row(), _row()], mode="commit")
    assert body["created_count"] == 1
    assert body["duplicate_count"] == 1
    assert body["results"][1]["journal_trade_id"] == body["results"][0]["journal_trade_id"]

    with factory() as session:
        assert len(session.scalars(select(JournalTrade)).all()) == 1


def test_fingerprint_dedup_without_external_ref(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    row = _row(external_ref=None)
    first = _import(test_client, headers, [row], mode="commit")
    ref = first["results"][0]["external_ref"]
    assert ref is not None and ref.startswith("fp-sha256:")

    second = _import(test_client, headers, [row], mode="commit")
    assert second["duplicate_count"] == 1
    assert second["results"][0]["external_ref"] == ref

    with factory() as session:
        assert len(session.scalars(select(JournalTrade)).all()) == 1


def test_commit_with_invalid_rows_persists_nothing(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    body = _import(test_client, headers, [_row(), _row(symbol="??bad??")], mode="commit")
    assert body["committed"] is False
    assert body["invalid_count"] == 1
    assert body["batch_id"] is None
    assert [r["outcome"] for r in body["results"]] == ["would_create", "invalid"]

    with factory() as session:
        assert session.scalars(select(JournalTrade)).all() == []
        assert session.scalars(select(JournalImportBatch)).all() == []


def test_import_row_window_validation(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers = _auth(test_client, "import-a@test.example")
    body = _import(
        test_client,
        headers,
        [_row(entry_time="2026-06-02T10:00:00Z", exit_time="2026-06-01T10:00:00Z")],
    )
    assert body["results"][0]["outcome"] == "invalid"
    assert any("exit_time" in err for err in body["results"][0]["errors"])


# --------------------------------------------------------------------------- #
# Tenant isolation & constraint backstop
# --------------------------------------------------------------------------- #


def test_external_ref_dedup_is_org_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, factory = client
    headers_a = _auth(test_client, "import-a@test.example")
    headers_b = _auth(test_client, "import-b@test.example")
    _import(test_client, headers_a, [_row()], mode="commit")
    body_b = _import(test_client, headers_b, [_row()], mode="commit")
    assert body_b["created_count"] == 1

    with factory() as session:
        assert len(session.scalars(select(JournalTrade)).all()) == 2


def test_import_batches_are_tenant_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers_a = _auth(test_client, "import-a@test.example")
    headers_b = _auth(test_client, "import-b@test.example")
    body = _import(test_client, headers_a, [_row()], mode="commit")
    batch_id = body["batch_id"]

    listing_a = test_client.get("/journal/imports", headers=headers_a).json()
    assert listing_a["total"] == 1
    assert listing_a["items"][0]["id"] == batch_id

    listing_b = test_client.get("/journal/imports", headers=headers_b).json()
    assert listing_b["total"] == 0
    assert test_client.get(f"/journal/imports/{batch_id}", headers=headers_b).status_code == 404
    detail_a = test_client.get(f"/journal/imports/{batch_id}", headers=headers_a)
    assert detail_a.status_code == 200
    assert len(detail_a.json()["row_report"]) == 1


def test_unique_index_rejects_duplicate_external_ref(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """DB backstop: the partial unique index blocks races the app check misses."""
    test_client, factory = client
    headers = _auth(test_client, "import-a@test.example")
    _import(test_client, headers, [_row()], mode="commit")

    with factory() as session:
        session.add(
            JournalTrade(
                organization_id=ORG_A,
                user_id=USER_A,
                source=JournalTradeSource.IMPORTED,
                symbol="BTCUSDT",
                timeframe="1h",
                direction=TradeDirection.LONG,
                external_ref="exchange-x:1001",
                tags=[],
                planned_targets=[],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_null_external_refs_are_not_constrained(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, factory = client
    with factory() as session:
        for _ in range(2):
            session.add(
                JournalTrade(
                    organization_id=ORG_A,
                    user_id=USER_A,
                    source=JournalTradeSource.MANUAL,
                    symbol="ETHUSDT",
                    timeframe="4h",
                    direction=TradeDirection.SHORT,
                    external_ref=None,
                    tags=[],
                    planned_targets=[],
                )
            )
        session.commit()
        assert len(session.scalars(select(JournalTrade)).all()) == 2


# --------------------------------------------------------------------------- #
# Statistics readiness (entry_method dimension)
# --------------------------------------------------------------------------- #


def test_statistics_group_by_entry_method(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, _ = client
    headers = _auth(test_client, "import-a@test.example")
    _import(
        test_client,
        headers,
        [_row(), _row(external_ref="exchange-x:1002", net_pnl="-50")],
        mode="commit",
    )
    resp = test_client.get(
        "/journal/statistics", params={"group_by": "entry_method"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall"]["trade_count"] == 2
    keys = {bucket["key"] for bucket in body["buckets"]}
    assert keys == {"import"}

    filtered = test_client.get(
        "/journal/statistics", params={"entry_method": "manual"}, headers=headers
    ).json()
    assert filtered["overall"]["trade_count"] == 0
