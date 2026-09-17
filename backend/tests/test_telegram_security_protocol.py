"""Isolated Telegram security protocol — enrollment, identity, nonce, receipts."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.deployment_safety import deployment_posture
from app.telegram_security.actions import (
    ALLOWED_TELEGRAM_UPDATE_TYPES,
    APPROVE_EXECUTES,
    AVAILABLE_TELEGRAM_ACTIONS,
    CLOSE_AVAILABLE,
    MAX_INBOUND_UPDATE_BYTES,
    TELEGRAM_EXECUTION_ENTRY_PATHS,
    TelegramRemoteAction,
    parse_remote_action,
)
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import (
    ActionReceiptState,
    BindingState,
    ChatType,
    EnrollmentChallengeState,
    NonceState,
    OutboxState,
    TelegramInboundUpdate,
)
from app.telegram_security.errors import (
    TelegramInteractionDisabledError,
    TelegramRateLimitedError,
    TelegramSecurityError,
    TelegramSecurityReason,
)
from app.telegram_security.hashing import hash_secret
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.rate_limit import RateLimitPolicy
from app.telegram_security.transport import FakeTelegramBehavior, FakeTelegramTransport
from tests.support.telegram_security import (
    ACCOUNT,
    BOT,
    CHAT,
    ORG,
    OTHER_ACCOUNT,
    OTHER_CHAT,
    OTHER_ORG,
    OTHER_TG_USER,
    OTHER_USER,
    REVISION,
    TG_USER,
    USER,
    callback_identity,
    enabled_protocol,
    enroll,
    inbound_callback,
    inbound_message,
    message_identity,
    payload,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src/app/telegram_security"
FORBIDDEN_SNIPPETS = (
    "app.services.execution",
    "ExecutionService",
    "execute_paper_plan",
    "place_paper_order",
    "app.db.models",
    "alembic",
    "blofin",
    "VenueSubmit",
)


def test_package_does_not_import_execution_or_orm() -> None:
    for path in PACKAGE_ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            assert snippet not in text, f"{path.name} contains {snippet}"


def test_execute_paper_plan_is_outside_telegram_vocabulary() -> None:
    assert not hasattr(TelegramRemoteAction, "EXECUTE_PAPER_PLAN")
    assert "EXECUTE_PAPER_PLAN" not in {item.value for item in TelegramRemoteAction}
    assert TELEGRAM_EXECUTION_ENTRY_PATHS == ()
    with pytest.raises(TelegramSecurityError) as exc:
        parse_remote_action("EXECUTE_PAPER_PLAN")
    assert exc.value.reason is TelegramSecurityReason.UNKNOWN_ACTION


def test_close_is_known_but_unavailable() -> None:
    assert TelegramRemoteAction.CLOSE in TelegramRemoteAction
    assert CLOSE_AVAILABLE is False
    assert TelegramRemoteAction.CLOSE not in AVAILABLE_TELEGRAM_ACTIONS
    with pytest.raises(TelegramSecurityError) as exc:
        parse_remote_action("CLOSE")
    assert exc.value.reason is TelegramSecurityReason.CLOSE_UNAVAILABLE


def test_telegram_interaction_disabled_by_default() -> None:
    settings = Settings()
    assert settings.telegram_interaction_enabled is False
    assert settings.telegram_alerts_enabled is False
    assert settings.automatic_telegram_delivery_enabled is False
    assert settings.real_trading_enabled is False
    posture = deployment_posture(settings)
    assert posture["telegram_interaction_enabled"] is False
    protocol = TelegramSecurityProtocol.in_memory()
    assert protocol.enabled is False
    with pytest.raises(TelegramInteractionDisabledError):
        protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)


def test_valid_enrollment_binds_verified_private_chat() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    assert started.challenge.state is EnrollmentChallengeState.PENDING
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
    assert binding.telegram_user_id == TG_USER
    assert binding.chat_id == CHAT
    assert binding.bot_id == BOT
    assert TelegramRemoteAction.CLOSE not in binding.allowed_actions
    assert TelegramRemoteAction.APPROVE in binding.allowed_actions


def test_invalid_enrollment_group_chat_rejected() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=message_identity(chat_type=ChatType.GROUP, update_id=2),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.CHAT_NOT_PRIVATE


def test_invalid_enrollment_chat_id_alone_is_not_enrollment() -> None:
    protocol = enabled_protocol()
    protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=CHAT,
            identity=message_identity(update_id=3),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.ENROLLMENT_CHAT_ID_ONLY


def test_invalid_enrollment_expired_challenge() -> None:
    clock = FrozenClock()
    protocol = enabled_protocol(clock=clock)
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    clock.advance(timedelta(minutes=16))
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=message_identity(update_id=4),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.ENROLLMENT_EXPIRED


def test_invalid_enrollment_used_nonce_semantics() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    protocol.complete_enrollment(
        token=started.token,
        identity=message_identity(),
        inbound=inbound_message(),
    )
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=message_identity(update_id=5, message_id="msg-2"),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.ENROLLMENT_USED


def test_duplicate_enrollment_delivery_converges() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity()
    first = protocol.complete_enrollment(
        token=started.token,
        identity=identity,
        inbound=inbound_message(),
    )
    second = protocol.complete_enrollment(
        token=started.token,
        identity=identity,
        inbound=inbound_message(),
    )
    assert second.binding.binding_id == first.binding.binding_id
    assert second.challenge.challenge_id == first.challenge.challenge_id


def test_exact_enrollment_replays_bypass_rate_limit() -> None:
    protocol = enabled_protocol(
        rate_limit_policy=RateLimitPolicy(
            callback_per_user=1,
            callback_per_chat=1,
        )
    )
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity(update_id=6, message_id="msg-rate-replay")
    first = protocol.complete_enrollment(
        token=started.token,
        identity=identity,
        inbound=inbound_message(),
    )

    for _ in range(5):
        replay = protocol.complete_enrollment(
            token=started.token,
            identity=identity,
            inbound=inbound_message(),
        )
        assert replay.binding.binding_id == first.binding.binding_id
        assert replay.challenge.challenge_id == first.challenge.challenge_id


def test_wrong_user_callback_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(telegram_user_id=OTHER_TG_USER),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert outcome.receipt.state is ActionReceiptState.REJECTED
    assert outcome.reason_code == TelegramSecurityReason.CROSS_USER.value
    assert outcome.executed is False
    stored = protocol.store.get_nonce_by_hash(issued.nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.ISSUED


def test_wrong_organization_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(organization_id=OTHER_ORG),
        inbound=inbound_callback(),
    )
    assert outcome.reason_code == TelegramSecurityReason.CROSS_ORGANIZATION.value
    assert outcome.receipt.state is ActionReceiptState.REJECTED


def test_wrong_account_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(account_id=OTHER_ACCOUNT),
        inbound=inbound_callback(),
    )
    assert outcome.reason_code == TelegramSecurityReason.CROSS_ACCOUNT.value
    assert outcome.authorization_intent is None


def test_expired_nonce_rejected() -> None:
    clock = FrozenClock()
    protocol = enabled_protocol(clock=clock)
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


def test_used_nonce_replay_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    first = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert first.receipt.state is ActionReceiptState.APPLIED
    replay = protocol.receive_callback(
        identity=callback_identity(update_id=11, callback_query_id="cb-2"),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert replay.reason_code == TelegramSecurityReason.NONCE_USED.value
    assert replay.replayed is False


def test_payload_mutation_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    mutated = payload(content_hash="b" * 64)
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=mutated,
        inbound=inbound_callback(),
    )
    assert outcome.reason_code == TelegramSecurityReason.PAYLOAD_MISMATCH.value
    assert outcome.receipt.state is ActionReceiptState.REJECTED


def test_duplicate_callback_returns_original_receipt() -> None:
    protocol = enabled_protocol()
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
    assert second.state_changed is False
    assert second.receipt.receipt_id == first.receipt.receipt_id
    assert second.receipt.state is ActionReceiptState.APPLIED
    assert second.authorization_intent is not None
    assert second.authorization_intent.intent_id == first.authorization_intent.intent_id


def test_same_update_id_changed_callback_id_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    first = protocol.receive_callback(
        identity=callback_identity(update_id=44, callback_query_id="cb-dup"),
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.STATUS),
        inbound=inbound_callback(),
    )
    assert first.replayed is False
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=callback_identity(update_id=44, callback_query_id="cb-other"),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.STATUS),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_callback_id_identical_replay_converges() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    identity = callback_identity(callback_query_id="cb-same")
    first = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    replay = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert replay.replayed is True
    assert replay.receipt.receipt_id == first.receipt.receipt_id
    assert replay.receipt.replay_fingerprint == first.receipt.replay_fingerprint
    assert len(replay.receipt.replay_fingerprint) == 64


def test_exact_callback_replays_bypass_rate_limit() -> None:
    protocol = enabled_protocol(
        rate_limit_policy=RateLimitPolicy(
            callback_per_user=2,
            callback_per_chat=2,
        )
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


def test_same_callback_id_changed_update_id_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id,
        payload=payload(action=TelegramRemoteAction.STATUS),
    )
    first_identity = callback_identity(update_id=46, callback_query_id="cb-update-conflict")
    first = protocol.receive_callback(
        identity=first_identity,
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.STATUS),
        inbound=inbound_callback(),
    )
    assert first.replayed is False

    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=first_identity.model_copy(update={"update_id": 47}),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.STATUS),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_callback_id_changed_nonce_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    first_issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    second_issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    identity = callback_identity(callback_query_id="cb-nonce-conflict")
    first = protocol.receive_callback(
        identity=identity,
        nonce_token=first_issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert first.receipt.state is ActionReceiptState.APPLIED
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=identity,
            nonce_token=second_issued.token,
            presented_payload=payload(),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT
    stored = protocol.store.get_nonce_by_hash(second_issued.nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.ISSUED


def test_same_callback_id_changed_payload_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    identity = callback_identity(callback_query_id="cb-payload-conflict")
    first = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert first.receipt.state is ActionReceiptState.APPLIED
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=identity,
            nonce_token=issued.token,
            presented_payload=payload(content_hash="c" * 64),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_update_id_changed_user_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    first = protocol.receive_callback(
        identity=callback_identity(update_id=77, callback_query_id="cb-user-a"),
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.STATUS),
        inbound=inbound_callback(),
    )
    assert first.replayed is False
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=callback_identity(
                update_id=77,
                callback_query_id="cb-user-b",
                telegram_user_id=OTHER_TG_USER,
            ),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.STATUS),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_update_id_changed_chat_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.EXPLAIN)
    )
    first = protocol.receive_callback(
        identity=callback_identity(update_id=88, callback_query_id="cb-chat-a"),
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
        inbound=inbound_callback(),
    )
    assert first.replayed is False
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=callback_identity(
                update_id=88,
                callback_query_id="cb-chat-b",
                chat_id=OTHER_CHAT,
            ),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_enrollment_update_id_changed_token_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity(update_id=9)
    first = protocol.complete_enrollment(
        token=started.token,
        identity=identity,
        inbound=inbound_message(),
    )
    assert first.binding.state is BindingState.VERIFIED
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token="other-enrollment-token-0001",
            identity=identity,
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_enrollment_update_id_changed_telegram_user_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    first = protocol.complete_enrollment(
        token=started.token,
        identity=message_identity(update_id=12, telegram_user_id=TG_USER),
        inbound=inbound_message(),
    )
    assert first.binding.telegram_user_id == TG_USER
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=message_identity(update_id=12, telegram_user_id=OTHER_TG_USER),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_enrollment_update_id_changed_message_id_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity(update_id=13, message_id="msg-original")
    first = protocol.complete_enrollment(
        token=started.token,
        identity=identity,
        inbound=inbound_message(),
    )
    assert first.binding.state is BindingState.VERIFIED

    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=identity.model_copy(update={"message_id": "msg-changed"}),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_enrollment_update_id_changed_chat_type_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    identity = message_identity(update_id=14)
    first = protocol.complete_enrollment(
        token=started.token,
        identity=identity,
        inbound=inbound_message(),
    )
    assert first.binding.state is BindingState.VERIFIED

    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=identity.model_copy(update={"chat_type": ChatType.GROUP}),
            inbound=inbound_message(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_same_callback_id_changed_chat_type_is_replay_conflict() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id,
        payload=payload(action=TelegramRemoteAction.EXPLAIN),
    )
    identity = callback_identity(update_id=48, callback_query_id="cb-chat-type-conflict")
    first = protocol.receive_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
        inbound=inbound_callback(),
    )
    assert first.replayed is False

    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=identity.model_copy(update={"chat_type": ChatType.GROUP}),
            nonce_token=issued.token,
            presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT


def test_valid_bounded_inbound_update() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    completed = protocol.complete_enrollment(
        token=started.token,
        identity=message_identity(),
        inbound=inbound_message(body_size=MAX_INBOUND_UPDATE_BYTES),
    )
    issued = protocol.issue_action_nonce(binding_id=completed.binding.binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(body_size=MAX_INBOUND_UPDATE_BYTES),
    )
    assert completed.binding.state is BindingState.VERIFIED
    assert outcome.receipt.state is ActionReceiptState.APPLIED
    assert outcome.executed is False


def test_oversized_callback_update_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.receive_callback(
            identity=callback_identity(),
            nonce_token=issued.token,
            presented_payload=payload(),
            inbound=inbound_callback(body_size=MAX_INBOUND_UPDATE_BYTES + 1),
        )
    assert exc.value.reason is TelegramSecurityReason.UPDATE_TOO_LARGE
    stored = protocol.store.get_nonce_by_hash(issued.nonce.nonce_hash)
    assert stored is not None
    assert stored.state is NonceState.ISSUED


def test_oversized_enrollment_update_rejected() -> None:
    protocol = enabled_protocol()
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    assert len(started.token.encode("utf-8")) < MAX_INBOUND_UPDATE_BYTES
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.complete_enrollment(
            token=started.token,
            identity=message_identity(),
            inbound=inbound_message(body_size=MAX_INBOUND_UPDATE_BYTES + 1),
        )
    assert exc.value.reason is TelegramSecurityReason.UPDATE_TOO_LARGE
    stored = protocol.store.get_challenge_by_hash(hash_secret(started.token))
    assert stored is not None
    assert stored.state is EnrollmentChallengeState.PENDING


def test_rate_limit_rejects_excess_callbacks() -> None:
    policy = RateLimitPolicy(
        callback_per_user=3,
        callback_window=timedelta(seconds=60),
        callback_per_chat=10,
        callback_chat_window=timedelta(seconds=60),
    )
    protocol = enabled_protocol(rate_limit_policy=policy)
    _, binding_id = enroll(protocol)
    first = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    second_nonce = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.EXPLAIN)
    )
    protocol.receive_callback(
        identity=callback_identity(update_id=21, callback_query_id="cb-r1"),
        nonce_token=first.token,
        presented_payload=payload(action=TelegramRemoteAction.STATUS),
        inbound=inbound_callback(),
    )
    protocol.receive_callback(
        identity=callback_identity(update_id=22, callback_query_id="cb-r2"),
        nonce_token=second_nonce.token,
        presented_payload=payload(action=TelegramRemoteAction.EXPLAIN),
        inbound=inbound_callback(),
    )
    third = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.SHOW_CHART)
    )
    with pytest.raises(TelegramRateLimitedError) as exc:
        protocol.receive_callback(
            identity=callback_identity(update_id=23, callback_query_id="cb-r3"),
            nonce_token=third.token,
            presented_payload=payload(action=TelegramRemoteAction.SHOW_CHART),
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.RATE_LIMITED


def test_approve_produces_authorization_intent_only() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert outcome.receipt.state is ActionReceiptState.APPLIED
    assert outcome.authorization_intent is not None
    intent = outcome.authorization_intent
    assert intent.action is TelegramRemoteAction.APPROVE
    assert intent.executes is False
    assert intent.execution_attempted is False
    assert intent.execution_entry_path is None
    assert intent.revision_id == REVISION
    assert intent.account_id == ACCOUNT
    assert APPROVE_EXECUTES is False
    assert outcome.executed is False
    assert outcome.execution_attempted is False
    assert outcome.execution_command_id is None
    assert protocol.execution_attempt_count == 0
    assert len(protocol.store.authorization_intents()) == 1


def test_approve_never_executes() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(binding_id=binding_id, payload=payload())
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(),
        inbound=inbound_callback(),
    )
    assert outcome.authorization_intent is not None
    assert outcome.executed is False
    assert protocol.execution_attempt_count == 0
    outbox = protocol.store.get_outbox_by_idempotency(
        organization_id=ORG,
        idempotency_key=f"auth-intent:{outcome.authorization_intent.intent_id}",
    )
    assert outbox is not None
    assert "does not execute" in outbox.text
    assert "EXECUTE_PAPER_PLAN" in outbox.text


def test_close_unavailable_on_issue_and_callback() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.issue_action_nonce(
            binding_id=binding_id,
            payload=payload(action=TelegramRemoteAction.CLOSE),
        )
    assert exc.value.reason is TelegramSecurityReason.CLOSE_UNAVAILABLE
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.STATUS)
    )
    close_payload = payload(action=TelegramRemoteAction.CLOSE)
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=close_payload,
        inbound=inbound_callback(),
    )
    assert outcome.reason_code == TelegramSecurityReason.CLOSE_UNAVAILABLE.value


def test_unknown_action_rejected_at_parse_boundary() -> None:
    with pytest.raises(TelegramSecurityError) as exc:
        parse_remote_action("LAUNCH")
    assert exc.value.reason is TelegramSecurityReason.UNKNOWN_ACTION


def test_transport_failure_and_retry() -> None:
    transport = FakeTelegramTransport()
    transport.fail_next(1)
    protocol = enabled_protocol(transport=transport)
    _, binding_id = enroll(protocol)
    record = protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="status prompt",
        idempotency_key="outbox-1",
    )
    first = protocol.deliver_pending()
    assert len(first) == 1
    assert first[0].accepted is False
    assert first[0].retryable is True
    assert first[0].outbox.state is OutboxState.RETRYABLE
    second = protocol.deliver_pending()
    assert len(second) == 1
    assert second[0].accepted is True
    assert second[0].outbox.state is OutboxState.SENT
    assert transport.send_count == 1
    assert transport.attempts == [record.idempotency_key, record.idempotency_key]


def test_duplicate_outbox_delivery_converges() -> None:
    transport = FakeTelegramTransport()
    protocol = enabled_protocol(transport=transport)
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
    delivered = protocol.deliver_pending()
    assert delivered[0].transport_message_id is not None
    # A retry after SENT is not claimed; at-least-once send uses the same key.
    again = protocol.deliver_pending()
    assert again == []
    assert transport.send_count == 1


def test_delivery_acknowledgement() -> None:
    transport = FakeTelegramTransport()
    protocol = enabled_protocol(transport=transport)
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


def test_transport_failure_without_retry_budget_dead_letters() -> None:
    transport = FakeTelegramTransport(behavior=FakeTelegramBehavior.FAIL)
    protocol = enabled_protocol(transport=transport)
    _, binding_id = enroll(protocol)
    protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="never sent",
        idempotency_key="dead-1",
    )
    last_state = None
    for _ in range(3):
        last_state = protocol.deliver_pending()[0].outbox.state
    assert last_state is OutboxState.DEAD_LETTER


def test_inbound_update_allowlist_and_size_bound() -> None:
    protocol = enabled_protocol()
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.assert_inbound_update_allowed(
            inbound=TelegramInboundUpdate(update_type="channel_post", body_size=10)
        )
    assert exc.value.reason is TelegramSecurityReason.UPDATE_TYPE_REJECTED
    with pytest.raises(TelegramSecurityError) as oversized:
        protocol.assert_inbound_update_allowed(
            inbound=TelegramInboundUpdate(
                update_type="message", body_size=MAX_INBOUND_UPDATE_BYTES + 1
            )
        )
    assert oversized.value.reason is TelegramSecurityReason.UPDATE_TOO_LARGE
    protocol.assert_inbound_update_allowed(
        inbound=TelegramInboundUpdate(update_type="callback_query", body_size=32)
    )
    assert "message" in ALLOWED_TELEGRAM_UPDATE_TYPES


def test_cross_user_alphatrade_payload_rejected() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    with pytest.raises(TelegramSecurityError) as exc:
        protocol.issue_action_nonce(binding_id=binding_id, payload=payload(user_id=OTHER_USER))
    assert exc.value.reason is TelegramSecurityReason.CROSS_USER


def test_action_receipts_are_auditable() -> None:
    protocol = enabled_protocol()
    _, binding_id = enroll(protocol)
    issued = protocol.issue_action_nonce(
        binding_id=binding_id, payload=payload(action=TelegramRemoteAction.REJECT)
    )
    outcome = protocol.receive_callback(
        identity=callback_identity(),
        nonce_token=issued.token,
        presented_payload=payload(action=TelegramRemoteAction.REJECT),
        inbound=inbound_callback(),
    )
    receipt = outcome.receipt
    assert receipt.nonce_hash == issued.nonce.nonce_hash
    assert receipt.payload_hash == issued.nonce.payload_hash
    assert len(receipt.replay_fingerprint) == 64
    assert [item.to_state for item in receipt.transitions] == [
        ActionReceiptState.RECEIVED,
        ActionReceiptState.CLAIMED,
        ActionReceiptState.APPLIED,
    ]
    events = [event.event_type for event in protocol.store.list_audits()]
    assert "nonce_issued" in events
    assert "action_applied" in events
    for event in protocol.store.list_audits():
        keys = {key for key, _value in event.details}
        assert "token" not in keys
        assert "nonce" not in keys


def test_no_telegram_webhook_route_is_registered() -> None:
    from app.main import create_app

    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any("telegram" in path and "webhook" in path for path in paths)
