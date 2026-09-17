"""PostgreSQL TelegramSecurityStore adapter: replay, nonce CAS, outbox claims."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.deployment_safety import deployment_posture
from app.persistence.composition import (
    build_postgres_telegram_security_protocol,
    build_postgres_telegram_security_store,
)
from app.telegram_security.actions import APPROVE_EXECUTES, TelegramRemoteAction
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import (
    ActionNonce,
    ActionOutcome,
    ActionReceiptState,
    BindingState,
    ChatType,
    NonceState,
    OutboxKind,
    OutboxRecord,
    OutboxState,
)
from app.telegram_security.errors import (
    TelegramInteractionDisabledError,
    TelegramSecurityError,
    TelegramSecurityReason,
)
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.rate_limit import RateLimitPolicy
from app.telegram_security.transport import FakeTelegramTransport
from tests.support.postgres_persistence import persistence_session_factory, requires_postgres
from tests.support.telegram_security import (
    ACCOUNT,
    BOT,
    CHAT,
    ORG,
    OTHER_ACCOUNT,
    OTHER_ORG,
    OTHER_USER,
    RESOURCE,
    REVISION,
    TG_USER,
    USER,
    TokenSeq,
    callback_identity,
    enroll,
    inbound_callback,
    inbound_message,
    message_identity,
    payload,
)


def _protocol(
    factory: sessionmaker[Session] | None = None,
    *,
    clock: FrozenClock | None = None,
    transport: FakeTelegramTransport | None = None,
    rate_limit_policy: RateLimitPolicy | None = None,
    enabled: bool = True,
    lease_owner: str = "telegram-security-protocol",
    outbox_lease: timedelta = timedelta(seconds=30),
) -> TelegramSecurityProtocol:
    return build_postgres_telegram_security_protocol(
        factory or persistence_session_factory(),
        enabled=enabled,
        clock=clock or FrozenClock(),
        transport=transport,
        token_factory=TokenSeq(),
        rate_limit_policy=rate_limit_policy,
        lease_owner=lease_owner,
        outbox_lease=outbox_lease,
    )


@requires_postgres
def test_postgres_telegram_disabled_by_default() -> None:
    settings = Settings()
    assert settings.telegram_interaction_enabled is False
    assert settings.watcher_orchestration_enabled is False
    assert settings.real_trading_enabled is False
    posture = deployment_posture(settings)
    assert posture["telegram_interaction_enabled"] is False
    protocol = _protocol(enabled=False)
    with pytest.raises(TelegramInteractionDisabledError):
        protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)


@requires_postgres
def test_postgres_private_enrollment_and_approve_intent_only() -> None:
    protocol = _protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    completed = protocol.complete_enrollment(
        token=started.token,
        identity=message_identity(),
        inbound=inbound_message(),
    )
    binding = completed.binding
    assert binding.state is BindingState.VERIFIED
    assert binding.chat_type is ChatType.PRIVATE
    assert binding.organization_id == ORG
    assert binding.user_id == USER
    issued = protocol.issue_action_nonce(binding_id=binding.binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert outcome.receipt.state is ActionReceiptState.APPLIED
    assert outcome.authorization_intent is not None
    assert outcome.authorization_intent.executes is False
    assert outcome.authorization_intent.execution_attempted is False
    assert outcome.authorization_intent.execution_entry_path is None
    assert outcome.executed is False
    assert APPROVE_EXECUTES is False
    assert protocol.execution_attempt_count == 0
    assert TelegramRemoteAction.CLOSE not in binding.allowed_actions


@requires_postgres
def test_postgres_same_enrollment_update_exact_replay() -> None:
    protocol = _protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity()
    first = protocol.complete_enrollment(
        token=started.token, identity=identity, inbound=inbound_message()
    )
    second = protocol.complete_enrollment(
        token=started.token, identity=identity, inbound=inbound_message()
    )
    assert second.binding.binding_id == first.binding.binding_id
    assert second.challenge.challenge_id == first.challenge.challenge_id


@requires_postgres
def test_postgres_same_enrollment_update_conflicting_replay() -> None:
    protocol = _protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity(update_id=13, message_id="msg-original")
    protocol.complete_enrollment(token=started.token, identity=identity, inbound=inbound_message())
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=identity.model_copy(update={"message_id": "msg-changed"}),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


@requires_postgres
def test_postgres_changed_enrollment_chat_type_rejected() -> None:
    protocol = _protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity(update_id=14)
    protocol.complete_enrollment(token=started.token, identity=identity, inbound=inbound_message())
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=identity.model_copy(update={"chat_type": ChatType.GROUP}),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


@requires_postgres
def test_postgres_same_callback_exact_replay() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    identity = callback_identity()
    first = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    second = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert second.replayed is True
    assert second.receipt.receipt_id == first.receipt.receipt_id
    assert second.authorization_intent is not None
    assert first.authorization_intent is not None
    assert second.authorization_intent.intent_id == first.authorization_intent.intent_id


@requires_postgres
def test_postgres_same_callback_conflicting_replay() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    identity = callback_identity(callback_query_id="cb-payload-conflict")
    protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=identity,
            nonce_token=issued.token,
            presented_payload=payload(content_hash="c" * 64),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


@requires_postgres
def test_postgres_same_callback_id_different_update_id_rejected() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    first_identity = callback_identity(update_id=46, callback_query_id="cb-update-conflict")
    protocol.receive_callback(
        identity=first_identity,
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.STATUS),
        inbound=inbound_callback(),
    )
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=first_identity.model_copy(update={"update_id": 47}),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.STATUS),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


@requires_postgres
def test_postgres_same_update_id_different_callback_id_rejected() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    protocol.receive_callback(
        identity=callback_identity(update_id=44, callback_query_id="cb-dup"),
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.STATUS),
        inbound=inbound_callback(),
    )
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=callback_identity(update_id=44, callback_query_id="cb-other"),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.STATUS),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


@requires_postgres
def test_postgres_changed_callback_chat_type_rejected() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.EXPLAIN)
    )
    identity = callback_identity(update_id=48, callback_query_id="cb-chat-type-conflict")
    protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
        inbound=inbound_callback(),
    )
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=identity.model_copy(update={"chat_type": ChatType.GROUP}),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


@requires_postgres
def test_postgres_organization_user_account_resource_revision_mismatch() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    org = protocol.receive_callback(
        identity=callback_identity(update_id=21, callback_query_id="cb-org"),
        nonce_token=issued.token,
        presented_payload=payload(organization_id=OTHER_ORG),
        inbound=inbound_callback(),
    )
    assert org.reason_code == TelegramSecurityReason.CROSS_ORGANIZATION.value
    user = protocol.receive_callback(
        identity=callback_identity(update_id=22, callback_query_id="cb-user"),
        nonce_token=issued.token,
        presented_payload=payload(user_id=OTHER_USER),
        inbound=inbound_callback(),
    )
    assert user.reason_code == TelegramSecurityReason.CROSS_USER.value
    account = protocol.receive_callback(
        identity=callback_identity(update_id=23, callback_query_id="cb-account"),
        nonce_token=issued.token,
        presented_payload=payload(account_id=OTHER_ACCOUNT),
        inbound=inbound_callback(),
    )
    assert account.reason_code == TelegramSecurityReason.CROSS_ACCOUNT.value
    resource = protocol.receive_callback(
        identity=callback_identity(update_id=24, callback_query_id="cb-resource"),
        nonce_token=issued.token,
        presented_payload=payload().model_copy(update={"resource_id": uuid4()}),
        inbound=inbound_callback(),
    )
    assert resource.reason_code == TelegramSecurityReason.PAYLOAD_MISMATCH.value
    revision = protocol.receive_callback(
        identity=callback_identity(update_id=25, callback_query_id="cb-revision"),
        nonce_token=issued.token,
        presented_payload=payload().model_copy(update={"revision_id": uuid4()}),
        inbound=inbound_callback(),
    )
    assert revision.reason_code == TelegramSecurityReason.PAYLOAD_MISMATCH.value
    stored = protocol.store.get_nonce_by_hash(issued.nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.ISSUED


@requires_postgres
def test_postgres_expired_nonce_rejected() -> None:
    clock = FrozenClock()
    protocol = _protocol(clock=clock)
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    clock.advance(timedelta(minutes=11))
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert outcome.reason_code == TelegramSecurityReason.NONCE_EXPIRED.value
    stored = protocol.store.get_nonce_by_hash(issued.nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.EXPIRED


@requires_postgres
def test_postgres_nonce_cas_exactly_one_consumer() -> None:
    factory = persistence_session_factory()
    store = build_postgres_telegram_security_store(factory)
    clock = FrozenClock()
    nonce = ActionNonce(
        nonce_id=uuid4(),
        nonce_hash="a" * 64,
        organization_id=ORG,
        user_id=USER,
        account_id=ACCOUNT,
        telegram_user_id=TG_USER,
        chat_id=CHAT,
        bot_id=BOT,
        binding_id=uuid4(),
        action=TelegramRemoteAction.APPROVE,
        resource_type="trade_plan_revision",
        resource_id=RESOURCE,
        revision_id=REVISION,
        content_hash="b" * 64,
        payload_hash="c" * 64,
        state=NonceState.ISSUED,
        expires_at=clock.now() + timedelta(minutes=10),
        created_at=clock.now(),
    )
    store.save_nonce(nonce)
    barrier = threading.Barrier(2)
    winners: list[bool] = []
    lock = threading.Lock()

    def consume() -> None:
        barrier.wait(timeout=20)
        updated = nonce.model_copy(
            update={
                "state": NonceState.CONSUMED,
                "consumed_at": clock.now(),
                "consumed_by_receipt_id": uuid4(),
            }
        )
        won = store.cas_nonce(nonce_hash=nonce.nonce_hash, expected=nonce, updated=updated)
        with lock:
            winners.append(won)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(consume), pool.submit(consume)]
        for future in futures:
            future.result(timeout=30)
    assert winners.count(True) == 1
    assert winners.count(False) == 1
    stored = store.get_nonce_by_hash(nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.CONSUMED


@requires_postgres
def test_postgres_concurrent_callback_nonce_one_consumer() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    barrier = threading.Barrier(2)
    outcomes: list[ActionOutcome] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(update_id: int, callback_id: str) -> None:
        barrier.wait(timeout=20)
        try:
            result = protocol.receive_callback(
                identity=callback_identity(update_id=update_id, callback_query_id=callback_id),
                nonce_token=issued.token,
                presented_payload=payload(),
                inbound=inbound_callback(),
            )
            with lock:
                outcomes.append(result)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, 10, "cb-1"),
            pool.submit(worker, 11, "cb-2"),
        ]
        for future in futures:
            future.result(timeout=30)
    assert errors == []
    applied = [item for item in outcomes if item.receipt.state is ActionReceiptState.APPLIED]
    used = [
        item for item in outcomes if item.reason_code == TelegramSecurityReason.NONCE_USED.value
    ]
    assert len(applied) == 1
    assert len(used) == 1
    stored = protocol.store.get_nonce_by_hash(issued.nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.CONSUMED


@requires_postgres
def test_postgres_exact_replay_does_not_consume_rate_limit() -> None:
    protocol = _protocol(
        rate_limit_policy=RateLimitPolicy(callback_per_user=2, callback_per_chat=2)
    )
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    identity = callback_identity(update_id=45, callback_query_id="cb-rate-replay")
    first = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    for _ in range(5):
        replay = protocol.receive_callback(
            identity=identity,
            nonce_token=issued.token,
            presented_payload=payload(),
            inbound=inbound_callback(),
        )
        assert replay.replayed is True
        assert replay.receipt.receipt_id == first.receipt.receipt_id


@requires_postgres
def test_postgres_duplicate_outbox_idempotency_converges() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    first = protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="hello",
        idempotency_key="dup-outbox",
    )
    second = protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="hello",
        idempotency_key="dup-outbox",
    )
    assert second.outbox_id == first.outbox_id


@requires_postgres
def test_postgres_outbox_conflicting_idempotency_fails_closed() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="hello",
        idempotency_key="conflict-outbox",
    )
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.enqueue_outbound(
            organization_id=ORG,
            user_id=USER,
            binding_id=binding_id,
            bot_id=BOT,
            chat_id=CHAT,
            text="different",
            idempotency_key="conflict-outbox",
        )
    assert exc.value.reason is TelegramSecurityReason.OUTBOX_CONFLICT


@requires_postgres
def test_postgres_delivery_claim_concurrency_one_owner() -> None:
    factory = persistence_session_factory()
    store = build_postgres_telegram_security_store(factory)
    clock = FrozenClock()
    row = OutboxRecord(
        outbox_id=uuid4(),
        organization_id=ORG,
        user_id=USER,
        binding_id=None,
        bot_id=BOT,
        chat_id=CHAT,
        idempotency_key="claim-1",
        kind=OutboxKind.PRIVATE_MESSAGE,
        text="claim me",
        state=OutboxState.PENDING,
        attempt=0,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    store.save_outbox(row)
    barrier = threading.Barrier(2)
    claimed: list[list[UUID]] = []
    lock = threading.Lock()

    def worker(owner: str) -> None:
        barrier.wait(timeout=20)
        batch = store.claim_outbox_batch(
            now=clock.now(),
            limit=1,
            lease_owner=owner,
            lease_for=timedelta(seconds=30),
        )
        with lock:
            claimed.append([item.outbox_id for item in batch])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, "worker-a"), pool.submit(worker, "worker-b")]
        for future in futures:
            future.result(timeout=30)
    winners = [batch for batch in claimed if batch]
    empties = [batch for batch in claimed if not batch]
    assert len(winners) == 1
    assert len(empties) == 1
    stored = store.get_outbox(row.outbox_id)
    assert stored is not None
    assert stored.state is OutboxState.CLAIMED
    assert stored.lease_owner in {"worker-a", "worker-b"}


@requires_postgres
def test_postgres_outbox_crash_after_claim_then_safe_recovery() -> None:
    clock = FrozenClock()
    transport = FakeTelegramTransport()
    protocol = _protocol(clock=clock, transport=transport, outbox_lease=timedelta(seconds=30))
    _, binding_id = enroll(protocol)
    protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="recover me",
        idempotency_key="crash-outbox",
    )
    claimed = protocol.store.claim_outbox_batch(
        now=clock.now(),
        limit=1,
        lease_owner="crashed-worker",
        lease_for=timedelta(seconds=30),
    )
    assert len(claimed) == 1
    assert claimed[0].state is OutboxState.CLAIMED
    clock.advance(timedelta(seconds=31))
    delivered = protocol.deliver_pending()
    assert len(delivered) == 1
    assert delivered[0].accepted is True
    assert delivered[0].outbox.state is OutboxState.SENT
    assert transport.send_count == 1


@requires_postgres
def test_postgres_delivery_acknowledgement_idempotency() -> None:
    transport = FakeTelegramTransport()
    protocol = _protocol(transport=transport)
    _, binding_id = enroll(protocol)
    protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="ack me",
        idempotency_key="ack-1",
    )
    delivered = protocol.deliver_pending()
    message_id = delivered[0].transport_message_id
    assert message_id is not None
    acked = protocol.acknowledge_delivery(
        outbox_id=delivered[0].outbox.outbox_id,
        transport_message_id=message_id,
    )
    assert acked.state is OutboxState.ACKNOWLEDGED
    replay = protocol.acknowledge_delivery(
        outbox_id=delivered[0].outbox.outbox_id,
        transport_message_id=message_id,
    )
    assert replay.outbox_id == acked.outbox_id
    assert replay.state is OutboxState.ACKNOWLEDGED


@requires_postgres
def test_postgres_close_unavailable_and_unknown_action() -> None:
    protocol = _protocol()
    _, binding_id = enroll(protocol)
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.issue_action_nonce(
            binding_id=binding_id,
            payload=payload(action=TelegramRemoteAction.CLOSE),
        )
    assert exc.value.reason is TelegramSecurityReason.CLOSE_UNAVAILABLE
    from app.telegram_security.actions import parse_remote_action

    with pytest.raises(TelegramSecurityError) as unknown:
        parse_remote_action("EXECUTE_PAPER_PLAN")
    assert unknown.value.reason is TelegramSecurityReason.UNKNOWN_ACTION
