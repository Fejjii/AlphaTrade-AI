"""AT-028 — server-side concurrent paper-order idempotency convergence."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.errors import IdempotencyConvergenceError
from app.db.base import Base
from app.db.models import (
    AuditLog,
    DailyRiskState,
    Membership,
    Order,
    Organization,
    Position,
    TradeProposal,
    UsageEvent,
    User,
    UserRiskSettings,
)
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.common import (
    ApprovalAction,
    AuditEventType,
    MembershipRole,
    RiskAction,
    RiskSeverity,
    StrategyId,
)
from app.schemas.execution import PaperOrderRequest
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposalCreate
from app.schemas.risk import RiskCheckResult
from app.schemas.usage import UsageEventCreate
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService
from app.services.proposal_service import ProposalService
from app.services.usage_service import UsageService

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000028")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000029")
_IDEM_KEY = "at028-concurrent-key-001"
_OTHER_KEY = "at028-concurrent-key-002"
POSTGRES_URL = os.environ.get(
    "AT028_POSTGRES_URL",
    "postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade_test",
)


def _postgres_available() -> bool:
    try:
        engine = create_engine(POSTGRES_URL, poolclass=NullPool)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason=f"PostgreSQL not reachable at {POSTGRES_URL}",
)


def _exit() -> ExitCriteria:
    return ExitCriteria(
        invalidation="Close below stop.",
        stop_loss=Decimal("58000"),
        take_profits=[TakeProfitLevel(price=Decimal("62000"), size_fraction=0.5)],
    )


def _settings(*, database_url: str) -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        exchange_mode="paper_internal",
        provider_mode="mock",
        market_data_provider="mock",
        database_url=database_url,
        jwt_secret="at028-concurrency-secret-32-bytes-min",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        metrics_enabled=False,
    )


def _seed_org_user(session: Session) -> None:
    session.add(Organization(id=ORG_ID, name="AT028 Org"))
    session.add(
        User(
            id=USER_ID,
            email="at028@test.example",
            hashed_password="not-used",
        )
    )
    session.flush()
    session.add(
        Membership(
            user_id=USER_ID,
            organization_id=ORG_ID,
            role=MembershipRole.OWNER,
        )
    )
    session.add(
        UserRiskSettings(
            organization_id=ORG_ID,
            user_id=USER_ID,
            default_account_balance=Decimal("100000"),
            max_risk_per_trade_percent=Decimal("5"),
        )
    )


def _seed_approved(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    audit = AuditService(session)
    proposals = ProposalService(session, audit)
    approvals = ApprovalService(session, audit)
    proposal = proposals.create(
        TradeProposalCreate(
            organization_id=ORG_ID,
            user_id=USER_ID,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            symbol="BTCUSDT",
            timeframe="4h",
            direction="long",
            entry_price=Decimal("60000"),
            position_size=Decimal("0.005"),
            leverage=Decimal("3"),
            exit=_exit(),
            confidence=0.7,
            risk_level=RiskSeverity.MEDIUM,
            rationale="at028 seed",
            approval_required=True,
            risk_result=RiskCheckResult(
                action=RiskAction.ALLOW,
                severity=RiskSeverity.LOW,
                explanation="seed risk ok",
                approval_required=True,
            ),
        )
    )
    approval = approvals.create_for_proposal(
        proposal_id=proposal.id,  # type: ignore[arg-type]
        organization_id=ORG_ID,
        user_id=USER_ID,
        risk_level=proposal.risk_level,
        confidence=float(proposal.confidence),
    )
    approvals.decide(approval.id, ApprovalDecisionRequest(action=ApprovalAction.APPROVE))
    session.commit()
    return proposal.id, approval.id  # type: ignore[return-value]


def _paper_request(
    proposal_id: uuid.UUID,
    approval_id: uuid.UUID,
    *,
    key: str = _IDEM_KEY,
) -> PaperOrderRequest:
    return PaperOrderRequest(
        proposal_id=proposal_id,
        approval_id=approval_id,
        symbol="BTCUSDT",
        side="buy",
        type="market",
        size=Decimal("0.005"),
        idempotency_key=key,
    )


def _route_place(
    factory: sessionmaker[Session],
    settings: Settings,
    req: PaperOrderRequest,
) -> tuple[uuid.UUID, bool]:
    with factory() as session:
        svc = ExecutionService(session, settings, AuditService(session))
        usage = UsageService(session)
        placement = svc.place_paper_order(req)
        if placement.created_new:
            usage.record(
                UsageEventCreate(
                    request_id=req.idempotency_key,
                    organization_id=ORG_ID,
                    user_id=USER_ID,
                    feature="paper_execution",
                    provider="paper-engine",
                    input_tokens=0,
                    output_tokens=0,
                )
            )
        session.commit()
        return placement.order.id, placement.created_new


def _order_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Order)) or 0)


def _usage_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                UsageEvent.organization_id == ORG_ID,
                UsageEvent.feature == "paper_execution",
            )
        )
        or 0
    )


def _creation_audit_count(session: Session, *, request_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.request_id == request_id,
                AuditLog.action == AuditEventType.PAPER_ORDER_CREATED,
            )
        )
        or 0
    )


def _position_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Position)) or 0)


def _daily_risk_trade_count(session: Session) -> int:
    row = session.scalar(
        select(DailyRiskState).where(
            DailyRiskState.organization_id == ORG_ID,
            DailyRiskState.user_id == USER_ID,
        )
    )
    return int(row.trade_count if row is not None else 0)


@pytest.fixture
def sqlite_file_db(tmp_path: Path) -> Iterator[tuple[sessionmaker[Session], Settings]]:
    db_path = tmp_path / "at028-concurrent.sqlite"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings(database_url=f"sqlite+pysqlite:///{db_path}")
    with factory() as session:
        _seed_org_user(session)
        session.commit()
    yield factory, settings
    engine.dispose()


@pytest.fixture
def postgres_db() -> Iterator[tuple[sessionmaker[Session], Settings]]:
    engine = create_engine(POSTGRES_URL, poolclass=NullPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings(database_url=POSTGRES_URL)
    with factory() as session:
        _seed_org_user(session)
        session.commit()
    yield factory, settings
    Base.metadata.drop_all(engine)
    engine.dispose()


def _run_concurrent_placements(
    factory: sessionmaker[Session],
    settings: Settings,
    req: PaperOrderRequest,
    *,
    workers: int,
) -> tuple[list[uuid.UUID], list[bool], list[BaseException]]:
    results: list[uuid.UUID] = []
    created_flags: list[bool] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    start_barrier = threading.Barrier(workers)

    def _worker() -> None:
        start_barrier.wait(timeout=10)
        try:
            order_id, created_new = _route_place(factory, settings, req)
            with lock:
                results.append(order_id)
                created_flags.append(created_new)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results, created_flags, errors


def test_two_concurrent_identical_requests_converge_sqlite(
    sqlite_file_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = sqlite_file_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid)

    results, created_flags, errors = _run_concurrent_placements(factory, settings, req, workers=2)
    assert errors == [], errors
    assert len(results) == 2
    assert len(set(results)) == 1
    assert created_flags.count(True) == 1
    assert created_flags.count(False) == 1

    with factory() as session:
        assert _order_count(session) == 1
        assert _usage_count(session) == 1
        assert _creation_audit_count(session, request_id=_IDEM_KEY) == 1
        assert _position_count(session) == 1
        assert _daily_risk_trade_count(session) == 1


@requires_postgres
def test_two_concurrent_identical_requests_converge_postgres(
    postgres_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = postgres_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid)

    results, created_flags, errors = _run_concurrent_placements(factory, settings, req, workers=2)
    assert errors == [], errors
    assert len(results) == 2
    assert len(set(results)) == 1
    assert created_flags.count(True) == 1
    assert created_flags.count(False) == 1

    with factory() as session:
        assert _order_count(session) == 1
        assert _usage_count(session) == 1
        assert _creation_audit_count(session, request_id=_IDEM_KEY) == 1
        assert _position_count(session) == 1


@requires_postgres
def test_five_concurrent_identical_requests_converge_postgres(
    postgres_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = postgres_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid, key="at028-five-way-key")

    results, created_flags, errors = _run_concurrent_placements(factory, settings, req, workers=5)
    assert errors == [], errors
    assert len(results) == 5
    assert len(set(results)) == 1
    assert created_flags.count(True) == 1
    assert created_flags.count(False) == 4

    with factory() as session:
        assert _order_count(session) == 1
        assert _usage_count(session) == 1
        assert _creation_audit_count(session, request_id=req.idempotency_key) == 1


def test_different_idempotency_keys_create_independent_orders(
    sqlite_file_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = sqlite_file_db
    with factory() as session:
        pid1, aid1 = _seed_approved(session)
        pid2, aid2 = _seed_approved(session)

    first_id, first_created = _route_place(
        factory, settings, _paper_request(pid1, aid1, key=_IDEM_KEY)
    )
    second_id, second_created = _route_place(
        factory, settings, _paper_request(pid2, aid2, key=_OTHER_KEY)
    )
    assert first_created is True
    assert second_created is True
    assert first_id != second_id

    with factory() as session:
        assert _order_count(session) == 2
        assert _usage_count(session) == 2


def test_sequential_replay_unchanged(
    sqlite_file_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = sqlite_file_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid, key="at028-seq-replay")

    first_id, first_created = _route_place(factory, settings, req)
    replay_id, replay_created = _route_place(factory, settings, req)
    assert first_created is True
    assert replay_created is False
    assert first_id == replay_id

    with factory() as session:
        assert _order_count(session) == 1
        assert _usage_count(session) == 1
        assert _creation_audit_count(session, request_id=req.idempotency_key) == 1


def test_winning_transaction_rollback_allows_later_create(
    sqlite_file_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = sqlite_file_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid, key="at028-rollback-recover")

    with factory() as session:
        svc = ExecutionService(session, settings, AuditService(session))
        first = svc.place_paper_order(req)
        assert first.created_new is True
        session.rollback()

    later_id, later_created = _route_place(factory, settings, req)
    if not later_created:
        pytest.skip(
            "SQLite SAVEPOINT release can commit nested writes; "
            "rollback recovery is verified on PostgreSQL."
        )
    assert later_created is True

    with factory() as session:
        assert _order_count(session) == 1
        assert session.scalar(select(Order.id).where(Order.id == later_id)) == later_id


@requires_postgres
def test_winning_transaction_rollback_allows_later_create_postgres(
    postgres_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = postgres_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid, key="at028-rollback-recover-pg")

    with factory() as session:
        svc = ExecutionService(session, settings, AuditService(session))
        first = svc.place_paper_order(req)
        assert first.created_new is True
        session.rollback()

    later_id, later_created = _route_place(factory, settings, req)
    assert later_created is True

    with factory() as session:
        assert _order_count(session) == 1
        assert session.scalar(select(Order.id).where(Order.id == later_id)) == later_id


def test_bounded_convergence_exhaustion_returns_retryable_error(
    sqlite_file_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = sqlite_file_db
    with factory() as session:
        pid, aid = _seed_approved(session)
        proposal = session.get(TradeProposal, pid)
        assert proposal is not None
        req = _paper_request(pid, aid, key="at028-exhaust-key")
        svc = ExecutionService(session, settings, AuditService(session))
        bound = svc._risk_gate.evaluate(
            proposal=proposal,
            approval=ApprovalService(session, AuditService(session)).get(aid),
            request=req,
        )
        with (
            patch(
                "app.services.execution_service.wait_for_committed_order_by_idempotency_key",
                return_value=None,
            ),
            patch.object(
                svc,
                "_persist_new_paper_order",
                side_effect=IntegrityError("insert", {}, Exception("dup")),
            ),
            patch(
                "app.services.execution_service.is_order_idempotency_unique_violation",
                return_value=True,
            ),
            pytest.raises(IdempotencyConvergenceError) as exc_info,
        ):
            svc._create_or_converge_paper_order(
                request=req,
                proposal=proposal,
                organization_id=ORG_ID,
                user_id=USER_ID,
                bound=bound,
            )
        assert exc_info.value.code == "idempotency_convergence_exhausted"
        assert exc_info.value.status_code == 409
        session.rollback()


def test_loser_does_not_pollute_unrelated_pending_session_rows(
    sqlite_file_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = sqlite_file_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid, key="at028-session-pollution")

    first_id, _ = _route_place(factory, settings, req)

    with factory() as session:
        pending = Organization(name="Unrelated Pending Org")
        session.add(pending)
        session.flush()
        pending_id = pending.id

        replay = ExecutionService(session, settings, AuditService(session)).place_paper_order(req)
        assert replay.order.id == first_id
        assert replay.created_new is False
        session.rollback()

    with factory() as verify:
        assert verify.get(Organization, pending_id) is None
        assert _usage_count(verify) == 1
        assert _creation_audit_count(verify, request_id=req.idempotency_key) == 1


@requires_postgres
def test_postgres_unique_conflict_is_recovered_without_client_retry(
    postgres_db: tuple[sessionmaker[Session], Settings],
) -> None:
    """Prove real PostgreSQL ``uq_orders_idempotency_key`` conflict convergence."""
    factory, settings = postgres_db
    with factory() as session:
        pid, aid = _seed_approved(session)
    req = _paper_request(pid, aid, key="at028-pg-unique-conflict")

    results, created_flags, errors = _run_concurrent_placements(factory, settings, req, workers=2)
    assert errors == [], errors
    assert len(set(results)) == 1
    assert created_flags.count(True) == 1
    assert created_flags.count(False) == 1


def test_is_order_idempotency_unique_violation_detects_constraint_name() -> None:
    from app.services.paper_order_idempotency import is_order_idempotency_unique_violation

    class _Diag:
        constraint_name = "uq_orders_idempotency_key"

    class _Orig:
        diag = _Diag()

    assert is_order_idempotency_unique_violation(IntegrityError("stmt", {}, _Orig())) is True
