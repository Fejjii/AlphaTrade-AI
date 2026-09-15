"""Phase 1 slices 7-9: idempotency, claim, reservation, epoch, receipt, effect."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PersistencePolicyError, TradingPolicyError
from app.core.operation_policy import operation_scope
from app.db.models import (
    AccountRiskAccountingState,
    ApprovalAuthorization,
    ExecutionCommand,
    ExecutionIdempotencyBinding,
    ExecutionProjection,
    ExecutionTransition,
    PlanEntryExecutionClaim,
    RiskReservation,
    VenueSubmitEffect,
)
from app.providers.execution.fake_venue import FakeVenueBehavior, FakeVenueSubmitProvider
from app.schemas.agent import Intent, IntentDecision, OperationClass, RequestedAction
from app.schemas.execution_protocol import (
    ExecutionCommandOutcome,
    ExecutionReceiptState,
    RiskReservationReleaseState,
    VenueSubmitEffectState,
)
from app.schemas.risk import KillSwitchMutationRequest
from app.schemas.trade_plan import AuthorizationState
from app.services.audit_service import AuditService
from app.services.execution_claim import conservative_reservation
from app.services.execution_client_order_id import derive_entry_client_order_id
from app.services.execution_transitions import rebuild_projection_from_transitions
from app.services.risk.kill_switch import KillSwitchService
from tests.support.phase1_plan_fixtures import (
    EXECUTE_AT,
    approve_plan,
    execute_request,
    execution_service,
    persist_plan,
    plan_request,
    prepared_authorized_plan,
    seed_support,
    sqlite_session,
)


@pytest.fixture
def session() -> Iterator[Session]:
    yield from sqlite_session()


def _approve_decision(organization_id: object) -> IntentDecision:
    return IntentDecision(
        intent=Intent.APPROVE,
        operation_class=OperationClass.APPROVAL,
        organization_id=organization_id,  # type: ignore[arg-type]
        requested_action=RequestedAction.APPROVE,
    )


def test_execute_paper_plan_creates_stable_identities(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    result = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="entry-key-1"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    assert result.replayed is False
    assert result.outcome is ExecutionCommandOutcome.ALLOW
    assert result.effect is not None
    assert result.reservation is not None
    assert result.projection.state is ExecutionReceiptState.SUBMITTING
    assert result.client_order_id == derive_entry_client_order_id(
        account_id=plan.account_id,
        revision_id=plan.revision_id,
        canonical_payload_hash=result.canonical_payload_hash,
    )
    assert session.scalar(select(func.count()).select_from(ExecutionCommand)) == 1
    assert session.scalar(select(func.count()).select_from(PlanEntryExecutionClaim)) == 1
    assert session.scalar(select(func.count()).select_from(VenueSubmitEffect)) == 1
    auth = session.get(ApprovalAuthorization, authorization.authorization_id)
    assert auth is not None
    assert auth.state is AuthorizationState.CONSUMED
    assert auth.consumed_by_execution_command_id == result.command_id


def test_approve_does_not_create_execution_command(session: Session) -> None:
    ids = seed_support(session)
    plan = persist_plan(session, ids)
    approve_plan(session, ids, plan)
    session.commit()
    assert session.scalar(select(func.count()).select_from(ExecutionCommand)) == 0
    assert session.scalar(select(func.count()).select_from(PlanEntryExecutionClaim)) == 0
    assert session.scalar(select(func.count()).select_from(VenueSubmitEffect)) == 0


def test_approve_intent_cannot_execute(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    org_id = ids["organization"].id
    with operation_scope(_approve_decision(org_id)), pytest.raises(TradingPolicyError):
        service.execute_paper_plan(
            execute_request(ids, plan, authorization, key="blocked-by-approve"),
            clock=lambda: EXECUTE_AT,
        )
    auth = session.get(ApprovalAuthorization, authorization.authorization_id)
    assert auth is not None
    assert auth.state is AuthorizationState.AVAILABLE


def test_replay_same_key_and_payload_returns_stable_receipt(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    first = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="replay-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    second = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="replay-key"),
        clock=lambda: EXECUTE_AT,
    )
    assert second.replayed is True
    assert second.command_id == first.command_id
    assert second.receipt.receipt_id == first.receipt.receipt_id
    assert second.client_order_id == first.client_order_id
    assert session.scalar(select(func.count()).select_from(ExecutionCommand)) == 1
    assert session.scalar(select(func.count()).select_from(ApprovalAuthorization)) == 1


def test_same_key_different_payload_conflicts(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="payload-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    other = persist_plan(
        session, ids, plan_request(ids, quantity={"value": "3", "unit": "CONTRACTS"})
    )
    other_auth = approve_plan(session, ids, other)
    with pytest.raises(ConflictError) as exc:
        service.execute_paper_plan(
            execute_request(ids, other, other_auth, key="payload-key"),
            clock=lambda: EXECUTE_AT,
        )
    assert exc.value.details.get("reason") == "idempotency_payload_conflict"


def test_same_key_different_principal_is_rejected(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="principal-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    with pytest.raises((ConflictError, TradingPolicyError, NotFoundError)):
        service.execute_paper_plan(
            execute_request(
                ids,
                plan,
                authorization,
                key="principal-key",
                user_id=ids["other_user"].id,
            ),
            clock=lambda: EXECUTE_AT,
        )


def test_same_key_different_account_conflicts(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="account-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    with pytest.raises(ConflictError) as exc:
        service.execute_paper_plan(
            execute_request(
                ids,
                plan,
                authorization,
                key="account-key",
                account_id=ids["account_two"].id,
            ),
            clock=lambda: EXECUTE_AT,
        )
    assert exc.value.details.get("reason") == "idempotency_account_conflict"


def test_different_keys_same_plan_do_not_duplicate_claim(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    first = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="plan-key-a"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    second = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="plan-key-b"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    assert first.outcome is ExecutionCommandOutcome.ALLOW
    assert second.outcome is ExecutionCommandOutcome.BLOCKED
    assert second.blocked_reason_code in {
        "plan_entry_already_claimed",
        "authorization_unavailable",
    }
    assert session.scalar(select(func.count()).select_from(PlanEntryExecutionClaim)) == 1
    assert session.scalar(select(func.count()).select_from(VenueSubmitEffect)) == 1
    auth = session.get(ApprovalAuthorization, authorization.authorization_id)
    assert auth is not None
    assert auth.consumed_by_execution_command_id == first.command_id


def test_kill_switch_before_claim_blocks_without_consumption(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    kill = KillSwitchService(session, AuditService(session), execution_service(session)._settings)
    kill.activate(
        organization_id=ids["organization"].id,
        actor_user_id=ids["user"].id,
        payload=KillSwitchMutationRequest(confirm=True, reason="halt entries"),
    )
    session.commit()
    result = execution_service(session).execute_paper_plan(
        execute_request(ids, plan, authorization, key="killed-before"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    assert result.outcome is ExecutionCommandOutcome.BLOCKED
    assert result.blocked_reason_code == "safety_epoch_blocking"
    assert result.effect is None
    assert result.reservation is None
    auth = session.get(ApprovalAuthorization, authorization.authorization_id)
    assert auth is not None
    assert auth.state is AuthorizationState.AVAILABLE
    replay = execution_service(session).execute_paper_plan(
        execute_request(ids, plan, authorization, key="killed-before"),
        clock=lambda: EXECUTE_AT,
    )
    assert replay.replayed is True
    assert replay.outcome is ExecutionCommandOutcome.BLOCKED


def test_serializable_capacity_blocks_second_command(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    intent = conservative_reservation(plan)
    session.add(
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
            max_symbol_notional=intent.pending_notional,
            daily_locked=False,
            exposure_unit=intent.exposure_unit,
            version=1,
        )
    )
    other = persist_plan(
        session, ids, plan_request(ids, quantity={"value": "3", "unit": "CONTRACTS"})
    )
    other_auth = approve_plan(session, ids, other)
    session.commit()
    service = execution_service(session)
    first = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="cap-a"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    second = service.execute_paper_plan(
        execute_request(ids, other, other_auth, key="cap-b"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    assert first.outcome is ExecutionCommandOutcome.ALLOW
    assert second.outcome is ExecutionCommandOutcome.BLOCKED
    assert second.blocked_reason_code == "insufficient_total_exposure"
    assert session.scalar(select(func.count()).select_from(RiskReservation)) == 1


def test_dispatch_barriers_and_fake_ack(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="dispatch-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="worker-1")
    session.commit()
    assert leased.state is VenueSubmitEffectState.LEASED
    authorized = service.authorize_paper_plan_dispatch(
        command_id=claimed.command_id,
        owner="worker-1",
        fencing_token=int(leased.fencing_token),
    )
    session.commit()
    assert authorized.state is VenueSubmitEffectState.DISPATCH_AUTHORIZED
    provider = FakeVenueSubmitProvider(behavior=FakeVenueBehavior.ACCEPT)
    sent = service.attempt_fake_paper_plan_send(
        command_id=claimed.command_id,
        owner="worker-1",
        fencing_token=int(leased.fencing_token),
        provider=provider,
    )
    session.commit()
    assert sent.reconciliation_disposition == "ACCEPTED"
    assert provider.submit_count == 1
    projection = session.scalar(
        select(ExecutionProjection).where(
            ExecutionProjection.receipt_id == claimed.receipt.receipt_id
        )
    )
    assert projection is not None
    assert projection.state is ExecutionReceiptState.ACKNOWLEDGED


def test_kill_after_claim_before_lease_blocks_unsent(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="lease-kill"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    KillSwitchService(session, AuditService(session), service._settings).activate(
        organization_id=ids["organization"].id,
        actor_user_id=ids["user"].id,
        payload=KillSwitchMutationRequest(confirm=True, reason="stop before lease"),
    )
    session.commit()
    provider = FakeVenueSubmitProvider()
    effect = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="worker-1")
    session.commit()
    assert effect.state is VenueSubmitEffectState.PROVEN_UNSENT
    with pytest.raises(ConflictError):
        service.attempt_fake_paper_plan_send(
            command_id=claimed.command_id,
            owner="worker-1",
            fencing_token=1,
            provider=provider,
        )
    assert provider.submit_count == 0
    reservation = session.scalar(
        select(RiskReservation).where(RiskReservation.command_id == claimed.command_id)
    )
    assert reservation is not None
    assert reservation.release_state is RiskReservationReleaseState.RELEASED
    auth = session.get(ApprovalAuthorization, authorization.authorization_id)
    assert auth is not None
    assert auth.state is AuthorizationState.CONSUMED


def test_kill_after_lease_before_dispatch_authorization(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="auth-kill"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="worker-1")
    session.commit()
    KillSwitchService(session, AuditService(session), service._settings).activate(
        organization_id=ids["organization"].id,
        actor_user_id=ids["user"].id,
        payload=KillSwitchMutationRequest(confirm=True, reason="stop before POST"),
    )
    session.commit()
    authorized = service.authorize_paper_plan_dispatch(
        command_id=claimed.command_id,
        owner="worker-1",
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


def test_crash_before_claim_commit_leaves_key_unused(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    session.commit()
    service = execution_service(session)
    service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="crash-before-commit"),
        clock=lambda: EXECUTE_AT,
    )
    session.rollback()
    assert session.scalar(select(func.count()).select_from(ExecutionCommand)) == 0
    assert session.scalar(select(func.count()).select_from(ExecutionIdempotencyBinding)) == 0
    auth = session.get(ApprovalAuthorization, authorization.authorization_id)
    assert auth is not None
    assert auth.state is AuthorizationState.AVAILABLE


def test_crash_after_dispatch_authorization_does_not_blind_resubmit(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="crash-after-auth"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="worker-1")
    session.commit()
    service.authorize_paper_plan_dispatch(
        command_id=claimed.command_id,
        owner="worker-1",
        fencing_token=int(leased.fencing_token),
    )
    session.commit()
    provider = FakeVenueSubmitProvider()
    recovered = service.recover_paper_plan_effect(command_id=claimed.command_id, owner="worker-1")
    session.commit()
    assert recovered.uncertainty is True
    assert recovered.state is VenueSubmitEffectState.SEND_AMBIGUOUS
    assert provider.submit_count == 0
    reservation = session.scalar(
        select(RiskReservation).where(RiskReservation.command_id == claimed.command_id)
    )
    assert reservation is not None
    assert reservation.release_state is RiskReservationReleaseState.CHARGED


def test_ambiguous_send_preserves_reservation(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="ambiguous"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    leased = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="worker-1")
    session.commit()
    service.authorize_paper_plan_dispatch(
        command_id=claimed.command_id,
        owner=leased.lease_owner or "worker-1",
        fencing_token=int(leased.fencing_token),
    )
    session.commit()
    provider = FakeVenueSubmitProvider(behavior=FakeVenueBehavior.AMBIGUOUS)
    sent = service.attempt_fake_paper_plan_send(
        command_id=claimed.command_id,
        owner="worker-1",
        fencing_token=int(leased.fencing_token),
        provider=provider,
    )
    session.commit()
    assert sent.uncertainty is True
    reservation = session.scalar(
        select(RiskReservation).where(RiskReservation.command_id == claimed.command_id)
    )
    assert reservation is not None
    assert reservation.release_state is RiskReservationReleaseState.CHARGED


def test_unique_fill_converts_reservation_and_appends_transition(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="fill-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    service.apply_paper_plan_fill(
        command_id=claimed.command_id,
        fill_quantity=Decimal("1"),
        fill_price=Decimal("100.10"),
        source_identity="fill-1",
    )
    session.commit()
    projection = session.scalar(
        select(ExecutionProjection).where(
            ExecutionProjection.receipt_id == claimed.receipt.receipt_id
        )
    )
    assert projection is not None
    assert projection.state is ExecutionReceiptState.PARTIALLY_FILLED
    assert projection.filled_quantity == Decimal("1")
    from app.db.models import ExecutionReceipt

    receipt = session.get(ExecutionReceipt, claimed.receipt.receipt_id)
    assert receipt is not None
    transitions = list(
        session.scalars(
            select(ExecutionTransition)
            .where(ExecutionTransition.receipt_id == claimed.receipt.receipt_id)
            .order_by(ExecutionTransition.sequence)
        )
    )
    rebuilt = rebuild_projection_from_transitions(
        receipt,
        transitions,
        initial_remaining=Decimal("2"),
        quantity_unit="CONTRACTS",
    )
    assert rebuilt["state"] is ExecutionReceiptState.PARTIALLY_FILLED
    assert rebuilt["filled_quantity"] == Decimal("1")
    reservation = session.scalar(
        select(RiskReservation).where(RiskReservation.command_id == claimed.command_id)
    )
    assert reservation is not None
    assert reservation.release_state is RiskReservationReleaseState.PARTIALLY_RELEASED
    assert reservation.remaining_reserved_notional < reservation.pending_order_exposure


def test_readonly_cannot_claim(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    decision = IntentDecision(
        intent=Intent.MARKET_ANALYSIS,
        operation_class=OperationClass.READ_ONLY,
        organization_id=ids["organization"].id,
        requested_action=RequestedAction.NONE,
    )
    with operation_scope(decision), pytest.raises(PersistencePolicyError):
        service.execute_paper_plan(
            execute_request(ids, plan, authorization, key="readonly-key"),
            clock=lambda: EXECUTE_AT,
        )


def test_stale_worker_cannot_dispatch_after_lease_loss(session: Session) -> None:
    ids, plan, authorization = prepared_authorized_plan(session)
    service = execution_service(session)
    claimed = service.execute_paper_plan(
        execute_request(ids, plan, authorization, key="fence-key"),
        clock=lambda: EXECUTE_AT,
    )
    session.commit()
    first = service.lease_paper_plan_effect(
        command_id=claimed.command_id, owner="worker-old", lease_seconds=0
    )
    first_token = int(first.fencing_token)
    session.commit()
    second = service.lease_paper_plan_effect(command_id=claimed.command_id, owner="worker-new")
    session.commit()
    with pytest.raises(ConflictError):
        service.authorize_paper_plan_dispatch(
            command_id=claimed.command_id,
            owner="worker-old",
            fencing_token=first_token,
        )
    authorized = service.authorize_paper_plan_dispatch(
        command_id=claimed.command_id,
        owner="worker-new",
        fencing_token=int(second.fencing_token),
    )
    assert authorized.state is VenueSubmitEffectState.DISPATCH_AUTHORIZED
    assert int(second.fencing_token) > first_token
