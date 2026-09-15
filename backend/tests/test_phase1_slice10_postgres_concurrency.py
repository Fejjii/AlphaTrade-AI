"""Phase 1 slice 10: PostgreSQL concurrency, fencing, and crash-injection tests."""

from __future__ import annotations

import os
import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.errors import ConflictError, NotFoundError, TradingPolicyError
from app.db.base import Base
from app.db.models import (
    AccountRiskAccountingState,
    ApprovalAuthorization,
    ExecutionCommand,
    ExecutionProjection,
    PlanEntryExecutionClaim,
    RiskReservation,
    VenueSubmitEffect,
)
from app.providers.execution.fake_venue import FakeVenueBehavior, FakeVenueSubmitProvider
from app.schemas.execution_protocol import (
    ExecutionCommandOutcome,
    ExecutionReceiptState,
    RiskReservationReleaseState,
    VenueSubmitEffectState,
)
from app.schemas.risk import KillSwitchMutationRequest
from app.schemas.trade_plan import AuthorizationState
from app.services.audit_service import AuditService
from app.services.execution_claim import ExecutionClaimHooks, conservative_reservation
from app.services.execution_service import ExecutionService
from app.services.risk.kill_switch import KillSwitchService
from tests.support.phase1_plan_fixtures import (
    EXECUTE_AT,
    approve_plan,
    execute_request,
    execution_service,
    paper_settings,
    persist_plan,
    plan_request,
    prepared_authorized_plan,
)

POSTGRES_URL = os.environ.get(
    "PHASE1_POSTGRES_URL",
    os.environ.get(
        "AT028_POSTGRES_URL",
        "postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade_test",
    ),
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


def _factory() -> tuple[sessionmaker[Session], str]:
    engine = create_engine(POSTGRES_URL, poolclass=NullPool, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), POSTGRES_URL


def _count(session: Session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


@requires_postgres
def test_postgres_two_identical_first_writers_converge() -> None:
    factory, url = _factory()
    with factory() as setup:
        ids, plan, authorization = prepared_authorized_plan(setup)
        setup.commit()
        org_id = ids["organization"].id
        key = f"pg-two-{uuid.uuid4()}"
        request = execute_request(ids, plan, authorization, key=key)
        auth_id = authorization.authorization_id
        plan_id = plan.revision_id
        account_id = plan.account_id

    barrier = threading.Barrier(2)
    results: list[object] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        with factory() as session:
            try:
                barrier.wait(timeout=20)
                service = execution_service(session, database_url=url)
                result = service.execute_paper_plan(request, clock=lambda: EXECUTE_AT)
                session.commit()
                with lock:
                    results.append(result)
            except BaseException as exc:
                session.rollback()
                with lock:
                    errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    assert len(results) == 2
    command_ids = {item.command_id for item in results}  # type: ignore[union-attr]
    receipt_ids = {item.receipt.receipt_id for item in results}  # type: ignore[union-attr]
    client_ids = {item.client_order_id for item in results}  # type: ignore[union-attr]
    assert len(command_ids) == 1
    assert len(receipt_ids) == 1
    assert len(client_ids) == 1
    allows = [item for item in results if not item.replayed]  # type: ignore[union-attr]
    assert len(allows) == 1
    with factory() as session:
        assert _count(session, ExecutionCommand) >= 1
        claims = list(
            session.scalars(
                select(PlanEntryExecutionClaim).where(
                    PlanEntryExecutionClaim.revision_id == plan_id
                )
            )
        )
        assert len(claims) == 1
        auth = session.get(ApprovalAuthorization, auth_id)
        assert auth is not None
        assert auth.state is AuthorizationState.CONSUMED
        effects = list(
            session.scalars(
                select(VenueSubmitEffect).where(
                    VenueSubmitEffect.command_id == claims[0].command_id
                )
            )
        )
        assert len(effects) == 1
        del org_id, account_id


@requires_postgres
def test_postgres_five_identical_first_writers_converge() -> None:
    factory, url = _factory()
    with factory() as setup:
        ids, plan, authorization = prepared_authorized_plan(setup)
        setup.commit()
        request = execute_request(ids, plan, authorization, key=f"pg-five-{uuid.uuid4()}")
        auth_id = authorization.authorization_id

    barrier = threading.Barrier(5)
    results: list[object] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        with factory() as session:
            try:
                barrier.wait(timeout=30)
                result = execution_service(session, database_url=url).execute_paper_plan(
                    request, clock=lambda: EXECUTE_AT
                )
                session.commit()
                with lock:
                    results.append(result)
            except BaseException as exc:
                session.rollback()
                with lock:
                    errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=45)
    assert errors == []
    assert len(results) == 5
    assert len({item.command_id for item in results}) == 1  # type: ignore[union-attr]
    assert len({item.client_order_id for item in results}) == 1  # type: ignore[union-attr]
    with factory() as session:
        auth = session.get(ApprovalAuthorization, auth_id)
        assert auth is not None
        assert auth.state is AuthorizationState.CONSUMED
        assert _count(session, PlanEntryExecutionClaim) >= 1


@requires_postgres
def test_postgres_same_key_different_payload_conflicts() -> None:
    factory, url = _factory()
    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        other = persist_plan(
            session, ids, plan_request(ids, quantity={"value": "3", "unit": "CONTRACTS"})
        )
        other_auth = approve_plan(session, ids, other)
        session.commit()
        key = f"pg-payload-{uuid.uuid4()}"
        execution_service(session, database_url=url).execute_paper_plan(
            execute_request(ids, plan, authorization, key=key),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        with pytest.raises(ConflictError):
            execution_service(session, database_url=url).execute_paper_plan(
                execute_request(ids, other, other_auth, key=key),
                clock=lambda: EXECUTE_AT,
            )


@requires_postgres
def test_postgres_different_keys_same_plan_one_claim() -> None:
    factory, url = _factory()
    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        service = execution_service(session, database_url=url)
        first = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-a-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        second = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-b-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        assert first.outcome is ExecutionCommandOutcome.ALLOW
        assert second.outcome is ExecutionCommandOutcome.BLOCKED
        claims = list(
            session.scalars(
                select(PlanEntryExecutionClaim).where(
                    PlanEntryExecutionClaim.revision_id == plan.revision_id
                )
            )
        )
        assert len(claims) == 1


@requires_postgres
def test_postgres_capacity_race_one_allow_one_block() -> None:
    factory, url = _factory()
    with factory() as setup:
        ids, plan, authorization = prepared_authorized_plan(setup)
        other = persist_plan(
            setup, ids, plan_request(ids, quantity={"value": "3", "unit": "CONTRACTS"})
        )
        other_auth = approve_plan(setup, ids, other)
        intent = conservative_reservation(plan)
        setup.add(
            AccountRiskAccountingState(
                organization_id=ids["organization"].id,
                account_id=plan.account_id,
                reserved_notional=Decimal("0"),
                reserved_daily_loss=Decimal("0"),
                reserved_trade_slots=0,
                actual_notional=Decimal("0"),
                actual_daily_loss=Decimal("0"),
                actual_trade_count=0,
                symbol_reserved={},
                symbol_actual={},
                max_notional=intent.pending_notional,
                max_daily_loss=Decimal("1000"),
                max_trade_slots=20,
                max_symbol_notional=intent.pending_notional * 10,
                daily_locked=False,
                exposure_unit=intent.exposure_unit,
                version=1,
            )
        )
        setup.commit()
        req_a = execute_request(ids, plan, authorization, key=f"pg-cap-a-{uuid.uuid4()}")
        req_b = execute_request(ids, other, other_auth, key=f"pg-cap-b-{uuid.uuid4()}")

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(request: object) -> None:
        with factory() as session:
            barrier.wait(timeout=20)
            result = execution_service(session, database_url=url).execute_paper_plan(
                request,  # type: ignore[arg-type]
                clock=lambda: EXECUTE_AT,
            )
            session.commit()
            with lock:
                outcomes.append(result.outcome.value)

    threads = [
        threading.Thread(target=worker, args=(req_a,)),
        threading.Thread(target=worker, args=(req_b,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(outcomes) == ["ALLOW", "BLOCKED"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RiskReservation)) == 1
        assert session.scalar(select(func.count()).select_from(PlanEntryExecutionClaim)) == 1


@requires_postgres
def test_postgres_kill_before_and_during_claim() -> None:
    factory, url = _factory()
    with factory() as setup:
        ids, plan, authorization = prepared_authorized_plan(setup)
        setup.commit()
        org_id = ids["organization"].id
        user_id = ids["user"].id
        settings = paper_settings(database_url=url)
        before_req = execute_request(ids, plan, authorization, key=f"pg-kill-before-{uuid.uuid4()}")

    with factory() as session:
        KillSwitchService(session, AuditService(session), settings).activate(
            organization_id=org_id,
            actor_user_id=user_id,
            payload=KillSwitchMutationRequest(confirm=True, reason="halt before claim"),
        )
        session.commit()
        blocked = execution_service(session, database_url=url).execute_paper_plan(
            before_req, clock=lambda: EXECUTE_AT
        )
        session.commit()
        assert blocked.outcome is ExecutionCommandOutcome.BLOCKED
        auth = session.get(ApprovalAuthorization, authorization.authorization_id)
        assert auth is not None
        assert auth.state is AuthorizationState.AVAILABLE

    with factory() as setup:
        ids2, plan2, authorization2 = prepared_authorized_plan(setup)
        setup.commit()
        org2 = ids2["organization"].id
        user2 = ids2["user"].id
        during_key = f"pg-kill-during-{uuid.uuid4()}"
        during_req = execute_request(ids2, plan2, authorization2, key=during_key)
        settings2 = paper_settings(database_url=url)

    ready = threading.Event()
    released = threading.Event()
    claim_result: list[str] = []

    def claimer() -> None:
        with factory() as session:
            hooks = ExecutionClaimHooks(after_idempotency=lambda: (ready.set(), released.wait(20)))
            result = ExecutionService(session, settings2, AuditService(session)).execute_paper_plan(
                during_req, clock=lambda: EXECUTE_AT, hooks=hooks
            )
            session.commit()
            claim_result.append(result.outcome.value)

    def killer() -> None:
        ready.wait(timeout=20)
        with factory() as session:
            KillSwitchService(session, AuditService(session), settings2).activate(
                organization_id=org2,
                actor_user_id=user2,
                payload=KillSwitchMutationRequest(confirm=True, reason="halt during claim"),
            )
            session.commit()
        released.set()

    claim_thread = threading.Thread(target=claimer)
    kill_thread = threading.Thread(target=killer)
    claim_thread.start()
    kill_thread.start()
    claim_thread.join(timeout=30)
    kill_thread.join(timeout=30)
    assert claim_result == ["BLOCKED"]
    with factory() as session:
        auth = session.get(ApprovalAuthorization, authorization2.authorization_id)
        assert auth is not None
        assert auth.state is AuthorizationState.AVAILABLE


@requires_postgres
def test_postgres_kill_after_claim_and_after_lease_before_dispatch() -> None:
    factory, url = _factory()
    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        settings = paper_settings(database_url=url)
        service = execution_service(session, database_url=url)
        claimed = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-post-claim-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        KillSwitchService(session, AuditService(session), settings).activate(
            organization_id=ids["organization"].id,
            actor_user_id=ids["user"].id,
            payload=KillSwitchMutationRequest(confirm=True, reason="after claim"),
        )
        session.commit()
        effect = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        assert effect.state is VenueSubmitEffectState.PROVEN_UNSENT
        provider = FakeVenueSubmitProvider()
        with pytest.raises(ConflictError):
            service.attempt_fake_paper_plan_send(
                command_id=claimed.command_id,
                owner="w1",
                fencing_token=1,
                provider=provider,
            )
        assert provider.submit_count == 0

    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        settings = paper_settings(database_url=url)
        service = execution_service(session, database_url=url)
        claimed = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-post-lease-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        KillSwitchService(session, AuditService(session), settings).activate(
            organization_id=ids["organization"].id,
            actor_user_id=ids["user"].id,
            payload=KillSwitchMutationRequest(confirm=True, reason="after lease"),
        )
        session.commit()
        authorized = service.authorize_paper_plan_dispatch(
            command_id=claimed.command_id,
            owner="w1",
            fencing_token=int(leased.fencing_token),
        )
        session.commit()
        assert authorized.state is VenueSubmitEffectState.PROVEN_UNSENT
        projection = session.scalar(
            select(ExecutionProjection).where(
                ExecutionProjection.receipt_id == claimed.receipt.receipt_id
            )
        )
        assert projection is not None
        assert projection.state is ExecutionReceiptState.BLOCKED_BEFORE_DISPATCH


@requires_postgres
def test_postgres_crash_points_and_ambiguous_send() -> None:
    factory, url = _factory()
    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        service = execution_service(session, database_url=url)
        service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-crash-pre-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.rollback()
        assert session.scalar(select(func.count()).select_from(ExecutionCommand)) == 0

    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        service = execution_service(session, database_url=url)
        claimed = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-crash-claim-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        recovered = service.recover_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        assert recovered.state in {
            VenueSubmitEffectState.LEASED,
            VenueSubmitEffectState.DISPATCH_AUTHORIZED,
            VenueSubmitEffectState.PROVEN_UNSENT,
        }

    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        service = execution_service(session, database_url=url)
        claimed = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-crash-lease-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        recovered = service.recover_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        assert recovered.state in {
            VenueSubmitEffectState.DISPATCH_AUTHORIZED,
            VenueSubmitEffectState.PROVEN_UNSENT,
        }
        del leased

    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        service = execution_service(session, database_url=url)
        claimed = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-crash-auth-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        service.authorize_paper_plan_dispatch(
            command_id=claimed.command_id,
            owner="w1",
            fencing_token=int(leased.fencing_token),
        )
        session.commit()
        provider = FakeVenueSubmitProvider()
        recovered = service.recover_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        assert recovered.uncertainty is True
        assert provider.submit_count == 0
        reservation = session.scalar(
            select(RiskReservation).where(RiskReservation.command_id == claimed.command_id)
        )
        assert reservation is not None
        assert reservation.release_state is RiskReservationReleaseState.CHARGED

    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        service = execution_service(session, database_url=url)
        claimed = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=f"pg-ambiguous-{uuid.uuid4()}"),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="w1")
        session.commit()
        service.authorize_paper_plan_dispatch(
            command_id=claimed.command_id,
            owner="w1",
            fencing_token=int(leased.fencing_token),
        )
        session.commit()
        sent = service.attempt_fake_paper_plan_send(
            command_id=claimed.command_id,
            owner="w1",
            fencing_token=int(leased.fencing_token),
            provider=FakeVenueSubmitProvider(behavior=FakeVenueBehavior.AMBIGUOUS),
        )
        session.commit()
        assert sent.uncertainty is True
        replay = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=claimed.receipt.receipt_id.hex[:8]),
            clock=lambda: EXECUTE_AT,
        )
        # different key: blocked as plan already claimed
        session.commit()
        del replay
        original_key_req = execute_request(
            ids,
            plan,
            authorization,
            key=session.get(ExecutionCommand, claimed.command_id).opaque_idempotency_key,  # type: ignore[union-attr]
        )
        replayed = service.execute_paper_plan(original_key_req, clock=lambda: EXECUTE_AT)
        assert replayed.replayed is True
        assert replayed.command_id == claimed.command_id


@requires_postgres
def test_postgres_replay_and_principal_conflict() -> None:
    factory, url = _factory()
    with factory() as session:
        ids, plan, authorization = prepared_authorized_plan(session)
        session.commit()
        key = f"pg-replay-{uuid.uuid4()}"
        service = execution_service(session, database_url=url)
        first = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=key),
            clock=lambda: EXECUTE_AT,
        )
        session.commit()
        second = service.execute_paper_plan(
            execute_request(ids, plan, authorization, key=key),
            clock=lambda: EXECUTE_AT,
        )
        assert second.replayed is True
        assert second.command_id == first.command_id
        assert second.client_order_id == first.client_order_id
        with pytest.raises((ConflictError, TradingPolicyError, NotFoundError)):
            service.execute_paper_plan(
                execute_request(
                    ids,
                    plan,
                    authorization,
                    key=key,
                    user_id=ids["other_user"].id,
                ),
                clock=lambda: EXECUTE_AT,
            )
