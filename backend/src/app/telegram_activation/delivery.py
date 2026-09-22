"""Deliver due outbox rows and acknowledge sends. No network of its own."""

from __future__ import annotations

from uuid import UUID

from app.telegram_security.contracts import DeliveryAttempt, OutboxState
from app.telegram_security.protocol import TelegramSecurityProtocol


def deliver_due(
    protocol: TelegramSecurityProtocol,
    *,
    organization_id: UUID,
    limit: int = 10,
) -> list[DeliveryAttempt]:
    """Ack recovered SENT rows, deliver due work, then ack new sends.

    Rate-limit defers do not increment the outbox attempt. Backoff is enforced
    by the protocol claim using ``updated_at`` and ``attempt``.
    """
    if limit < 1:
        return []
    _acknowledge_sent(protocol, organization_id=organization_id, limit=limit)
    attempts = protocol.deliver_pending(limit=limit)
    finished: list[DeliveryAttempt] = []
    for attempt in attempts:
        message_id = attempt.transport_message_id
        if attempt.accepted and message_id is not None:
            acked = protocol.acknowledge_delivery(
                outbox_id=attempt.outbox.outbox_id,
                transport_message_id=message_id,
            )
            finished.append(attempt.model_copy(update={"outbox": acked}))
            continue
        finished.append(attempt)
    return finished


def _acknowledge_sent(
    protocol: TelegramSecurityProtocol,
    *,
    organization_id: UUID,
    limit: int,
) -> None:
    sent = protocol.store.list_outbox(
        organization_id=organization_id,
        state=OutboxState.SENT,
        limit=limit,
    )
    for row in sent:
        if row.transport_message_id is None:
            continue
        protocol.acknowledge_delivery(
            outbox_id=row.outbox_id,
            transport_message_id=row.transport_message_id,
        )
