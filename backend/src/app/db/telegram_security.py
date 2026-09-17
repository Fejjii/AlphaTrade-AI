"""ORM models for the Telegram security protocol durable persistence.

These tables bind TelegramSecurityStore. They are not wired to HTTP, webhooks,
delivery workers, or execution. APPROVE intent rows cannot record execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramEnrollmentChallengeRow(Base):
    __tablename__ = "telegram_security_enrollment_challenges"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "challenge_id",
            name="uq_tgsec_challenges_org_id",
        ),
        UniqueConstraint("token_hash", name="uq_tgsec_challenges_token_hash"),
        UniqueConstraint(
            "organization_id",
            "token_hash",
            name="uq_tgsec_challenges_org_token_hash",
        ),
        Index(
            "ix_tgsec_challenges_org_user_bot_state",
            "organization_id",
            "user_id",
            "bot_id",
            "state",
        ),
        Index("ix_tgsec_challenges_binding_id", "binding_id"),
        CheckConstraint("char_length(token_hash) = 64", name="tgsec_challenge_hash_len"),
    )

    challenge_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    bot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    binding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class TelegramBindingRow(Base):
    __tablename__ = "telegram_security_bindings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "binding_id",
            name="uq_tgsec_bindings_org_id",
        ),
        Index(
            "uq_tgsec_bindings_active_org_user",
            "organization_id",
            "user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "uq_tgsec_bindings_active_bot_tg_user",
            "bot_id",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "uq_tgsec_bindings_active_bot_chat",
            "bot_id",
            "chat_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    binding_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    telegram_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_type: Mapped[str] = mapped_column(String(32), nullable=False)
    bot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class TelegramActionNonceRow(Base):
    __tablename__ = "telegram_security_action_nonces"
    __table_args__ = (
        UniqueConstraint("nonce_hash", name="uq_tgsec_nonces_hash"),
        UniqueConstraint(
            "organization_id",
            "nonce_hash",
            name="uq_tgsec_nonces_org_hash",
        ),
        UniqueConstraint(
            "organization_id",
            "nonce_id",
            name="uq_tgsec_nonces_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "nonce_hash",
            "payload_hash",
            name="uq_tgsec_nonces_org_hash_payload",
        ),
        CheckConstraint("char_length(nonce_hash) = 64", name="tgsec_nonce_hash_len"),
        CheckConstraint("char_length(payload_hash) = 64", name="tgsec_nonce_payload_hash_len"),
    )

    nonce_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    telegram_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by_receipt_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class TelegramActionReceiptRow(Base):
    __tablename__ = "telegram_security_action_receipts"
    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "update_id",
            name="uq_tgsec_receipts_bot_update",
        ),
        Index(
            "uq_tgsec_receipts_bot_callback",
            "bot_id",
            "callback_query_id",
            unique=True,
            postgresql_where=text("callback_query_id IS NOT NULL"),
        ),
        CheckConstraint("char_length(replay_fingerprint) = 64", name="tgsec_receipt_fp_len"),
        CheckConstraint("update_id >= 0", name="tgsec_receipt_update_id_min"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    callback_query_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    nonce_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    replay_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    authorization_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    binding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    effect_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    transitions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramAuthorizationIntentRow(Base):
    __tablename__ = "telegram_security_authorization_intents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "intent_id",
            name="uq_tgsec_intents_org_id",
        ),
        CheckConstraint("executes IS FALSE", name="tgsec_intent_never_executes"),
        CheckConstraint("execution_attempted IS FALSE", name="tgsec_intent_never_attempted"),
        CheckConstraint(
            "execution_entry_path IS NULL",
            name="tgsec_intent_no_execution_entry_path",
        ),
        CheckConstraint("action = 'APPROVE'", name="tgsec_intent_approve_only"),
    )

    intent_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    revision_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("telegram_security_action_receipts.receipt_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="APPROVE")
    executes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_entry_path: Mapped[str | None] = mapped_column(String(128), nullable=True)


class TelegramOutboxRow(Base):
    __tablename__ = "telegram_security_outbox"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_tgsec_outbox_org_idempotency",
        ),
        UniqueConstraint(
            "organization_id",
            "outbox_id",
            name="uq_tgsec_outbox_org_id",
        ),
        Index(
            "ix_tgsec_outbox_claim",
            "state",
            "lease_until",
            "created_at",
        ),
        CheckConstraint("attempt >= 0", name="tgsec_outbox_attempt_min"),
    )

    outbox_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    binding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    bot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(String(4096), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transport_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramProtocolAuditEventRow(Base):
    __tablename__ = "telegram_security_audit_events"
    __table_args__ = (Index("ix_tgsec_audit_org_at", "organization_id", "at"),)

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[list[list[str]]] = mapped_column(JSON, nullable=False)
