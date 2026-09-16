"""Persistence interfaces for the Telegram security protocol.

A later integration phase may bind these to PostgreSQL. This package does not
import ORM models or Alembic migrations.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.telegram_security.contracts import (
    ActionNonce,
    ActionReceipt,
    AuthorizationIntent,
    EnrollmentChallenge,
    OutboxRecord,
    ProtocolAuditEvent,
    TelegramBinding,
)
from app.telegram_security.errors import TelegramSecurityReason


class TelegramSecurityStore(Protocol):
    """Unit-of-work style store. Implementations must be transactional."""

    def transaction(self) -> AbstractContextManager[None]:
        """Hold the store lock / DB transaction for a protocol mutation."""

    def save_challenge(self, row: EnrollmentChallenge) -> None: ...

    def get_challenge_by_hash(self, token_hash: str) -> EnrollmentChallenge | None: ...

    def get_challenge_for_binding(self, binding_id: UUID) -> EnrollmentChallenge | None: ...

    def list_pending_challenges(
        self, *, organization_id: UUID, user_id: UUID, bot_id: str
    ) -> list[EnrollmentChallenge]: ...

    def cas_challenge(
        self,
        *,
        challenge_id: UUID,
        expected: EnrollmentChallenge,
        updated: EnrollmentChallenge,
    ) -> bool: ...

    def save_binding(self, row: TelegramBinding) -> None: ...

    def get_binding(self, binding_id: UUID) -> TelegramBinding | None: ...

    def get_active_binding_for_user(
        self, *, organization_id: UUID, user_id: UUID
    ) -> TelegramBinding | None: ...

    def get_active_binding_for_telegram_user(
        self, *, bot_id: str, telegram_user_id: str
    ) -> TelegramBinding | None: ...

    def get_active_binding_for_chat(
        self, *, bot_id: str, chat_id: str
    ) -> TelegramBinding | None: ...

    def save_nonce(self, row: ActionNonce) -> None: ...

    def get_nonce_by_hash(self, nonce_hash: str) -> ActionNonce | None: ...

    def cas_nonce(
        self, *, nonce_hash: str, expected: ActionNonce, updated: ActionNonce
    ) -> bool: ...

    def get_callback_receipt(
        self, *, bot_id: str, callback_query_id: str
    ) -> ActionReceipt | None: ...

    def get_update_receipt(self, *, bot_id: str, update_id: int) -> ActionReceipt | None: ...

    def save_receipt(self, row: ActionReceipt) -> None: ...

    def save_authorization_intent(self, row: AuthorizationIntent) -> None: ...

    def get_authorization_intent(self, intent_id: UUID) -> AuthorizationIntent | None: ...

    def get_outbox(self, outbox_id: UUID) -> OutboxRecord | None: ...

    def get_outbox_by_idempotency(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> OutboxRecord | None: ...

    def save_outbox(self, row: OutboxRecord) -> None: ...

    def claim_outbox_batch(
        self,
        *,
        now: datetime,
        limit: int,
        lease_owner: str,
        lease_for: timedelta,
        retryable_reasons: frozenset[TelegramSecurityReason] | None = None,
    ) -> list[OutboxRecord]: ...

    def append_audit(self, event: ProtocolAuditEvent) -> None: ...

    def list_audits(self) -> list[ProtocolAuditEvent]: ...

    def authorization_intents(self) -> list[AuthorizationIntent]: ...
