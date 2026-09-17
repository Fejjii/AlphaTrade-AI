"""Isolated Telegram security protocol.

Enrollment, nonce, receipt, authorization-boundary, outbox, and delivery
acknowledgement live here. The protocol never imports execution services, never
invokes ``EXECUTE_PAPER_PLAN``, and is disabled until the caller passes
``enabled=True``. HTTP webhook wiring is intentionally absent.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.telegram_security.actions import (
    ALLOWED_TELEGRAM_UPDATE_TYPES,
    AVAILABLE_TELEGRAM_ACTIONS,
    MAX_INBOUND_UPDATE_BYTES,
    TelegramRemoteAction,
    approve_creates_authorization_intent_only,
    effect_kind_for,
    is_telegram_action_available,
)
from app.telegram_security.clock import Clock, FrozenClock
from app.telegram_security.contracts import (
    ActionNonce,
    ActionOutcome,
    ActionPayload,
    ActionReceipt,
    ActionReceiptState,
    AuthorizationIntent,
    BindingState,
    CallbackIdentity,
    ChatType,
    DeliveryAttempt,
    EnrollmentChallenge,
    EnrollmentChallengeState,
    EnrollmentCompleteResult,
    EnrollmentStartResult,
    InboundReplayFingerprint,
    IssueNonceResult,
    MessageIdentity,
    NonceState,
    OutboxKind,
    OutboxRecord,
    OutboxState,
    ProtocolAuditEvent,
    ReceiptTransition,
    TelegramBinding,
    TelegramInboundUpdate,
)
from app.telegram_security.errors import (
    TelegramInteractionDisabledError,
    TelegramSecurityError,
    TelegramSecurityReason,
)
from app.telegram_security.hashing import (
    TokenFactory,
    generate_opaque_token,
    hash_secret,
    inbound_fingerprint_digest,
    payload_binding_hash,
    secrets_equal,
)
from app.telegram_security.memory import InMemoryTelegramSecurityStore
from app.telegram_security.persistence import TelegramSecurityStore
from app.telegram_security.rate_limit import ProtocolRateLimiter, RateLimitPolicy
from app.telegram_security.transport import FakeTelegramTransport, TelegramTransport


class TelegramSecurityProtocol:
    def __init__(
        self,
        *,
        store: TelegramSecurityStore,
        transport: TelegramTransport,
        clock: Clock,
        enabled: bool = False,
        token_factory: TokenFactory | None = None,
        rate_limiter: ProtocolRateLimiter | None = None,
        enrollment_ttl: timedelta = timedelta(minutes=15),
        nonce_ttl: timedelta = timedelta(minutes=10),
        outbox_max_attempts: int = 3,
        outbox_lease: timedelta = timedelta(seconds=30),
        lease_owner: str = "telegram-security-protocol",
    ) -> None:
        self._store = store
        self._transport = transport
        self._clock = clock
        self._enabled = enabled
        self._token_factory = token_factory or generate_opaque_token
        self._rate = rate_limiter or ProtocolRateLimiter(clock)
        self._enrollment_ttl = enrollment_ttl
        self._nonce_ttl = nonce_ttl
        self._outbox_max_attempts = outbox_max_attempts
        self._outbox_lease = outbox_lease
        self._lease_owner = lease_owner

    @classmethod
    def in_memory(
        cls,
        *,
        enabled: bool = False,
        clock: Clock | None = None,
        transport: TelegramTransport | None = None,
        token_factory: TokenFactory | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
    ) -> TelegramSecurityProtocol:
        resolved_clock = clock or FrozenClock()
        limiter = (
            ProtocolRateLimiter(resolved_clock, policy=rate_limit_policy)
            if rate_limit_policy is not None
            else ProtocolRateLimiter(resolved_clock)
        )
        return cls(
            store=InMemoryTelegramSecurityStore(),
            transport=transport or FakeTelegramTransport(),
            clock=resolved_clock,
            enabled=enabled,
            token_factory=token_factory,
            rate_limiter=limiter,
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def store(self) -> TelegramSecurityStore:
        return self._store

    @property
    def execution_attempt_count(self) -> int:
        """Always zero: this protocol has no execution path."""
        return 0

    def assert_inbound_update_allowed(self, *, inbound: TelegramInboundUpdate) -> None:
        """Reject disallowed update types and oversized inbound Telegram payloads.

        ``inbound.body_size`` is the authoritative raw Telegram request size.
        Callers must not substitute nonce or enrollment-token length.
        """
        self._require_enabled()
        if inbound.update_type not in ALLOWED_TELEGRAM_UPDATE_TYPES:
            raise TelegramSecurityError(
                "Telegram update type is not allowed.",
                reason=TelegramSecurityReason.UPDATE_TYPE_REJECTED,
                details={"update_type": inbound.update_type},
            )
        if inbound.body_size > MAX_INBOUND_UPDATE_BYTES:
            raise TelegramSecurityError(
                "Telegram update exceeds bounded request size.",
                reason=TelegramSecurityReason.UPDATE_TOO_LARGE,
                details={"body_size": str(inbound.body_size)},
            )

    def start_enrollment(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        bot_id: str,
    ) -> EnrollmentStartResult:
        self._require_enabled()
        self._rate.check_enrollment(organization_id=str(organization_id), user_id=str(user_id))
        now = self._clock.now()
        with self._store.transaction():
            for pending in self._store.list_pending_challenges(
                organization_id=organization_id, user_id=user_id, bot_id=bot_id
            ):
                revoked = pending.model_copy(update={"state": EnrollmentChallengeState.REVOKED})
                self._store.cas_challenge(
                    challenge_id=pending.challenge_id, expected=pending, updated=revoked
                )
            token = self._token_factory()
            challenge = EnrollmentChallenge(
                challenge_id=uuid4(),
                organization_id=organization_id,
                user_id=user_id,
                bot_id=bot_id,
                token_hash=hash_secret(token),
                state=EnrollmentChallengeState.PENDING,
                expires_at=now + self._enrollment_ttl,
                created_at=now,
            )
            self._store.save_challenge(challenge)
            self._audit(
                "enrollment_started",
                organization_id=organization_id,
                user_id=user_id,
                details=(("bot_id", bot_id), ("challenge_id", str(challenge.challenge_id))),
            )
        return EnrollmentStartResult(challenge=challenge, token=token)

    def complete_enrollment(
        self,
        *,
        token: str,
        identity: MessageIdentity,
        inbound: TelegramInboundUpdate,
    ) -> EnrollmentCompleteResult:
        self._require_enabled()
        self.assert_inbound_update_allowed(inbound=inbound)
        self._require_inbound_type(inbound, expected="message")
        now = self._clock.now()
        presented = token.strip()
        with self._store.transaction():
            replay_fingerprint = inbound_fingerprint_digest(
                self._enrollment_replay_fingerprint(identity=identity, presented=presented)
            )
            existing_receipt = self._store.get_update_receipt(
                bot_id=identity.bot_id, update_id=identity.update_id
            )
            if existing_receipt is not None:
                self._require_identical_replay(existing_receipt, replay_fingerprint)
                return self._replay_enrollment(existing_receipt)
            self._rate.check_callback(
                bot_id=identity.bot_id,
                telegram_user_id=identity.telegram_user_id,
                chat_id=identity.chat_id,
            )
            if identity.chat_type is not ChatType.PRIVATE:
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.CHAT_NOT_PRIVATE,
                    now=now,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Telegram enrollment requires a private chat.",
                    reason=TelegramSecurityReason.CHAT_NOT_PRIVATE,
                )
            if not presented or presented == identity.chat_id:
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.ENROLLMENT_CHAT_ID_ONLY,
                    now=now,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "A Telegram chat id is not enrollment.",
                    reason=TelegramSecurityReason.ENROLLMENT_CHAT_ID_ONLY,
                )
            challenge = self._store.get_challenge_by_hash(hash_secret(presented))
            if challenge is None:
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.ENROLLMENT_NOT_FOUND,
                    now=now,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Enrollment challenge was not found.",
                    reason=TelegramSecurityReason.ENROLLMENT_NOT_FOUND,
                )
            if challenge.bot_id != identity.bot_id:
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.ENROLLMENT_WRONG_BOT,
                    now=now,
                    organization_id=challenge.organization_id,
                    user_id=challenge.user_id,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Enrollment challenge belongs to a different bot.",
                    reason=TelegramSecurityReason.ENROLLMENT_WRONG_BOT,
                )
            if challenge.state is EnrollmentChallengeState.COMPLETED:
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.ENROLLMENT_USED,
                    now=now,
                    organization_id=challenge.organization_id,
                    user_id=challenge.user_id,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Enrollment challenge has already been used.",
                    reason=TelegramSecurityReason.ENROLLMENT_USED,
                )
            if challenge.state is not EnrollmentChallengeState.PENDING:
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.ENROLLMENT_USED,
                    now=now,
                    organization_id=challenge.organization_id,
                    user_id=challenge.user_id,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Enrollment challenge is not pending.",
                    reason=TelegramSecurityReason.ENROLLMENT_USED,
                )
            if now >= challenge.expires_at:
                expired = challenge.model_copy(update={"state": EnrollmentChallengeState.EXPIRED})
                self._store.cas_challenge(
                    challenge_id=challenge.challenge_id, expected=challenge, updated=expired
                )
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.ENROLLMENT_EXPIRED,
                    now=now,
                    organization_id=challenge.organization_id,
                    user_id=challenge.user_id,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Enrollment challenge has expired.",
                    reason=TelegramSecurityReason.ENROLLMENT_EXPIRED,
                )
            existing_tg = self._store.get_active_binding_for_telegram_user(
                bot_id=identity.bot_id, telegram_user_id=identity.telegram_user_id
            )
            if existing_tg is not None and (
                existing_tg.user_id != challenge.user_id
                or existing_tg.organization_id != challenge.organization_id
            ):
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.TELEGRAM_USER_ALREADY_BOUND,
                    now=now,
                    organization_id=challenge.organization_id,
                    user_id=challenge.user_id,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Telegram user is already bound to another AlphaTrade user.",
                    reason=TelegramSecurityReason.TELEGRAM_USER_ALREADY_BOUND,
                )
            existing_chat = self._store.get_active_binding_for_chat(
                bot_id=identity.bot_id, chat_id=identity.chat_id
            )
            if existing_chat is not None and (
                existing_chat.user_id != challenge.user_id
                or existing_chat.organization_id != challenge.organization_id
            ):
                self._record_enrollment_rejection(
                    identity,
                    reason=TelegramSecurityReason.TELEGRAM_USER_ALREADY_BOUND,
                    now=now,
                    organization_id=challenge.organization_id,
                    user_id=challenge.user_id,
                    replay_fingerprint=replay_fingerprint,
                )
                raise TelegramSecurityError(
                    "Telegram chat is already bound to another AlphaTrade user.",
                    reason=TelegramSecurityReason.TELEGRAM_USER_ALREADY_BOUND,
                )
            previous = self._store.get_active_binding_for_user(
                organization_id=challenge.organization_id, user_id=challenge.user_id
            )
            if previous is not None:
                self._store.save_binding(
                    previous.model_copy(update={"state": BindingState.REVOKED, "revoked_at": now})
                )
            allowed = tuple(sorted(AVAILABLE_TELEGRAM_ACTIONS, key=lambda action: action.value))
            binding = TelegramBinding(
                binding_id=uuid4(),
                organization_id=challenge.organization_id,
                user_id=challenge.user_id,
                telegram_user_id=identity.telegram_user_id,
                chat_id=identity.chat_id,
                chat_type=ChatType.PRIVATE,
                bot_id=identity.bot_id,
                state=BindingState.VERIFIED,
                verified_at=now,
                allowed_actions=allowed,
            )
            completed = challenge.model_copy(
                update={
                    "state": EnrollmentChallengeState.COMPLETED,
                    "completed_at": now,
                    "binding_id": binding.binding_id,
                }
            )
            if not self._store.cas_challenge(
                challenge_id=challenge.challenge_id, expected=challenge, updated=completed
            ):
                raise TelegramSecurityError(
                    "Enrollment challenge has already been used.",
                    reason=TelegramSecurityReason.ENROLLMENT_USED,
                )
            self._store.save_binding(binding)
            receipt = self._new_receipt(
                bot_id=identity.bot_id,
                update_id=identity.update_id,
                telegram_user_id=identity.telegram_user_id,
                chat_id=identity.chat_id,
                now=now,
                message_id=identity.message_id,
                organization_id=binding.organization_id,
                user_id=binding.user_id,
                binding_id=binding.binding_id,
                state=ActionReceiptState.APPLIED,
                replay_fingerprint=replay_fingerprint,
            )
            self._store.save_receipt(receipt)
            self._audit(
                "enrollment_completed",
                organization_id=binding.organization_id,
                user_id=binding.user_id,
                details=(
                    ("binding_id", str(binding.binding_id)),
                    ("chat_type", binding.chat_type.value),
                ),
            )
        return EnrollmentCompleteResult(challenge=completed, binding=binding)

    def issue_action_nonce(self, *, binding_id: UUID, payload: ActionPayload) -> IssueNonceResult:
        self._require_enabled()
        now = self._clock.now()
        with self._store.transaction():
            binding = self._require_active_binding(binding_id)
            self._assert_payload_matches_binding(binding, payload)
            if payload.action is TelegramRemoteAction.CLOSE:
                raise TelegramSecurityError(
                    "Telegram CLOSE is unavailable.",
                    reason=TelegramSecurityReason.CLOSE_UNAVAILABLE,
                )
            if not is_telegram_action_available(payload.action):
                raise TelegramSecurityError(
                    "Telegram action is not allowed.",
                    reason=TelegramSecurityReason.ACTION_NOT_ALLOWED,
                    details={"action": payload.action.value},
                )
            if payload.action not in binding.allowed_actions:
                raise TelegramSecurityError(
                    "Action is not allowed for this binding.",
                    reason=TelegramSecurityReason.ACTION_NOT_ALLOWED,
                    details={"action": payload.action.value},
                )
            if payload.action is TelegramRemoteAction.APPROVE and payload.revision_id is None:
                raise TelegramSecurityError(
                    "APPROVE requires an exact revision id.",
                    reason=TelegramSecurityReason.ACTION_NOT_ALLOWED,
                )
            token = self._token_factory()
            nonce = ActionNonce(
                nonce_id=uuid4(),
                nonce_hash=hash_secret(token),
                organization_id=payload.organization_id,
                user_id=payload.user_id,
                account_id=payload.account_id,
                telegram_user_id=binding.telegram_user_id,
                chat_id=binding.chat_id,
                bot_id=binding.bot_id,
                binding_id=binding.binding_id,
                action=payload.action,
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
                revision_id=payload.revision_id,
                content_hash=payload.content_hash,
                payload_hash=payload_binding_hash(payload),
                state=NonceState.ISSUED,
                expires_at=now + self._nonce_ttl,
                created_at=now,
            )
            self._store.save_nonce(nonce)
            self._audit(
                "nonce_issued",
                organization_id=binding.organization_id,
                user_id=binding.user_id,
                details=(
                    ("action", payload.action.value),
                    ("nonce_id", str(nonce.nonce_id)),
                    ("account_id", str(payload.account_id)),
                ),
            )
        return IssueNonceResult(nonce=nonce, token=token)

    def receive_callback(
        self,
        *,
        identity: CallbackIdentity,
        nonce_token: str,
        presented_payload: ActionPayload,
        inbound: TelegramInboundUpdate,
    ) -> ActionOutcome:
        self._require_enabled()
        self.assert_inbound_update_allowed(inbound=inbound)
        self._require_inbound_type(inbound, expected="callback_query")
        now = self._clock.now()
        with self._store.transaction():
            replay_fingerprint = inbound_fingerprint_digest(
                self._callback_replay_fingerprint(
                    identity=identity,
                    nonce_token=nonce_token,
                    presented=presented_payload,
                )
            )
            existing = self._store.get_callback_receipt(
                bot_id=identity.bot_id, callback_query_id=identity.callback_query_id
            )
            if existing is None:
                existing = self._store.get_update_receipt(
                    bot_id=identity.bot_id, update_id=identity.update_id
                )
            if existing is not None:
                self._require_identical_replay(existing, replay_fingerprint)
                return self._replay_action(existing)
            self._rate.check_callback(
                bot_id=identity.bot_id,
                telegram_user_id=identity.telegram_user_id,
                chat_id=identity.chat_id,
            )
            receipt = self._new_receipt(
                bot_id=identity.bot_id,
                update_id=identity.update_id,
                telegram_user_id=identity.telegram_user_id,
                chat_id=identity.chat_id,
                now=now,
                callback_query_id=identity.callback_query_id,
                organization_id=presented_payload.organization_id,
                user_id=presented_payload.user_id,
                account_id=presented_payload.account_id,
                action=presented_payload.action,
                payload_hash=payload_binding_hash(presented_payload),
                replay_fingerprint=replay_fingerprint,
            )
            claimed = self._transition(receipt, to=ActionReceiptState.CLAIMED, now=now)
            self._store.save_receipt(claimed)
            if identity.chat_type is not ChatType.PRIVATE:
                return self._finalize_rejection(
                    claimed, TelegramSecurityReason.CHAT_NOT_PRIVATE, now
                )
            nonce = self._store.get_nonce_by_hash(hash_secret(nonce_token.strip()))
            if nonce is None:
                return self._finalize_rejection(
                    claimed, TelegramSecurityReason.NONCE_NOT_FOUND, now
                )
            claimed = claimed.model_copy(update={"nonce_hash": nonce.nonce_hash})
            reason = self._authorize_callback(
                identity=identity,
                nonce=nonce,
                presented=presented_payload,
                now=now,
            )
            if reason is not None:
                if reason is TelegramSecurityReason.NONCE_EXPIRED:
                    expired = nonce.model_copy(update={"state": NonceState.EXPIRED})
                    self._store.cas_nonce(
                        nonce_hash=nonce.nonce_hash, expected=nonce, updated=expired
                    )
                return self._finalize_rejection(claimed, reason, now)
            consumed = nonce.model_copy(
                update={
                    "state": NonceState.CONSUMED,
                    "consumed_at": now,
                    "consumed_by_receipt_id": claimed.receipt_id,
                }
            )
            if not self._store.cas_nonce(
                nonce_hash=nonce.nonce_hash, expected=nonce, updated=consumed
            ):
                return self._finalize_rejection(claimed, TelegramSecurityReason.NONCE_USED, now)
            intent: AuthorizationIntent | None = None
            effect = effect_kind_for(presented_payload.action)
            if approve_creates_authorization_intent_only(presented_payload.action):
                if presented_payload.revision_id is None:
                    return self._finalize_rejection(
                        claimed, TelegramSecurityReason.ACTION_NOT_ALLOWED, now
                    )
                intent = AuthorizationIntent(
                    intent_id=uuid4(),
                    organization_id=presented_payload.organization_id,
                    user_id=presented_payload.user_id,
                    account_id=presented_payload.account_id,
                    resource_id=presented_payload.resource_id,
                    revision_id=presented_payload.revision_id,
                    content_hash=presented_payload.content_hash,
                    payload_hash=nonce.payload_hash,
                    receipt_id=claimed.receipt_id,
                    created_at=now,
                )
                self._store.save_authorization_intent(intent)
                self._enqueue_unlocked(
                    organization_id=nonce.organization_id,
                    user_id=nonce.user_id,
                    binding_id=nonce.binding_id,
                    bot_id=nonce.bot_id,
                    chat_id=nonce.chat_id,
                    text=(
                        "Authorization intent recorded. APPROVE does not execute. "
                        "EXECUTE_PAPER_PLAN remains the only execution entry path."
                    ),
                    idempotency_key=f"auth-intent:{intent.intent_id}",
                    now=now,
                )
            applied = self._transition(
                claimed.model_copy(
                    update={
                        "authorization_intent_id": None if intent is None else intent.intent_id,
                        "binding_id": nonce.binding_id,
                        "nonce_hash": nonce.nonce_hash,
                        "effect_kind": effect,
                    }
                ),
                to=ActionReceiptState.APPLIED,
                now=now,
            )
            self._store.save_receipt(applied)
            self._audit(
                "action_applied",
                organization_id=nonce.organization_id,
                user_id=nonce.user_id,
                details=(
                    ("action", presented_payload.action.value),
                    ("receipt_id", str(applied.receipt_id)),
                    ("executes", "false"),
                ),
            )
            return ActionOutcome(
                receipt=applied,
                replayed=False,
                state_changed=True,
                authorization_intent=intent,
                effect_kind=effect,
            )

    def enqueue_outbound(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        bot_id: str,
        chat_id: str,
        text: str,
        idempotency_key: str,
        binding_id: UUID | None = None,
    ) -> OutboxRecord:
        self._require_enabled()
        now = self._clock.now()
        with self._store.transaction():
            return self._enqueue_unlocked(
                organization_id=organization_id,
                user_id=user_id,
                binding_id=binding_id,
                bot_id=bot_id,
                chat_id=chat_id,
                text=text,
                idempotency_key=idempotency_key,
                now=now,
            )

    def deliver_pending(self, *, limit: int = 10) -> list[DeliveryAttempt]:
        self._require_enabled()
        now = self._clock.now()
        attempts: list[DeliveryAttempt] = []
        with self._store.transaction():
            claimed = self._store.claim_outbox_batch(
                now=now,
                limit=limit,
                lease_owner=self._lease_owner,
                lease_for=self._outbox_lease,
            )
        for row in claimed:
            result = self._transport.send_private_message(
                bot_id=row.bot_id,
                chat_id=row.chat_id,
                text=row.text,
                idempotency_key=row.idempotency_key,
            )
            attempt_no = row.attempt + 1
            if result.ok:
                sent = row.model_copy(
                    update={
                        "state": OutboxState.SENT,
                        "attempt": attempt_no,
                        "transport_message_id": result.transport_message_id,
                        "lease_owner": None,
                        "lease_until": None,
                        "last_error": None,
                        "updated_at": now,
                    }
                )
                self._store.save_outbox(sent)
                attempts.append(
                    DeliveryAttempt(
                        outbox=sent,
                        accepted=True,
                        retryable=False,
                        transport_message_id=result.transport_message_id,
                    )
                )
                continue
            dead = attempt_no >= self._outbox_max_attempts
            failed = row.model_copy(
                update={
                    "state": OutboxState.DEAD_LETTER if dead else OutboxState.RETRYABLE,
                    "attempt": attempt_no,
                    "lease_owner": None,
                    "lease_until": None,
                    "last_error": result.error_code or "TRANSPORT_FAILURE",
                    "updated_at": now,
                }
            )
            self._store.save_outbox(failed)
            attempts.append(
                DeliveryAttempt(
                    outbox=failed,
                    accepted=False,
                    retryable=not dead,
                    error_code=result.error_code or "TRANSPORT_FAILURE",
                )
            )
        return attempts

    def acknowledge_delivery(self, *, outbox_id: UUID, transport_message_id: str) -> OutboxRecord:
        self._require_enabled()
        now = self._clock.now()
        with self._store.transaction():
            row = self._store.get_outbox(outbox_id)
            if row is None:
                raise TelegramSecurityError(
                    "Outbox record was not found.",
                    reason=TelegramSecurityReason.OUTBOX_NOT_FOUND,
                )
            if row.state is OutboxState.ACKNOWLEDGED:
                if row.transport_message_id != transport_message_id:
                    raise TelegramSecurityError(
                        "Delivery acknowledgement payload conflict.",
                        reason=TelegramSecurityReason.OUTBOX_CONFLICT,
                    )
                return row
            if row.state is not OutboxState.SENT:
                raise TelegramSecurityError(
                    "Delivery acknowledgement requires a SENT outbox record.",
                    reason=TelegramSecurityReason.ACK_STATE_INVALID,
                    details={"state": row.state.value},
                )
            if row.transport_message_id != transport_message_id:
                raise TelegramSecurityError(
                    "Delivery acknowledgement message id mismatch.",
                    reason=TelegramSecurityReason.OUTBOX_CONFLICT,
                )
            acknowledged = row.model_copy(
                update={"state": OutboxState.ACKNOWLEDGED, "updated_at": now}
            )
            self._store.save_outbox(acknowledged)
            self._audit(
                "delivery_acknowledged",
                organization_id=row.organization_id,
                user_id=row.user_id,
                details=(("outbox_id", str(row.outbox_id)),),
            )
            return acknowledged

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise TelegramInteractionDisabledError()

    def _require_inbound_type(self, inbound: TelegramInboundUpdate, *, expected: str) -> None:
        if inbound.update_type != expected:
            raise TelegramSecurityError(
                "Telegram inbound update type does not match this protocol entry.",
                reason=TelegramSecurityReason.UPDATE_TYPE_REJECTED,
                details={"update_type": inbound.update_type, "expected": expected},
            )

    def _require_identical_replay(self, receipt: ActionReceipt, incoming_digest: str) -> None:
        if secrets_equal(receipt.replay_fingerprint, incoming_digest):
            return
        self._audit(
            "replay_conflict",
            organization_id=receipt.organization_id,
            user_id=receipt.user_id,
            reason=TelegramSecurityReason.REPLAY_CONFLICT,
            details=(
                ("bot_id", receipt.bot_id),
                ("update_id", str(receipt.update_id)),
                ("receipt_id", str(receipt.receipt_id)),
            ),
        )
        raise TelegramSecurityError(
            "Inbound Telegram replay conflicts with the original fingerprint.",
            reason=TelegramSecurityReason.REPLAY_CONFLICT,
            details={
                "bot_id": receipt.bot_id,
                "update_id": str(receipt.update_id),
            },
        )

    def _enrollment_replay_fingerprint(
        self, *, identity: MessageIdentity, presented: str
    ) -> InboundReplayFingerprint:
        challenge = self._store.get_challenge_by_hash(hash_secret(presented))
        return InboundReplayFingerprint(
            update_id=identity.update_id,
            message_id=identity.message_id,
            callback_query_id=None,
            telegram_user_id=identity.telegram_user_id,
            chat_id=identity.chat_id,
            chat_type=identity.chat_type,
            bot_id=identity.bot_id,
            secret_hash=hash_secret(presented),
            action=None,
            organization_id=None if challenge is None else str(challenge.organization_id),
            user_id=None if challenge is None else str(challenge.user_id),
            account_id=None,
            resource_type=None,
            resource_id=None,
            revision_id=None,
            content_hash=None,
            payload_hash=None,
        )

    def _callback_replay_fingerprint(
        self,
        *,
        identity: CallbackIdentity,
        nonce_token: str,
        presented: ActionPayload,
    ) -> InboundReplayFingerprint:
        return InboundReplayFingerprint(
            update_id=identity.update_id,
            message_id=None,
            callback_query_id=identity.callback_query_id,
            telegram_user_id=identity.telegram_user_id,
            chat_id=identity.chat_id,
            chat_type=identity.chat_type,
            bot_id=identity.bot_id,
            secret_hash=hash_secret(nonce_token.strip()),
            action=presented.action.value,
            organization_id=str(presented.organization_id),
            user_id=str(presented.user_id),
            account_id=str(presented.account_id),
            resource_type=presented.resource_type,
            resource_id=str(presented.resource_id),
            revision_id=None if presented.revision_id is None else str(presented.revision_id),
            content_hash=presented.content_hash,
            payload_hash=payload_binding_hash(presented),
        )

    def _require_active_binding(self, binding_id: UUID) -> TelegramBinding:
        binding = self._store.get_binding(binding_id)
        if binding is None:
            raise TelegramSecurityError(
                "Telegram binding was not found.",
                reason=TelegramSecurityReason.BINDING_NOT_FOUND,
            )
        if binding.revoked_at is not None or binding.state is BindingState.REVOKED:
            raise TelegramSecurityError(
                "Telegram binding has been revoked.",
                reason=TelegramSecurityReason.BINDING_REVOKED,
            )
        return binding

    def _assert_payload_matches_binding(
        self, binding: TelegramBinding, payload: ActionPayload
    ) -> None:
        if payload.organization_id != binding.organization_id:
            raise TelegramSecurityError(
                "Action payload organization does not match the binding.",
                reason=TelegramSecurityReason.CROSS_ORGANIZATION,
            )
        if payload.user_id != binding.user_id:
            raise TelegramSecurityError(
                "Action payload user does not match the binding.",
                reason=TelegramSecurityReason.CROSS_USER,
            )

    def _authorize_callback(
        self,
        *,
        identity: CallbackIdentity,
        nonce: ActionNonce,
        presented: ActionPayload,
        now: datetime,
    ) -> TelegramSecurityReason | None:
        if now >= nonce.expires_at:
            return TelegramSecurityReason.NONCE_EXPIRED
        if nonce.state is NonceState.CONSUMED:
            return TelegramSecurityReason.NONCE_USED
        if nonce.state is not NonceState.ISSUED:
            return TelegramSecurityReason.NONCE_USED
        if identity.bot_id != nonce.bot_id:
            return TelegramSecurityReason.CROSS_BOT
        if identity.telegram_user_id != nonce.telegram_user_id:
            return TelegramSecurityReason.CROSS_USER
        if identity.chat_id != nonce.chat_id:
            return TelegramSecurityReason.CROSS_CHAT
        if presented.organization_id != nonce.organization_id:
            return TelegramSecurityReason.CROSS_ORGANIZATION
        if presented.user_id != nonce.user_id:
            return TelegramSecurityReason.CROSS_USER
        if presented.account_id != nonce.account_id:
            return TelegramSecurityReason.CROSS_ACCOUNT
        if presented.action is TelegramRemoteAction.CLOSE:
            return TelegramSecurityReason.CLOSE_UNAVAILABLE
        if presented.action != nonce.action:
            return TelegramSecurityReason.PAYLOAD_MISMATCH
        if payload_binding_hash(presented) != nonce.payload_hash:
            return TelegramSecurityReason.PAYLOAD_MISMATCH
        binding = self._store.get_binding(nonce.binding_id)
        if binding is None:
            return TelegramSecurityReason.BINDING_NOT_FOUND
        if binding.revoked_at is not None or binding.state is BindingState.REVOKED:
            return TelegramSecurityReason.BINDING_REVOKED
        if presented.action not in binding.allowed_actions:
            return TelegramSecurityReason.ACTION_NOT_ALLOWED
        return None

    def _finalize_rejection(
        self,
        receipt: ActionReceipt,
        reason: TelegramSecurityReason,
        now: datetime,
    ) -> ActionOutcome:
        rejected = self._transition(
            receipt.model_copy(update={"reason_code": reason.value}),
            to=ActionReceiptState.REJECTED,
            now=now,
            reason_code=reason.value,
        )
        self._store.save_receipt(rejected)
        self._audit(
            "action_rejected",
            organization_id=receipt.organization_id,
            user_id=receipt.user_id,
            reason=reason,
            details=(("receipt_id", str(receipt.receipt_id)),),
        )
        return ActionOutcome(
            receipt=rejected,
            replayed=False,
            state_changed=True,
            reason_code=reason.value,
        )

    def _replay_action(self, receipt: ActionReceipt) -> ActionOutcome:
        intent = None
        if receipt.authorization_intent_id is not None:
            intent = self._store.get_authorization_intent(receipt.authorization_intent_id)
        self._audit(
            "action_replayed",
            organization_id=receipt.organization_id,
            user_id=receipt.user_id,
            details=(("receipt_id", str(receipt.receipt_id)),),
        )
        return ActionOutcome(
            receipt=receipt,
            replayed=True,
            state_changed=False,
            reason_code=receipt.reason_code,
            authorization_intent=intent,
            effect_kind=receipt.effect_kind,
        )

    def _replay_enrollment(self, receipt: ActionReceipt) -> EnrollmentCompleteResult:
        if receipt.state is not ActionReceiptState.APPLIED or receipt.binding_id is None:
            reason = TelegramSecurityReason(
                receipt.reason_code or TelegramSecurityReason.ENROLLMENT_NOT_FOUND.value
            )
            raise TelegramSecurityError(
                "Enrollment delivery replayed a prior rejection.",
                reason=reason,
            )
        binding = self._store.get_binding(receipt.binding_id)
        if binding is None:
            raise TelegramSecurityError(
                "Telegram binding was not found.",
                reason=TelegramSecurityReason.BINDING_NOT_FOUND,
            )
        challenge = self._store.get_challenge_for_binding(binding.binding_id)
        if challenge is None:
            raise TelegramSecurityError(
                "Enrollment challenge was not found.",
                reason=TelegramSecurityReason.ENROLLMENT_NOT_FOUND,
            )
        return EnrollmentCompleteResult(challenge=challenge, binding=binding)

    def _record_enrollment_rejection(
        self,
        identity: MessageIdentity,
        *,
        reason: TelegramSecurityReason,
        now: datetime,
        replay_fingerprint: str,
        organization_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> None:
        receipt = self._new_receipt(
            bot_id=identity.bot_id,
            update_id=identity.update_id,
            telegram_user_id=identity.telegram_user_id,
            chat_id=identity.chat_id,
            now=now,
            message_id=identity.message_id,
            organization_id=organization_id,
            user_id=user_id,
            state=ActionReceiptState.REJECTED,
            reason_code=reason.value,
            replay_fingerprint=replay_fingerprint,
        )
        self._store.save_receipt(receipt)
        self._audit(
            "enrollment_rejected",
            organization_id=organization_id,
            user_id=user_id,
            reason=reason,
        )

    def _enqueue_unlocked(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        binding_id: UUID | None,
        bot_id: str,
        chat_id: str,
        text: str,
        idempotency_key: str,
        now: datetime,
    ) -> OutboxRecord:
        existing = self._store.get_outbox_by_idempotency(
            organization_id=organization_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            if existing.text != text or existing.chat_id != chat_id or existing.bot_id != bot_id:
                raise TelegramSecurityError(
                    "Outbox idempotency key is bound to a different payload.",
                    reason=TelegramSecurityReason.OUTBOX_CONFLICT,
                )
            return existing
        row = OutboxRecord(
            outbox_id=uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            binding_id=binding_id,
            bot_id=bot_id,
            chat_id=chat_id,
            idempotency_key=idempotency_key,
            kind=OutboxKind.PRIVATE_MESSAGE,
            text=text,
            state=OutboxState.PENDING,
            attempt=0,
            created_at=now,
            updated_at=now,
        )
        self._store.save_outbox(row)
        return row

    def _new_receipt(
        self,
        *,
        bot_id: str,
        update_id: int,
        telegram_user_id: str,
        chat_id: str,
        now: datetime,
        callback_query_id: str | None = None,
        message_id: str | None = None,
        organization_id: UUID | None = None,
        user_id: UUID | None = None,
        account_id: UUID | None = None,
        action: TelegramRemoteAction | None = None,
        payload_hash: str | None = None,
        binding_id: UUID | None = None,
        state: ActionReceiptState = ActionReceiptState.RECEIVED,
        reason_code: str | None = None,
        replay_fingerprint: str,
    ) -> ActionReceipt:
        transition = ReceiptTransition(
            sequence=1,
            from_state=None,
            to_state=state,
            at=now,
            reason_code=reason_code,
        )
        return ActionReceipt(
            receipt_id=uuid4(),
            bot_id=bot_id,
            update_id=update_id,
            callback_query_id=callback_query_id,
            message_id=message_id,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            organization_id=organization_id,
            user_id=user_id,
            account_id=account_id,
            action=action,
            payload_hash=payload_hash,
            replay_fingerprint=replay_fingerprint,
            binding_id=binding_id,
            state=state,
            reason_code=reason_code,
            transitions=(transition,),
            created_at=now,
            updated_at=now,
        )

    def _transition(
        self,
        receipt: ActionReceipt,
        *,
        to: ActionReceiptState,
        now: datetime,
        reason_code: str | None = None,
    ) -> ActionReceipt:
        transition = ReceiptTransition(
            sequence=len(receipt.transitions) + 1,
            from_state=receipt.state,
            to_state=to,
            at=now,
            reason_code=reason_code,
        )
        return receipt.model_copy(
            update={
                "state": to,
                "updated_at": now,
                "reason_code": reason_code if reason_code is not None else receipt.reason_code,
                "transitions": (*receipt.transitions, transition),
            }
        )

    def _audit(
        self,
        event_type: str,
        *,
        organization_id: UUID | None = None,
        user_id: UUID | None = None,
        reason: TelegramSecurityReason | None = None,
        details: tuple[tuple[str, str], ...] = (),
    ) -> None:
        forbidden = {"token", "nonce", "bot_token", "secret", "password", "nonce_token"}
        sanitized = tuple((key, value) for key, value in details if key.lower() not in forbidden)
        self._store.append_audit(
            ProtocolAuditEvent(
                event_id=uuid4(),
                at=self._clock.now(),
                event_type=event_type,
                organization_id=organization_id,
                user_id=user_id,
                reason_code=None if reason is None else reason.value,
                details=sanitized,
            )
        )
