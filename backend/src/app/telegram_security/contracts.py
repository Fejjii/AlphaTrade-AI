"""Immutable contracts for the isolated Telegram security protocol."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.telegram_security.actions import ActionEffectKind, TelegramRemoteAction


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ChatType(StrEnum):
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class EnrollmentChallengeState(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class BindingState(StrEnum):
    VERIFIED = "VERIFIED"
    REVOKED = "REVOKED"


class NonceState(StrEnum):
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ActionReceiptState(StrEnum):
    RECEIVED = "RECEIVED"
    CLAIMED = "CLAIMED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    RETRYABLE = "RETRYABLE"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxState(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RETRYABLE = "RETRYABLE"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxKind(StrEnum):
    PRIVATE_MESSAGE = "PRIVATE_MESSAGE"


class TelegramActorIdentity(FrozenContract):
    bot_id: str = Field(min_length=1, max_length=64)
    telegram_user_id: str = Field(min_length=1, max_length=64)
    chat_id: str = Field(min_length=1, max_length=64)
    chat_type: ChatType


class MessageIdentity(TelegramActorIdentity):
    update_id: int = Field(ge=0)
    message_id: str = Field(min_length=1, max_length=64)


class CallbackIdentity(TelegramActorIdentity):
    update_id: int = Field(ge=0)
    callback_query_id: str = Field(min_length=1, max_length=128)


class TelegramInboundUpdate(FrozenContract):
    """Authoritative inbound Telegram update envelope.

    ``body_size`` is the actual Telegram request payload size in bytes (raw
    update / request body). It is never derived from nonce or enrollment-token
    length. Webhook wiring is out of scope; a later adapter MUST pass the raw
    body length here.
    """

    update_type: str = Field(min_length=1, max_length=64)
    body_size: int = Field(ge=0)


class InboundReplayFingerprint(FrozenContract):
    """Immutable semantic content bound to one Telegram transport identity."""

    telegram_user_id: str = Field(min_length=1, max_length=64)
    chat_id: str = Field(min_length=1, max_length=64)
    bot_id: str = Field(min_length=1, max_length=64)
    secret_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    action: str | None = None
    organization_id: str | None = None
    user_id: str | None = None
    account_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    revision_id: str | None = None
    content_hash: str | None = None
    payload_hash: str | None = None


class ActionPayload(FrozenContract):
    """Exact payload bound to one nonce. Callback data carries only the nonce."""

    action: TelegramRemoteAction
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: UUID
    revision_id: UUID | None = None
    content_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class EnrollmentChallenge(FrozenContract):
    challenge_id: UUID
    organization_id: UUID
    user_id: UUID
    bot_id: str
    token_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    state: EnrollmentChallengeState
    expires_at: datetime
    created_at: datetime
    completed_at: datetime | None = None
    binding_id: UUID | None = None


class TelegramBinding(FrozenContract):
    binding_id: UUID
    organization_id: UUID
    user_id: UUID
    telegram_user_id: str
    chat_id: str
    chat_type: ChatType
    bot_id: str
    state: BindingState
    verified_at: datetime
    revoked_at: datetime | None = None
    allowed_actions: tuple[TelegramRemoteAction, ...]


class ActionNonce(FrozenContract):
    nonce_id: UUID
    nonce_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    telegram_user_id: str
    chat_id: str
    bot_id: str
    binding_id: UUID
    action: TelegramRemoteAction
    resource_type: str
    resource_id: UUID
    revision_id: UUID | None
    content_hash: str
    payload_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    state: NonceState
    expires_at: datetime
    created_at: datetime
    consumed_at: datetime | None = None
    consumed_by_receipt_id: UUID | None = None


class ReceiptTransition(FrozenContract):
    sequence: int = Field(ge=1)
    from_state: ActionReceiptState | None
    to_state: ActionReceiptState
    at: datetime
    reason_code: str | None = None


class ActionReceipt(FrozenContract):
    receipt_id: UUID
    bot_id: str
    update_id: int
    callback_query_id: str | None = None
    message_id: str | None = None
    telegram_user_id: str
    chat_id: str
    organization_id: UUID | None = None
    user_id: UUID | None = None
    account_id: UUID | None = None
    nonce_hash: str | None = None
    action: TelegramRemoteAction | None = None
    payload_hash: str | None = None
    replay_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    state: ActionReceiptState
    reason_code: str | None = None
    authorization_intent_id: UUID | None = None
    binding_id: UUID | None = None
    effect_kind: ActionEffectKind = ActionEffectKind.NONE
    transitions: tuple[ReceiptTransition, ...] = ()
    created_at: datetime
    updated_at: datetime


class AuthorizationIntent(FrozenContract):
    """Protocol-level APPROVE intent. This is not an execution command."""

    intent_id: UUID
    organization_id: UUID
    user_id: UUID
    account_id: UUID
    resource_id: UUID
    revision_id: UUID
    content_hash: str
    payload_hash: str
    receipt_id: UUID
    created_at: datetime
    action: Literal[TelegramRemoteAction.APPROVE] = TelegramRemoteAction.APPROVE
    executes: Literal[False] = False
    execution_attempted: Literal[False] = False
    execution_entry_path: None = None


class OutboxRecord(FrozenContract):
    outbox_id: UUID
    organization_id: UUID
    user_id: UUID
    binding_id: UUID | None
    bot_id: str
    chat_id: str
    idempotency_key: str = Field(min_length=1, max_length=128)
    kind: OutboxKind
    text: str = Field(min_length=1, max_length=4096)
    state: OutboxState
    attempt: int = Field(ge=0)
    lease_owner: str | None = None
    lease_until: datetime | None = None
    transport_message_id: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProtocolAuditEvent(FrozenContract):
    event_id: UUID
    at: datetime
    event_type: str = Field(min_length=1, max_length=64)
    organization_id: UUID | None = None
    user_id: UUID | None = None
    reason_code: str | None = None
    details: tuple[tuple[str, str], ...] = ()


class EnrollmentStartResult(FrozenContract):
    challenge: EnrollmentChallenge
    token: str = Field(min_length=16, max_length=64)


class EnrollmentCompleteResult(FrozenContract):
    challenge: EnrollmentChallenge
    binding: TelegramBinding


class IssueNonceResult(FrozenContract):
    nonce: ActionNonce
    token: str = Field(min_length=16, max_length=64)


class ActionOutcome(FrozenContract):
    receipt: ActionReceipt
    replayed: bool
    state_changed: bool
    reason_code: str | None = None
    authorization_intent: AuthorizationIntent | None = None
    effect_kind: ActionEffectKind = ActionEffectKind.NONE
    executed: Literal[False] = False
    execution_attempted: Literal[False] = False
    execution_command_id: None = None


class DeliveryAttempt(FrozenContract):
    outbox: OutboxRecord
    accepted: bool
    retryable: bool
    error_code: str | None = None
    transport_message_id: str | None = None
