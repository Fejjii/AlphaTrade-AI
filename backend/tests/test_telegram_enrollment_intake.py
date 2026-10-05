"""Telegram-shaped enrollment updates through polling, runtime, and durable cursor."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from structlog.testing import capture_logs

from app.core.config import Settings
from app.db.runtime_status import ControlledRuntimeStatusRow
from app.db.telegram_activation import TelegramActivationCursorRow
from app.persistence.telegram_activation import PostgresActivationCursorStore
from app.telegram_activation.cursor import InboundCursor, enrollment_cursor_owner
from app.telegram_activation.intake import (
    HttpTelegramUpdateSource,
    ParsedTelegramUpdate,
    RecordedUpdateSource,
    parse_telegram_update,
    parse_webhook_body,
)
from app.telegram_activation.runtime import TelegramPaperRuntime, TelegramRuntimeCycle
from app.telegram_security.actions import MAX_INBOUND_UPDATE_BYTES
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import ActionReceiptState, ChatType, EnrollmentChallengeState
from app.telegram_security.errors import TelegramSecurityError, TelegramSecurityReason
from app.telegram_security.hashing import hash_secret
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import FakeTelegramTransport
from tests.support.telegram_security import BOT, ORG, USER, TokenSeq

UPDATE_ID = 967148778
TG_USER_ID = 123456789


@dataclass
class EnrollmentWorld:
    factory: sessionmaker[Session]
    clock: FrozenClock
    protocol: TelegramSecurityProtocol
    transport: FakeTelegramTransport
    token: str

    def poll(self, payload: dict[str, object]) -> TelegramRuntimeCycle:
        cursor = PostgresActivationCursorStore(self.factory).get_cursor(bot_id=BOT)
        assert cursor is not None

        def post(url: str, *, json: dict[str, object], timeout: float) -> httpx.Response:
            del url, timeout
            assert json["offset"] == cursor.last_update_id + 1
            assert json["limit"] == 20
            return httpx.Response(200, json={"ok": True, "result": [payload]})

        runtime = TelegramPaperRuntime(
            settings=Settings(
                _env_file=None,
                environment="local",
                execution_mode="paper",
                enable_real_trading=False,
                exchange_mode="paper_internal",
                global_kill_switch_active=False,
                telegram_bot_id=BOT,
                telegram_paper_activation_armed=False,
            ),
            session_factory=self.factory,
            clock=self.clock,
            worker_id="enrollment-intake-test",
            posture="enrollment",
            protocol=self.protocol,
            update_source=HttpTelegramUpdateSource(
                token="fixture-bot-token",
                timeout_seconds=1,
                network_permitted=True,
                http_post=post,
            ),
            cursor_store=PostgresActivationCursorStore(self.factory),
        )
        return runtime.run_cycle()

    def assert_cursor_consumed(self) -> None:
        cursor = PostgresActivationCursorStore(self.factory).get_cursor(bot_id=BOT)
        assert cursor is not None
        assert cursor.last_update_id == UPDATE_ID


@pytest.fixture
def world() -> Iterator[EnrollmentWorld]:
    # Exercise the real SQL cursor/status persistence without a shared database.
    engine = create_engine("sqlite://")
    TelegramActivationCursorRow.__table__.create(engine)
    ControlledRuntimeStatusRow.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    clock = FrozenClock()
    transport = FakeTelegramTransport()
    protocol = TelegramSecurityProtocol.in_memory(
        enabled=True, clock=clock, transport=transport, token_factory=TokenSeq()
    )
    started = protocol.start_enrollment(organization_id=ORG, user_id=USER, bot_id=BOT)
    PostgresActivationCursorStore(factory).save_cursor(
        InboundCursor(
            bot_id=BOT,
            organization_id=enrollment_cursor_owner(BOT),
            last_update_id=UPDATE_ID - 1,
            updated_at=clock.now(),
        )
    )
    yield EnrollmentWorld(factory, clock, protocol, transport, started.token)
    engine.dispose()


def _message(text: object) -> dict[str, object]:
    return {
        "message_id": 42,
        "from": {"id": TG_USER_ID, "is_bot": False, "first_name": "Test"},
        "chat": {"id": TG_USER_ID, "type": "private", "first_name": "Test"},
        "date": 1791190800,
        "text": text,
    }


def test_valid_private_message_enrollment_completes(world: EnrollmentWorld) -> None:
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": _message(world.token)})

    world.assert_cursor_consumed()
    assert cycle.kill_switch_active is False
    assert cycle.posture == "enrollment"
    challenge = world.protocol.store.get_challenge_by_hash(hash_secret(world.token))
    assert challenge is not None
    assert challenge.state is EnrollmentChallengeState.COMPLETED
    assert challenge.token_hash == hash_secret(world.token)
    assert world.token not in challenge.model_dump_json()
    assert cycle.poll_applied == 1
    assert cycle.poll_rejected == 0
    assert cycle.last_error_code == ""
    binding = world.protocol.store.get_active_binding_for_chat(bot_id=BOT, chat_id=str(TG_USER_ID))
    assert binding is not None
    assert binding.organization_id == ORG
    assert binding.telegram_user_id == str(TG_USER_ID)
    receipt = world.protocol.store.get_update_receipt(bot_id=BOT, update_id=UPDATE_ID)
    assert receipt is not None
    assert receipt.state is ActionReceiptState.APPLIED
    assert [row.event_type for row in world.protocol.store.list_audits()] == [
        "enrollment_started",
        "enrollment_completed",
    ]
    assert world.protocol.execution_attempt_count == 0
    assert world.transport.send_count == 0
    assert world.token not in json.dumps(logs)


def _assert_rejected(
    world: EnrollmentWorld,
    cycle: TelegramRuntimeCycle,
    logs: list[dict[str, object]],
    *,
    reason: str,
) -> dict[str, object]:
    world.assert_cursor_consumed()
    assert cycle.poll_applied == 0
    assert cycle.poll_rejected == 1
    assert cycle.last_error_code == reason
    with world.factory() as session:
        status = session.get(ControlledRuntimeStatusRow, "telegram")
        assert status is not None
        assert status.last_error_code == reason
    challenge = world.protocol.store.get_challenge_by_hash(hash_secret(world.token))
    assert challenge is not None
    assert challenge.state is EnrollmentChallengeState.PENDING
    assert (
        world.protocol.store.get_active_binding_for_chat(bot_id=BOT, chat_id=str(TG_USER_ID))
        is None
    )
    assert world.protocol.execution_attempt_count == 0
    assert world.transport.send_count == 0
    assert world.token not in json.dumps(logs)
    [event] = [row for row in logs if row["event"] == "telegram_enrollment_rejected"]
    assert event["update_id"] == UPDATE_ID
    assert event["reason"] == reason
    assert set(event) == {
        "event",
        "log_level",
        "update_id",
        "kind",
        "chat_type",
        "reason",
        "parser_rejection_reason",
        "has_text",
        "has_telegram_user_id",
        "has_message_id",
    }
    return event


def test_wrong_token_stays_rejected(world: EnrollmentWorld) -> None:
    wrong_token = "wrong-token-do-not-log"
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": _message(wrong_token)})
    event = _assert_rejected(world, cycle, logs, reason="ENROLLMENT_NOT_FOUND")
    assert event["parser_rejection_reason"] is None
    assert wrong_token not in json.dumps(logs)
    receipt = world.protocol.store.get_update_receipt(bot_id=BOT, update_id=UPDATE_ID)
    assert receipt is not None
    assert receipt.state is ActionReceiptState.REJECTED
    assert receipt.reason_code == "ENROLLMENT_NOT_FOUND"


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
def test_non_private_chat_stays_rejected(world: EnrollmentWorld, chat_type: str) -> None:
    message = _message(world.token)
    message["chat"] = {"id": -100123456789, "type": chat_type}
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": message})
    event = _assert_rejected(world, cycle, logs, reason="chat_not_private")
    assert event["kind"] == "message"
    assert event["chat_type"] == chat_type
    assert event["parser_rejection_reason"] == "chat_not_private"
    assert event["has_text"] is True
    assert event["has_telegram_user_id"] is True
    assert event["has_message_id"] is True
    assert world.protocol.store.get_update_receipt(bot_id=BOT, update_id=UPDATE_ID) is None


@pytest.mark.parametrize("sender", [None, {}, {"id": None}, {"id": True}, 123456789])
def test_missing_or_invalid_user_id_stays_rejected(world: EnrollmentWorld, sender: object) -> None:
    message = _message(world.token)
    message["from"] = sender
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": message})
    event = _assert_rejected(world, cycle, logs, reason="telegram_user_id_missing")
    assert event["parser_rejection_reason"] == "telegram_user_id_missing"
    assert event["has_telegram_user_id"] is False
    assert event["has_message_id"] is True


def test_missing_message_id_stays_rejected(world: EnrollmentWorld) -> None:
    message = _message(world.token)
    del message["message_id"]
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": message})
    event = _assert_rejected(world, cycle, logs, reason="message_id_missing")
    assert event["parser_rejection_reason"] == "message_id_missing"
    assert event["has_telegram_user_id"] is True
    assert event["has_message_id"] is False


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_has_deterministic_reason(world: EnrollmentWorld, text: str) -> None:
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": _message(text)})
    event = _assert_rejected(world, cycle, logs, reason="text_missing")
    assert event["parser_rejection_reason"] is None


def test_callback_sender_object_parses_but_cannot_enroll(world: EnrollmentWorld) -> None:
    payload = {
        "update_id": UPDATE_ID,
        "callback_query": {
            "id": "callback-42",
            "from": {"id": TG_USER_ID},
            "message": _message("callback-message-do-not-log"),
            "data": world.token,
        },
    }
    parsed = parse_telegram_update(payload, body_size=1024)
    assert parsed.kind == "callback_query"
    assert parsed.telegram_user_id == str(TG_USER_ID)
    with capture_logs() as logs:
        cycle = world.poll(payload)
    event = _assert_rejected(world, cycle, logs, reason="update_type_rejected")
    assert event["kind"] == "callback_query"
    assert "callback-message-do-not-log" not in json.dumps(logs)


def test_parser_rejection_diagnostics_remain_bounded(world: EnrollmentWorld) -> None:
    message = _message(world.token)
    message["chat"] = {"id": TG_USER_ID, "type": world.token}
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": message})
    event = _assert_rejected(world, cycle, logs, reason="chat_not_private")
    assert event["chat_type"] == "unknown"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("id", "", "invalid_update"),
        ("id", "x" * 129, "invalid_update"),
        ("data", "", "invalid_update"),
        ("data", "x" * 65, "invalid_update"),
        ("from", {}, "invalid_update"),
        ("message", {"chat": {"id": 1, "type": "group"}}, "chat_not_private"),
        ("message", {}, "invalid_update"),
    ],
)
def test_callback_parser_rejection_is_observable(
    world: EnrollmentWorld, field: str, value: object, reason: str
) -> None:
    callback = {
        "id": "callback-42",
        "from": {"id": TG_USER_ID},
        "message": _message(world.token),
        "data": world.token,
    }
    callback[field] = value
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "callback_query": callback})
    event = _assert_rejected(world, cycle, logs, reason=reason)
    assert event["kind"] == "callback_query"
    assert event["parser_rejection_reason"] == reason


@pytest.mark.parametrize(
    ("payload", "body_size", "reason"),
    [
        (None, 10, "invalid_update"),
        ({"update_id": True}, 10, "invalid_update"),
        ({"update_id": -1}, 10, "invalid_update"),
        ({"update_id": UPDATE_ID}, 10, "update_type_rejected"),
        ({"update_id": UPDATE_ID, "message": {}, "callback_query": {}}, 10, "update_type_rejected"),
        ({"update_id": UPDATE_ID, "message": []}, 10, "invalid_update"),
        ({"update_id": UPDATE_ID, "callback_query": []}, 10, "invalid_update"),
        (
            {"update_id": UPDATE_ID, "message": _message("x")},
            MAX_INBOUND_UPDATE_BYTES + 1,
            "update_too_large",
        ),
        ({"update_id": UPDATE_ID, "message": _message("x" * 4097)}, 5000, "message_too_large"),
        ({"update_id": UPDATE_ID, "message": _message(123)}, 1024, "invalid_update"),
        (
            {"update_id": UPDATE_ID, "message": {"chat": None}},
            1024,
            "invalid_update",
        ),
        (
            {"update_id": UPDATE_ID, "message": {"chat": {"id": None, "type": "private"}}},
            1024,
            "invalid_update",
        ),
    ],
)
def test_parser_rejection_paths(payload: object, body_size: int, reason: str) -> None:
    parsed = parse_telegram_update(payload, body_size=body_size)
    assert parsed.kind == "rejected"
    assert parsed.rejection == reason
    assert parsed.text == ""
    assert parsed.telegram_user_id == ""
    assert parsed.chat_id == ""
    assert parsed.message_id is None


@pytest.mark.parametrize("raw", [b"not-json", b"\xff", b"x" * (MAX_INBOUND_UPDATE_BYTES + 1)])
def test_webhook_body_rejection(raw: bytes) -> None:
    parsed = parse_webhook_body(raw)
    assert parsed.kind == "rejected"
    assert parsed.rejection in {"invalid_update", "update_too_large"}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"kind": "rejected"}, "parser_rejected"),
        ({"chat_type": ChatType.GROUP}, "chat_not_private"),
        ({"telegram_user_id": ""}, "telegram_user_id_missing"),
        ({"message_id": None}, "message_id_missing"),
        ({"chat_id": ""}, "chat_id_missing"),
    ],
)
def test_runtime_early_returns_are_observable(
    world: EnrollmentWorld,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
    reason: str,
) -> None:
    parsed = ParsedTelegramUpdate(
        update_id=UPDATE_ID,
        body_size=1024,
        kind="message",
        chat_id=str(TG_USER_ID),
        telegram_user_id=str(TG_USER_ID),
        message_id="42",
        text=world.token,
    ).model_copy(update=overrides)
    # Replace the fixture's polling constructor, retaining runtime/cursor persistence.
    monkeypatch.setattr(
        "tests.test_telegram_enrollment_intake.HttpTelegramUpdateSource",
        lambda **_: RecordedUpdateSource([parsed]),
    )
    with capture_logs() as logs:
        cycle = world.poll({})
    _assert_rejected(world, cycle, logs, reason=reason)


def test_token_is_one_time_and_never_logged(world: EnrollmentWorld) -> None:
    with capture_logs() as logs:
        first = world.poll({"update_id": UPDATE_ID, "message": _message(world.token)})
        second = world.poll({"update_id": UPDATE_ID + 1, "message": _message(world.token)})
    assert first.poll_applied == 1
    assert second.poll_applied == 0
    assert second.poll_rejected == 1
    assert second.last_error_code == "ENROLLMENT_USED"
    [event] = [row for row in logs if row["event"] == "telegram_enrollment_rejected"]
    assert event["reason"] == "ENROLLMENT_USED"
    assert event["parser_rejection_reason"] is None
    assert world.token not in json.dumps(logs)


def test_invalid_update_id_has_reason_and_does_not_advance(world: EnrollmentWorld) -> None:
    with capture_logs() as logs:
        cycle = world.poll({"update_id": False, "message": _message(world.token)})
    assert cycle.poll_rejected == 1
    assert cycle.last_error_code == "invalid_update"
    cursor = PostgresActivationCursorStore(world.factory).get_cursor(bot_id=BOT)
    assert cursor is not None
    assert cursor.last_update_id == UPDATE_ID - 1
    [event] = [row for row in logs if row["event"] == "telegram_enrollment_rejected"]
    assert event["reason"] == "invalid_update"
    assert world.token not in json.dumps(logs)


def test_protocol_exception_text_and_details_are_never_logged(
    world: EnrollmentWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject(**_: object) -> None:
        raise TelegramSecurityError(
            world.token,
            reason=TelegramSecurityReason.RATE_LIMITED,
            details={"text": world.token},
        )

    monkeypatch.setattr(world.protocol, "complete_enrollment", reject)
    with capture_logs() as logs:
        cycle = world.poll({"update_id": UPDATE_ID, "message": _message(world.token)})
    _assert_rejected(world, cycle, logs, reason="RATE_LIMITED")
