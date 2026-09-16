"""Deterministic in-memory Telegram security store.

Replaces PostgreSQL for this isolated foundation. All mutations under one
re-entrant lock so receipt + outbox writes are atomic from the protocol's
point of view.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import RLock
from uuid import UUID

from app.telegram_security.contracts import (
    ActionNonce,
    ActionReceipt,
    AuthorizationIntent,
    EnrollmentChallenge,
    OutboxRecord,
    OutboxState,
    ProtocolAuditEvent,
    TelegramBinding,
)
from app.telegram_security.errors import TelegramSecurityReason


class InMemoryTelegramSecurityStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._challenges: dict[UUID, EnrollmentChallenge] = {}
        self._challenges_by_hash: dict[str, UUID] = {}
        self._bindings: dict[UUID, TelegramBinding] = {}
        self._nonces: dict[str, ActionNonce] = {}
        self._receipts: dict[UUID, ActionReceipt] = {}
        self._receipts_by_callback: dict[tuple[str, str], UUID] = {}
        self._receipts_by_update: dict[tuple[str, int], UUID] = {}
        self._intents: dict[UUID, AuthorizationIntent] = {}
        self._outbox: dict[UUID, OutboxRecord] = {}
        self._outbox_by_key: dict[tuple[UUID, str], UUID] = {}
        self._audits: list[ProtocolAuditEvent] = []

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def save_challenge(self, row: EnrollmentChallenge) -> None:
        with self._lock:
            self._challenges[row.challenge_id] = row
            self._challenges_by_hash[row.token_hash] = row.challenge_id

    def get_challenge_by_hash(self, token_hash: str) -> EnrollmentChallenge | None:
        with self._lock:
            challenge_id = self._challenges_by_hash.get(token_hash)
            if challenge_id is None:
                return None
            return self._challenges.get(challenge_id)

    def get_challenge_for_binding(self, binding_id: UUID) -> EnrollmentChallenge | None:
        with self._lock:
            for row in self._challenges.values():
                if row.binding_id == binding_id:
                    return row
            return None

    def list_pending_challenges(
        self, *, organization_id: UUID, user_id: UUID, bot_id: str
    ) -> list[EnrollmentChallenge]:
        with self._lock:
            return [
                row
                for row in self._challenges.values()
                if row.organization_id == organization_id
                and row.user_id == user_id
                and row.bot_id == bot_id
                and row.state.value == "PENDING"
            ]

    def cas_challenge(
        self,
        *,
        challenge_id: UUID,
        expected: EnrollmentChallenge,
        updated: EnrollmentChallenge,
    ) -> bool:
        with self._lock:
            current = self._challenges.get(challenge_id)
            if current is None or current != expected:
                return False
            self._challenges[challenge_id] = updated
            self._challenges_by_hash[updated.token_hash] = challenge_id
            return True

    def save_binding(self, row: TelegramBinding) -> None:
        with self._lock:
            self._bindings[row.binding_id] = row

    def get_binding(self, binding_id: UUID) -> TelegramBinding | None:
        with self._lock:
            return self._bindings.get(binding_id)

    def get_active_binding_for_user(
        self, *, organization_id: UUID, user_id: UUID
    ) -> TelegramBinding | None:
        with self._lock:
            for row in self._bindings.values():
                if (
                    row.organization_id == organization_id
                    and row.user_id == user_id
                    and row.revoked_at is None
                ):
                    return row
            return None

    def get_active_binding_for_telegram_user(
        self, *, bot_id: str, telegram_user_id: str
    ) -> TelegramBinding | None:
        with self._lock:
            for row in self._bindings.values():
                if (
                    row.bot_id == bot_id
                    and row.telegram_user_id == telegram_user_id
                    and row.revoked_at is None
                ):
                    return row
            return None

    def get_active_binding_for_chat(self, *, bot_id: str, chat_id: str) -> TelegramBinding | None:
        with self._lock:
            for row in self._bindings.values():
                if row.bot_id == bot_id and row.chat_id == chat_id and row.revoked_at is None:
                    return row
            return None

    def save_nonce(self, row: ActionNonce) -> None:
        with self._lock:
            self._nonces[row.nonce_hash] = row

    def get_nonce_by_hash(self, nonce_hash: str) -> ActionNonce | None:
        with self._lock:
            return self._nonces.get(nonce_hash)

    def cas_nonce(self, *, nonce_hash: str, expected: ActionNonce, updated: ActionNonce) -> bool:
        with self._lock:
            current = self._nonces.get(nonce_hash)
            if current is None or current != expected:
                return False
            if updated.nonce_hash != nonce_hash:
                del self._nonces[nonce_hash]
            self._nonces[updated.nonce_hash] = updated
            return True

    def get_callback_receipt(self, *, bot_id: str, callback_query_id: str) -> ActionReceipt | None:
        with self._lock:
            receipt_id = self._receipts_by_callback.get((bot_id, callback_query_id))
            if receipt_id is None:
                return None
            return self._receipts.get(receipt_id)

    def get_update_receipt(self, *, bot_id: str, update_id: int) -> ActionReceipt | None:
        with self._lock:
            receipt_id = self._receipts_by_update.get((bot_id, update_id))
            if receipt_id is None:
                return None
            return self._receipts.get(receipt_id)

    def save_receipt(self, row: ActionReceipt) -> None:
        with self._lock:
            self._receipts[row.receipt_id] = row
            self._receipts_by_update[(row.bot_id, row.update_id)] = row.receipt_id
            if row.callback_query_id is not None:
                self._receipts_by_callback[(row.bot_id, row.callback_query_id)] = row.receipt_id

    def save_authorization_intent(self, row: AuthorizationIntent) -> None:
        with self._lock:
            self._intents[row.intent_id] = row

    def get_authorization_intent(self, intent_id: UUID) -> AuthorizationIntent | None:
        with self._lock:
            return self._intents.get(intent_id)

    def get_outbox(self, outbox_id: UUID) -> OutboxRecord | None:
        with self._lock:
            return self._outbox.get(outbox_id)

    def get_outbox_by_idempotency(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> OutboxRecord | None:
        with self._lock:
            outbox_id = self._outbox_by_key.get((organization_id, idempotency_key))
            if outbox_id is None:
                return None
            return self._outbox.get(outbox_id)

    def save_outbox(self, row: OutboxRecord) -> None:
        with self._lock:
            self._outbox[row.outbox_id] = row
            self._outbox_by_key[(row.organization_id, row.idempotency_key)] = row.outbox_id

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
        claimed: list[OutboxRecord] = []
        with self._lock:
            for row in sorted(self._outbox.values(), key=lambda item: item.created_at):
                if len(claimed) >= limit:
                    break
                if not _is_claimable(row, now=now):
                    continue
                updated = row.model_copy(
                    update={
                        "state": OutboxState.CLAIMED,
                        "lease_owner": lease_owner,
                        "lease_until": now + lease_for,
                        "updated_at": now,
                    }
                )
                self._outbox[row.outbox_id] = updated
                claimed.append(updated)
        return claimed

    def append_audit(self, event: ProtocolAuditEvent) -> None:
        with self._lock:
            self._audits.append(event)

    def list_audits(self) -> list[ProtocolAuditEvent]:
        with self._lock:
            return list(self._audits)

    def authorization_intents(self) -> list[AuthorizationIntent]:
        with self._lock:
            return list(self._intents.values())


def _is_claimable(row: OutboxRecord, *, now: datetime) -> bool:
    if row.state is OutboxState.PENDING or row.state is OutboxState.RETRYABLE:
        return True
    if row.state is OutboxState.CLAIMED:
        return row.lease_until is None or row.lease_until <= now
    return False
