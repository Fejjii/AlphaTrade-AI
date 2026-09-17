"""PostgreSQL adapter for the existing TelegramSecurityStore contract.

Linearization points
--------------------
* Protocol mutation: ``pg_advisory_xact_lock`` at ``transaction()`` start (same
  serial order as the in-memory re-entrant lock). No transaction stays open
  across Telegram transport I/O.
* Nonce consume: ``SELECT ... FOR UPDATE`` on ``nonce_hash``, then compare-and-set.
* Outbox claim: ``SELECT ... FOR UPDATE SKIP LOCKED`` of claimable rows ordered
  by ``created_at``. Expired ``CLAIMED`` leases are reclaimable.
* Replay first-writer: unique ``(bot_id, update_id)`` and unique
  ``(bot_id, callback_query_id)``; conflicting fingerprints fail closed.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.telegram_security import (
    TelegramActionNonceRow,
    TelegramActionReceiptRow,
    TelegramAuthorizationIntentRow,
    TelegramBindingRow,
    TelegramEnrollmentChallengeRow,
    TelegramOutboxRow,
    TelegramProtocolAuditEventRow,
)
from app.persistence.unique import is_unique_violation
from app.telegram_security.actions import ActionEffectKind, TelegramRemoteAction
from app.telegram_security.contracts import (
    ActionNonce,
    ActionReceipt,
    ActionReceiptState,
    AuthorizationIntent,
    BindingState,
    ChatType,
    EnrollmentChallenge,
    EnrollmentChallengeState,
    NonceState,
    OutboxKind,
    OutboxRecord,
    OutboxState,
    ProtocolAuditEvent,
    ReceiptTransition,
    TelegramBinding,
)
from app.telegram_security.errors import TelegramSecurityError, TelegramSecurityReason

_T = TypeVar("_T")

_STORE_LOCK_SQL = "SELECT pg_advisory_xact_lock(1413890885, 1)"
_RECEIPT_UNIQUES = (
    "uq_tgsec_receipts_bot_update",
    "uq_tgsec_receipts_bot_callback",
)
_OUTBOX_UNIQUES = ("uq_tgsec_outbox_org_idempotency",)
_CLAIMABLE_STATES = (OutboxState.PENDING.value, OutboxState.RETRYABLE.value)


class PostgresTelegramSecurityStore:
    """Durable TelegramSecurityStore. In-memory store remains the unit-test default."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._local = threading.local()

    def _current(self) -> Session | None:
        session = getattr(self._local, "session", None)
        return session if isinstance(session, Session) else None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        existing = self._current()
        if existing is not None:
            yield
            return
        session = self._session_factory()
        self._local.session = session
        try:
            with session.begin():
                session.execute(text(_STORE_LOCK_SQL))
                yield
        finally:
            session.close()
            self._local.session = None

    def _run(self, work: Callable[[Session], _T]) -> _T:
        current = self._current()
        if current is not None:
            return work(current)
        with self.transaction():
            held = self._current()
            if held is None:
                raise RuntimeError("Telegram persistence transaction is not active.")
            return work(held)

    def save_challenge(self, row: EnrollmentChallenge) -> None:
        def work(session: Session) -> None:
            current = session.get(TelegramEnrollmentChallengeRow, row.challenge_id)
            if current is None:
                session.add(_challenge_to_row(row))
            else:
                _apply_challenge(current, row)
            session.flush()

        self._run(work)

    def get_challenge_by_hash(self, token_hash: str) -> EnrollmentChallenge | None:
        def work(session: Session) -> EnrollmentChallenge | None:
            current = session.scalars(
                select(TelegramEnrollmentChallengeRow).where(
                    TelegramEnrollmentChallengeRow.token_hash == token_hash
                )
            ).first()
            return None if current is None else _challenge_from_row(current)

        return self._run(work)

    def get_challenge_for_binding(self, binding_id: UUID) -> EnrollmentChallenge | None:
        def work(session: Session) -> EnrollmentChallenge | None:
            current = session.scalars(
                select(TelegramEnrollmentChallengeRow).where(
                    TelegramEnrollmentChallengeRow.binding_id == binding_id
                )
            ).first()
            return None if current is None else _challenge_from_row(current)

        return self._run(work)

    def list_pending_challenges(
        self, *, organization_id: UUID, user_id: UUID, bot_id: str
    ) -> list[EnrollmentChallenge]:
        def work(session: Session) -> list[EnrollmentChallenge]:
            rows = session.scalars(
                select(TelegramEnrollmentChallengeRow).where(
                    TelegramEnrollmentChallengeRow.organization_id == organization_id,
                    TelegramEnrollmentChallengeRow.user_id == user_id,
                    TelegramEnrollmentChallengeRow.bot_id == bot_id,
                    TelegramEnrollmentChallengeRow.state == EnrollmentChallengeState.PENDING.value,
                )
            ).all()
            return [_challenge_from_row(item) for item in rows]

        return self._run(work)

    def cas_challenge(
        self,
        *,
        challenge_id: UUID,
        expected: EnrollmentChallenge,
        updated: EnrollmentChallenge,
    ) -> bool:
        def work(session: Session) -> bool:
            current = session.get(
                TelegramEnrollmentChallengeRow, challenge_id, with_for_update=True
            )
            if current is None or _challenge_from_row(current) != expected:
                return False
            _apply_challenge(current, updated)
            session.flush()
            return True

        return self._run(work)

    def save_binding(self, row: TelegramBinding) -> None:
        def work(session: Session) -> None:
            current = session.get(TelegramBindingRow, row.binding_id)
            if current is None:
                session.add(_binding_to_row(row))
            else:
                _apply_binding(current, row)
            session.flush()

        self._run(work)

    def get_binding(self, binding_id: UUID) -> TelegramBinding | None:
        def work(session: Session) -> TelegramBinding | None:
            current = session.get(TelegramBindingRow, binding_id)
            return None if current is None else _binding_from_row(current)

        return self._run(work)

    def get_active_binding_for_user(
        self, *, organization_id: UUID, user_id: UUID
    ) -> TelegramBinding | None:
        def work(session: Session) -> TelegramBinding | None:
            current = session.scalars(
                _active_binding_stmt().where(
                    TelegramBindingRow.organization_id == organization_id,
                    TelegramBindingRow.user_id == user_id,
                )
            ).first()
            return None if current is None else _binding_from_row(current)

        return self._run(work)

    def get_active_binding_for_telegram_user(
        self, *, bot_id: str, telegram_user_id: str
    ) -> TelegramBinding | None:
        def work(session: Session) -> TelegramBinding | None:
            current = session.scalars(
                _active_binding_stmt().where(
                    TelegramBindingRow.bot_id == bot_id,
                    TelegramBindingRow.telegram_user_id == telegram_user_id,
                )
            ).first()
            return None if current is None else _binding_from_row(current)

        return self._run(work)

    def get_active_binding_for_chat(self, *, bot_id: str, chat_id: str) -> TelegramBinding | None:
        def work(session: Session) -> TelegramBinding | None:
            current = session.scalars(
                _active_binding_stmt().where(
                    TelegramBindingRow.bot_id == bot_id,
                    TelegramBindingRow.chat_id == chat_id,
                )
            ).first()
            return None if current is None else _binding_from_row(current)

        return self._run(work)

    def save_nonce(self, row: ActionNonce) -> None:
        def work(session: Session) -> None:
            current = session.scalars(
                select(TelegramActionNonceRow)
                .where(TelegramActionNonceRow.nonce_hash == row.nonce_hash)
                .with_for_update()
            ).first()
            if current is None:
                session.add(_nonce_to_row(row))
            else:
                _apply_nonce(current, row)
            session.flush()

        self._run(work)

    def get_nonce_by_hash(self, nonce_hash: str) -> ActionNonce | None:
        def work(session: Session) -> ActionNonce | None:
            current = session.scalars(
                select(TelegramActionNonceRow).where(
                    TelegramActionNonceRow.nonce_hash == nonce_hash
                )
            ).first()
            return None if current is None else _nonce_from_row(current)

        return self._run(work)

    def cas_nonce(self, *, nonce_hash: str, expected: ActionNonce, updated: ActionNonce) -> bool:
        def work(session: Session) -> bool:
            current = session.scalars(
                select(TelegramActionNonceRow)
                .where(TelegramActionNonceRow.nonce_hash == nonce_hash)
                .with_for_update()
            ).first()
            if current is None or _nonce_from_row(current) != expected:
                return False
            _apply_nonce(current, updated)
            session.flush()
            return True

        return self._run(work)

    def get_callback_receipt(self, *, bot_id: str, callback_query_id: str) -> ActionReceipt | None:
        def work(session: Session) -> ActionReceipt | None:
            current = session.scalars(
                select(TelegramActionReceiptRow).where(
                    TelegramActionReceiptRow.bot_id == bot_id,
                    TelegramActionReceiptRow.callback_query_id == callback_query_id,
                )
            ).first()
            return None if current is None else _receipt_from_row(current)

        return self._run(work)

    def get_update_receipt(self, *, bot_id: str, update_id: int) -> ActionReceipt | None:
        def work(session: Session) -> ActionReceipt | None:
            current = session.scalars(
                select(TelegramActionReceiptRow).where(
                    TelegramActionReceiptRow.bot_id == bot_id,
                    TelegramActionReceiptRow.update_id == update_id,
                )
            ).first()
            return None if current is None else _receipt_from_row(current)

        return self._run(work)

    def save_receipt(self, row: ActionReceipt) -> None:
        def work(session: Session) -> None:
            current = session.get(TelegramActionReceiptRow, row.receipt_id, with_for_update=True)
            if current is not None:
                _apply_receipt(current, row)
                session.flush()
                return
            winner = _locked_receipt_identity(session, row)
            if winner is not None and winner.receipt_id != row.receipt_id:
                _reject_or_converge_receipt(winner, row)
                return
            try:
                with session.begin_nested():
                    session.add(_receipt_to_row(row))
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_RECEIPT_UNIQUES):
                    raise
                existing = _locked_receipt_identity(session, row)
                if existing is None:
                    raise
                _reject_or_converge_receipt(existing, row)

        self._run(work)

    def save_authorization_intent(self, row: AuthorizationIntent) -> None:
        def work(session: Session) -> None:
            current = session.get(TelegramAuthorizationIntentRow, row.intent_id)
            if current is None:
                session.add(_intent_to_row(row))
            session.flush()

        self._run(work)

    def get_authorization_intent(self, intent_id: UUID) -> AuthorizationIntent | None:
        def work(session: Session) -> AuthorizationIntent | None:
            current = session.get(TelegramAuthorizationIntentRow, intent_id)
            return None if current is None else _intent_from_row(current)

        return self._run(work)

    def get_outbox(self, outbox_id: UUID) -> OutboxRecord | None:
        def work(session: Session) -> OutboxRecord | None:
            current = session.get(TelegramOutboxRow, outbox_id)
            return None if current is None else _outbox_from_row(current)

        return self._run(work)

    def get_outbox_by_idempotency(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> OutboxRecord | None:
        def work(session: Session) -> OutboxRecord | None:
            current = _load_outbox_key(session, organization_id, idempotency_key)
            return None if current is None else _outbox_from_row(current)

        return self._run(work)

    def save_outbox(self, row: OutboxRecord) -> None:
        def work(session: Session) -> None:
            current = session.get(TelegramOutboxRow, row.outbox_id, with_for_update=True)
            if current is not None:
                _apply_outbox(current, row)
                session.flush()
                return
            existing = _load_outbox_key(
                session, row.organization_id, row.idempotency_key, for_update=True
            )
            if existing is not None:
                _reject_or_converge_outbox(existing, row)
                return
            try:
                with session.begin_nested():
                    session.add(_outbox_to_row(row))
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_OUTBOX_UNIQUES):
                    raise
                winner = _load_outbox_key(
                    session, row.organization_id, row.idempotency_key, for_update=True
                )
                if winner is None:
                    raise
                _reject_or_converge_outbox(winner, row)

        self._run(work)

    def claim_outbox_batch(
        self,
        *,
        now: datetime,
        limit: int,
        lease_owner: str,
        lease_for: timedelta,
        retryable_reasons: frozenset[TelegramSecurityReason] | None = None,
    ) -> list[OutboxRecord]:
        _ = retryable_reasons

        def work(session: Session) -> list[OutboxRecord]:
            rows = list(
                session.scalars(
                    select(TelegramOutboxRow)
                    .where(_outbox_claimable(now))
                    .order_by(TelegramOutboxRow.created_at, TelegramOutboxRow.outbox_id)
                    .with_for_update(skip_locked=True)
                    .limit(limit)
                )
            )
            claimed: list[OutboxRecord] = []
            until = now + lease_for
            for row in rows:
                row.state = OutboxState.CLAIMED.value
                row.lease_owner = lease_owner
                row.lease_until = until
                row.updated_at = now
                claimed.append(_outbox_from_row(row))
            session.flush()
            return claimed

        return self._run(work)

    def append_audit(self, event: ProtocolAuditEvent) -> None:
        def work(session: Session) -> None:
            session.add(
                TelegramProtocolAuditEventRow(
                    event_id=event.event_id,
                    at=event.at,
                    event_type=event.event_type,
                    organization_id=event.organization_id,
                    user_id=event.user_id,
                    reason_code=event.reason_code,
                    details=[[key, value] for key, value in event.details],
                )
            )

        self._run(work)

    def list_audits(self) -> list[ProtocolAuditEvent]:
        def work(session: Session) -> list[ProtocolAuditEvent]:
            rows = session.scalars(
                select(TelegramProtocolAuditEventRow).order_by(
                    TelegramProtocolAuditEventRow.at,
                    TelegramProtocolAuditEventRow.event_id,
                )
            ).all()
            return [
                ProtocolAuditEvent(
                    event_id=item.event_id,
                    at=_aware(item.at),
                    event_type=item.event_type,
                    organization_id=item.organization_id,
                    user_id=item.user_id,
                    reason_code=item.reason_code,
                    details=tuple((pair[0], pair[1]) for pair in item.details),
                )
                for item in rows
            ]

        return self._run(work)

    def authorization_intents(self) -> list[AuthorizationIntent]:
        def work(session: Session) -> list[AuthorizationIntent]:
            rows = session.scalars(
                select(TelegramAuthorizationIntentRow).order_by(
                    TelegramAuthorizationIntentRow.created_at,
                    TelegramAuthorizationIntentRow.intent_id,
                )
            ).all()
            return [_intent_from_row(item) for item in rows]

        return self._run(work)


def _active_binding_stmt() -> Select[tuple[TelegramBindingRow]]:
    return (
        select(TelegramBindingRow)
        .where(TelegramBindingRow.revoked_at.is_(None))
        .order_by(TelegramBindingRow.verified_at.desc())
    )


def _outbox_claimable(now: datetime) -> object:
    return or_(
        TelegramOutboxRow.state.in_(_CLAIMABLE_STATES),
        and_(
            TelegramOutboxRow.state == OutboxState.CLAIMED.value,
            or_(TelegramOutboxRow.lease_until.is_(None), TelegramOutboxRow.lease_until <= now),
        ),
    )


def _load_outbox_key(
    session: Session,
    organization_id: UUID,
    idempotency_key: str,
    *,
    for_update: bool = False,
) -> TelegramOutboxRow | None:
    stmt = select(TelegramOutboxRow).where(
        TelegramOutboxRow.organization_id == organization_id,
        TelegramOutboxRow.idempotency_key == idempotency_key,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).first()


def _locked_receipt_identity(
    session: Session, row: ActionReceipt
) -> TelegramActionReceiptRow | None:
    by_update = session.scalars(
        select(TelegramActionReceiptRow)
        .where(
            TelegramActionReceiptRow.bot_id == row.bot_id,
            TelegramActionReceiptRow.update_id == row.update_id,
        )
        .with_for_update()
    ).first()
    if by_update is not None:
        return by_update
    if row.callback_query_id is None:
        return None
    return session.scalars(
        select(TelegramActionReceiptRow)
        .where(
            TelegramActionReceiptRow.bot_id == row.bot_id,
            TelegramActionReceiptRow.callback_query_id == row.callback_query_id,
        )
        .with_for_update()
    ).first()


def _reject_or_converge_receipt(
    existing: TelegramActionReceiptRow, incoming: ActionReceipt
) -> None:
    if existing.replay_fingerprint == incoming.replay_fingerprint:
        return
    raise TelegramSecurityError(
        "Inbound Telegram replay conflicts with the original fingerprint.",
        reason=TelegramSecurityReason.REPLAY_CONFLICT,
        details={"bot_id": existing.bot_id, "update_id": str(existing.update_id)},
    )


def _reject_or_converge_outbox(existing: TelegramOutboxRow, incoming: OutboxRecord) -> None:
    if (
        existing.text == incoming.text
        and existing.chat_id == incoming.chat_id
        and existing.bot_id == incoming.bot_id
    ):
        return
    raise TelegramSecurityError(
        "Outbox idempotency key is bound to a different payload.",
        reason=TelegramSecurityReason.OUTBOX_CONFLICT,
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _aware_opt(value: datetime | None) -> datetime | None:
    return None if value is None else _aware(value)


def _challenge_to_row(row: EnrollmentChallenge) -> TelegramEnrollmentChallengeRow:
    return TelegramEnrollmentChallengeRow(
        challenge_id=row.challenge_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        bot_id=row.bot_id,
        token_hash=row.token_hash,
        state=row.state.value,
        expires_at=row.expires_at,
        created_at=row.created_at,
        completed_at=row.completed_at,
        binding_id=row.binding_id,
    )


def _apply_challenge(current: TelegramEnrollmentChallengeRow, row: EnrollmentChallenge) -> None:
    current.organization_id = row.organization_id
    current.user_id = row.user_id
    current.bot_id = row.bot_id
    current.token_hash = row.token_hash
    current.state = row.state.value
    current.expires_at = row.expires_at
    current.created_at = row.created_at
    current.completed_at = row.completed_at
    current.binding_id = row.binding_id


def _challenge_from_row(row: TelegramEnrollmentChallengeRow) -> EnrollmentChallenge:
    return EnrollmentChallenge(
        challenge_id=row.challenge_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        bot_id=row.bot_id,
        token_hash=row.token_hash,
        state=EnrollmentChallengeState(row.state),
        expires_at=_aware(row.expires_at),
        created_at=_aware(row.created_at),
        completed_at=_aware_opt(row.completed_at),
        binding_id=row.binding_id,
    )


def _binding_to_row(row: TelegramBinding) -> TelegramBindingRow:
    return TelegramBindingRow(
        binding_id=row.binding_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        telegram_user_id=row.telegram_user_id,
        chat_id=row.chat_id,
        chat_type=row.chat_type.value,
        bot_id=row.bot_id,
        state=row.state.value,
        verified_at=row.verified_at,
        revoked_at=row.revoked_at,
        allowed_actions=[action.value for action in row.allowed_actions],
    )


def _apply_binding(current: TelegramBindingRow, row: TelegramBinding) -> None:
    current.organization_id = row.organization_id
    current.user_id = row.user_id
    current.telegram_user_id = row.telegram_user_id
    current.chat_id = row.chat_id
    current.chat_type = row.chat_type.value
    current.bot_id = row.bot_id
    current.state = row.state.value
    current.verified_at = row.verified_at
    current.revoked_at = row.revoked_at
    current.allowed_actions = [action.value for action in row.allowed_actions]


def _binding_from_row(row: TelegramBindingRow) -> TelegramBinding:
    return TelegramBinding(
        binding_id=row.binding_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        telegram_user_id=row.telegram_user_id,
        chat_id=row.chat_id,
        chat_type=ChatType(row.chat_type),
        bot_id=row.bot_id,
        state=BindingState(row.state),
        verified_at=_aware(row.verified_at),
        revoked_at=_aware_opt(row.revoked_at),
        allowed_actions=tuple(TelegramRemoteAction(item) for item in row.allowed_actions),
    )


def _nonce_to_row(row: ActionNonce) -> TelegramActionNonceRow:
    return TelegramActionNonceRow(
        nonce_id=row.nonce_id,
        nonce_hash=row.nonce_hash,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        telegram_user_id=row.telegram_user_id,
        chat_id=row.chat_id,
        bot_id=row.bot_id,
        binding_id=row.binding_id,
        action=row.action.value,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        revision_id=row.revision_id,
        content_hash=row.content_hash,
        payload_hash=row.payload_hash,
        state=row.state.value,
        expires_at=row.expires_at,
        created_at=row.created_at,
        consumed_at=row.consumed_at,
        consumed_by_receipt_id=row.consumed_by_receipt_id,
    )


def _apply_nonce(current: TelegramActionNonceRow, row: ActionNonce) -> None:
    current.nonce_id = row.nonce_id
    current.nonce_hash = row.nonce_hash
    current.organization_id = row.organization_id
    current.user_id = row.user_id
    current.account_id = row.account_id
    current.telegram_user_id = row.telegram_user_id
    current.chat_id = row.chat_id
    current.bot_id = row.bot_id
    current.binding_id = row.binding_id
    current.action = row.action.value
    current.resource_type = row.resource_type
    current.resource_id = row.resource_id
    current.revision_id = row.revision_id
    current.content_hash = row.content_hash
    current.payload_hash = row.payload_hash
    current.state = row.state.value
    current.expires_at = row.expires_at
    current.created_at = row.created_at
    current.consumed_at = row.consumed_at
    current.consumed_by_receipt_id = row.consumed_by_receipt_id


def _nonce_from_row(row: TelegramActionNonceRow) -> ActionNonce:
    return ActionNonce(
        nonce_id=row.nonce_id,
        nonce_hash=row.nonce_hash,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        telegram_user_id=row.telegram_user_id,
        chat_id=row.chat_id,
        bot_id=row.bot_id,
        binding_id=row.binding_id,
        action=TelegramRemoteAction(row.action),
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        revision_id=row.revision_id,
        content_hash=row.content_hash,
        payload_hash=row.payload_hash,
        state=NonceState(row.state),
        expires_at=_aware(row.expires_at),
        created_at=_aware(row.created_at),
        consumed_at=_aware_opt(row.consumed_at),
        consumed_by_receipt_id=row.consumed_by_receipt_id,
    )


def _receipt_to_row(row: ActionReceipt) -> TelegramActionReceiptRow:
    return TelegramActionReceiptRow(
        receipt_id=row.receipt_id,
        bot_id=row.bot_id,
        update_id=row.update_id,
        callback_query_id=row.callback_query_id,
        message_id=row.message_id,
        telegram_user_id=row.telegram_user_id,
        chat_id=row.chat_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        nonce_hash=row.nonce_hash,
        action=None if row.action is None else row.action.value,
        payload_hash=row.payload_hash,
        replay_fingerprint=row.replay_fingerprint,
        state=row.state.value,
        reason_code=row.reason_code,
        authorization_intent_id=row.authorization_intent_id,
        binding_id=row.binding_id,
        effect_kind=row.effect_kind.value,
        transitions=_transitions_to_json(row.transitions),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply_receipt(current: TelegramActionReceiptRow, row: ActionReceipt) -> None:
    current.bot_id = row.bot_id
    current.update_id = row.update_id
    current.callback_query_id = row.callback_query_id
    current.message_id = row.message_id
    current.telegram_user_id = row.telegram_user_id
    current.chat_id = row.chat_id
    current.organization_id = row.organization_id
    current.user_id = row.user_id
    current.account_id = row.account_id
    current.nonce_hash = row.nonce_hash
    current.action = None if row.action is None else row.action.value
    current.payload_hash = row.payload_hash
    current.replay_fingerprint = row.replay_fingerprint
    current.state = row.state.value
    current.reason_code = row.reason_code
    current.authorization_intent_id = row.authorization_intent_id
    current.binding_id = row.binding_id
    current.effect_kind = row.effect_kind.value
    current.transitions = _transitions_to_json(row.transitions)
    current.created_at = row.created_at
    current.updated_at = row.updated_at


def _receipt_from_row(row: TelegramActionReceiptRow) -> ActionReceipt:
    return ActionReceipt(
        receipt_id=row.receipt_id,
        bot_id=row.bot_id,
        update_id=int(row.update_id),
        callback_query_id=row.callback_query_id,
        message_id=row.message_id,
        telegram_user_id=row.telegram_user_id,
        chat_id=row.chat_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        nonce_hash=row.nonce_hash,
        action=None if row.action is None else TelegramRemoteAction(row.action),
        payload_hash=row.payload_hash,
        replay_fingerprint=row.replay_fingerprint,
        state=ActionReceiptState(row.state),
        reason_code=row.reason_code,
        authorization_intent_id=row.authorization_intent_id,
        binding_id=row.binding_id,
        effect_kind=ActionEffectKind(row.effect_kind),
        transitions=_transitions_from_json(row.transitions),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _transitions_to_json(rows: tuple[ReceiptTransition, ...]) -> list[dict[str, object]]:
    return [
        {
            "sequence": item.sequence,
            "from_state": None if item.from_state is None else item.from_state.value,
            "to_state": item.to_state.value,
            "at": item.at.isoformat(),
            "reason_code": item.reason_code,
        }
        for item in rows
    ]


def _transitions_from_json(rows: list[dict[str, object]] | None) -> tuple[ReceiptTransition, ...]:
    if not rows:
        return ()
    parsed: list[ReceiptTransition] = []
    for item in rows:
        from_state = item.get("from_state")
        parsed.append(
            ReceiptTransition(
                sequence=int(item["sequence"]),  # type: ignore[arg-type]
                from_state=None if from_state is None else ActionReceiptState(str(from_state)),
                to_state=ActionReceiptState(str(item["to_state"])),
                at=_aware(_parse_datetime(item["at"])),
                reason_code=None if item.get("reason_code") is None else str(item["reason_code"]),
            )
        )
    return tuple(parsed)


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _intent_to_row(row: AuthorizationIntent) -> TelegramAuthorizationIntentRow:
    return TelegramAuthorizationIntentRow(
        intent_id=row.intent_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        resource_id=row.resource_id,
        revision_id=row.revision_id,
        content_hash=row.content_hash,
        payload_hash=row.payload_hash,
        receipt_id=row.receipt_id,
        created_at=row.created_at,
        action=row.action.value,
        executes=False,
        execution_attempted=False,
        execution_entry_path=None,
    )


def _intent_from_row(row: TelegramAuthorizationIntentRow) -> AuthorizationIntent:
    return AuthorizationIntent(
        intent_id=row.intent_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        resource_id=row.resource_id,
        revision_id=row.revision_id,
        content_hash=row.content_hash,
        payload_hash=row.payload_hash,
        receipt_id=row.receipt_id,
        created_at=_aware(row.created_at),
        action=TelegramRemoteAction.APPROVE,
        executes=False,
        execution_attempted=False,
        execution_entry_path=None,
    )


def _outbox_to_row(row: OutboxRecord) -> TelegramOutboxRow:
    return TelegramOutboxRow(
        outbox_id=row.outbox_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        binding_id=row.binding_id,
        bot_id=row.bot_id,
        chat_id=row.chat_id,
        idempotency_key=row.idempotency_key,
        kind=row.kind.value,
        text=row.text,
        state=row.state.value,
        attempt=row.attempt,
        lease_owner=row.lease_owner,
        lease_until=row.lease_until,
        transport_message_id=row.transport_message_id,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply_outbox(current: TelegramOutboxRow, row: OutboxRecord) -> None:
    current.organization_id = row.organization_id
    current.user_id = row.user_id
    current.binding_id = row.binding_id
    current.bot_id = row.bot_id
    current.chat_id = row.chat_id
    current.idempotency_key = row.idempotency_key
    current.kind = row.kind.value
    current.text = row.text
    current.state = row.state.value
    current.attempt = row.attempt
    current.lease_owner = row.lease_owner
    current.lease_until = row.lease_until
    current.transport_message_id = row.transport_message_id
    current.last_error = row.last_error
    current.created_at = row.created_at
    current.updated_at = row.updated_at


def _outbox_from_row(row: TelegramOutboxRow) -> OutboxRecord:
    return OutboxRecord(
        outbox_id=row.outbox_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        binding_id=row.binding_id,
        bot_id=row.bot_id,
        chat_id=row.chat_id,
        idempotency_key=row.idempotency_key,
        kind=OutboxKind(row.kind),
        text=row.text,
        state=OutboxState(row.state),
        attempt=row.attempt,
        lease_owner=row.lease_owner,
        lease_until=_aware_opt(row.lease_until),
        transport_message_id=row.transport_message_id,
        last_error=row.last_error,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )
