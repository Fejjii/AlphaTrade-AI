"""PostgreSQL cursor and send ledger for paper Telegram activation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.telegram_activation import (
    TelegramActivationCursorRow,
    TelegramActivationSendLedgerRow,
)
from app.telegram_activation.cursor import InboundCursor
from app.telegram_activation.errors import TelegramActivationError
from app.telegram_activation.transport import SendLedgerRecord


class PostgresActivationCursorStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_cursor(self, *, bot_id: str) -> InboundCursor | None:
        with self._session_factory() as session:
            row = session.get(TelegramActivationCursorRow, bot_id)
            if row is None:
                return None
            return InboundCursor(
                bot_id=row.bot_id,
                organization_id=row.organization_id,
                last_update_id=row.last_update_id,
                updated_at=row.updated_at,
            )

    def save_cursor(self, row: InboundCursor) -> None:
        with self._session_factory() as session, session.begin():
            current = session.get(TelegramActivationCursorRow, row.bot_id, with_for_update=True)
            if current is None:
                session.add(
                    TelegramActivationCursorRow(
                        bot_id=row.bot_id,
                        organization_id=row.organization_id,
                        last_update_id=row.last_update_id,
                        updated_at=row.updated_at,
                    )
                )
                return
            if current.organization_id != row.organization_id:
                raise TelegramActivationError(
                    "Inbound cursor is bound to another organization.",
                    reason="tenant_conflict",
                )
            if row.last_update_id < current.last_update_id:
                raise TelegramActivationError(
                    "Inbound cursor cannot move backwards.",
                    reason="cursor_regression",
                )
            current.last_update_id = row.last_update_id
            current.updated_at = row.updated_at


class PostgresActivationSendLedger:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, *, bot_id: str, idempotency_key: str) -> SendLedgerRecord | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(TelegramActivationSendLedgerRow).where(
                    TelegramActivationSendLedgerRow.bot_id == bot_id,
                    TelegramActivationSendLedgerRow.idempotency_key == idempotency_key,
                )
            ).first()
            if row is None:
                return None
            return SendLedgerRecord(
                organization_id=row.organization_id,
                transport_message_id=row.transport_message_id,
            )

    def record(
        self,
        *,
        organization_id: UUID,
        bot_id: str,
        idempotency_key: str,
        transport_message_id: str,
        created_at: datetime,
    ) -> None:
        with self._session_factory() as session, session.begin():
            existing = session.scalars(
                select(TelegramActivationSendLedgerRow)
                .where(
                    TelegramActivationSendLedgerRow.bot_id == bot_id,
                    TelegramActivationSendLedgerRow.idempotency_key == idempotency_key,
                )
                .with_for_update()
            ).first()
            if existing is not None:
                _require_same_ledger(existing, organization_id, transport_message_id)
                return
            try:
                with session.begin_nested():
                    session.add(
                        TelegramActivationSendLedgerRow(
                            ledger_id=uuid4(),
                            organization_id=organization_id,
                            bot_id=bot_id,
                            idempotency_key=idempotency_key,
                            transport_message_id=transport_message_id,
                            created_at=created_at,
                        )
                    )
                    session.flush()
            except IntegrityError:
                winner = session.scalars(
                    select(TelegramActivationSendLedgerRow)
                    .where(
                        TelegramActivationSendLedgerRow.bot_id == bot_id,
                        TelegramActivationSendLedgerRow.idempotency_key == idempotency_key,
                    )
                    .with_for_update()
                ).first()
                if winner is None:
                    raise
                _require_same_ledger(winner, organization_id, transport_message_id)


def _require_same_ledger(
    row: TelegramActivationSendLedgerRow,
    organization_id: UUID,
    transport_message_id: str,
) -> None:
    if row.organization_id != organization_id or row.transport_message_id != transport_message_id:
        raise TelegramActivationError(
            "Send ledger identity conflict.",
            reason="ledger_conflict",
        )
