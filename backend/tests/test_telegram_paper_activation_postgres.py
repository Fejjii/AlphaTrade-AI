"""PostgreSQL paper-activation cursor, send ledger, and durable backoff."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.persistence.composition import build_postgres_telegram_security_protocol
from app.persistence.telegram_activation import (
    PostgresActivationCursorStore,
    PostgresActivationSendLedger,
)
from app.telegram_activation.cursor import InboundCursor
from app.telegram_activation.errors import TelegramActivationError
from app.telegram_activation.policy import PAPER_ACTIVATION_BACKOFF
from app.telegram_security.backoff import RATE_LIMITED_ERROR
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import OutboxState
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import FakeTelegramBehavior, FakeTelegramTransport
from tests.support.postgres_persistence import persistence_session_factory, requires_postgres
from tests.support.telegram_security import BOT, CHAT, ORG, OTHER_ORG, USER, enroll


def _protocol(
    factory: sessionmaker[Session],
    *,
    clock: FrozenClock,
    transport: FakeTelegramTransport,
) -> TelegramSecurityProtocol:
    return build_postgres_telegram_security_protocol(
        factory,
        enabled=True,
        clock=clock,
        transport=transport,
        retry_backoff=PAPER_ACTIVATION_BACKOFF,
    )


@requires_postgres
def test_postgres_backoff_and_rate_limit_wait_are_durable() -> None:
    factory = persistence_session_factory()
    clock = FrozenClock()
    failing = FakeTelegramTransport()
    failing.behavior = FakeTelegramBehavior.FAIL
    protocol = _protocol(factory, clock=clock, transport=failing)
    _, binding_id = enroll(protocol)
    protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="retry me",
        idempotency_key="paper-activation:backoff",
    )
    first = protocol.deliver_pending(limit=5)
    assert len(first) == 1
    assert first[0].outbox.state is OutboxState.RETRYABLE
    assert first[0].outbox.attempt == 1
    assert protocol.deliver_pending(limit=5) == []
    clock.advance(timedelta(seconds=4))
    assert protocol.deliver_pending(limit=5) == []
    clock.advance(timedelta(seconds=1))
    second = protocol.deliver_pending(limit=5)
    assert len(second) == 1
    assert second[0].outbox.attempt == 2
    assert second[0].outbox.state is OutboxState.RETRYABLE

    limited = protocol.enqueue_outbound(
        organization_id=ORG,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="wait",
        idempotency_key="paper-activation:limited",
    )
    protocol.store.save_outbox(
        limited.model_copy(
            update={
                "state": OutboxState.RETRYABLE,
                "last_error": RATE_LIMITED_ERROR,
                "attempt": 0,
                "updated_at": clock.now(),
            }
        )
    )
    assert protocol.deliver_pending(limit=5) == []
    clock.advance(timedelta(seconds=5))
    resumed = protocol.deliver_pending(limit=5)
    assert len(resumed) == 1
    assert resumed[0].outbox.idempotency_key == "paper-activation:limited"
    assert resumed[0].accepted is False
    assert resumed[0].outbox.attempt == 1
    assert resumed[0].error_code == "TRANSPORT_FAILURE"


@requires_postgres
def test_postgres_cursor_and_send_ledger_fail_closed() -> None:
    factory = persistence_session_factory()
    clock = FrozenClock()
    cursors = PostgresActivationCursorStore(factory)
    now = clock.now()
    cursors.save_cursor(
        InboundCursor(
            bot_id=BOT,
            organization_id=ORG,
            last_update_id=4,
            updated_at=now,
        )
    )
    loaded = cursors.get_cursor(bot_id=BOT)
    assert loaded is not None
    assert loaded.last_update_id == 4
    assert loaded.organization_id == ORG
    with pytest.raises(TelegramActivationError) as tenant:
        cursors.save_cursor(
            InboundCursor(
                bot_id=BOT,
                organization_id=OTHER_ORG,
                last_update_id=5,
                updated_at=now,
            )
        )
    assert tenant.value.reason == "tenant_conflict"
    with pytest.raises(TelegramActivationError) as regression:
        cursors.save_cursor(
            InboundCursor(
                bot_id=BOT,
                organization_id=ORG,
                last_update_id=3,
                updated_at=now,
            )
        )
    assert regression.value.reason == "cursor_regression"
    cursors.save_cursor(
        InboundCursor(
            bot_id=BOT,
            organization_id=ORG,
            last_update_id=6,
            updated_at=now,
        )
    )
    advanced = cursors.get_cursor(bot_id=BOT)
    assert advanced is not None and advanced.last_update_id == 6

    ledger = PostgresActivationSendLedger(factory)
    ledger.record(
        organization_id=ORG,
        bot_id=BOT,
        idempotency_key="paper-activation:send",
        transport_message_id="91",
        created_at=now,
    )
    stored = ledger.get(bot_id=BOT, idempotency_key="paper-activation:send")
    assert stored is not None
    assert stored.transport_message_id == "91"
    assert stored.organization_id == ORG
    ledger.record(
        organization_id=ORG,
        bot_id=BOT,
        idempotency_key="paper-activation:send",
        transport_message_id="91",
        created_at=now,
    )
    with pytest.raises(TelegramActivationError) as conflict:
        ledger.record(
            organization_id=ORG,
            bot_id=BOT,
            idempotency_key="paper-activation:send",
            transport_message_id="92",
            created_at=now,
        )
    assert conflict.value.reason == "ledger_conflict"
    with pytest.raises(TelegramActivationError) as cross_tenant:
        ledger.record(
            organization_id=OTHER_ORG,
            bot_id=BOT,
            idempotency_key="paper-activation:send",
            transport_message_id="91",
            created_at=now,
        )
    assert cross_tenant.value.reason == "ledger_conflict"
