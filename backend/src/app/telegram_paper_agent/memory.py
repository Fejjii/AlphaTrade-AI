"""In-memory paper Telegram store and read-only context fakes."""

from __future__ import annotations

from threading import RLock
from typing import Protocol
from uuid import UUID

from app.telegram_paper_agent.contracts import (
    JournalOutcomeView,
    LearningSummaryView,
    PaperNotificationIntent,
    PaperThread,
    PaperThreadMessage,
    PaperTradeStatusView,
    PresentedPaperConfirmation,
    StrategyDraftView,
)
from app.telegram_paper_agent.errors import ConflictingPaperNotificationError
from app.telegram_security.actions import TelegramRemoteAction


class PaperAgentStore(Protocol):
    def get_notification_by_hash(self, identity_hash: str) -> PaperNotificationIntent | None: ...

    def get_or_insert_notification(
        self, intent: PaperNotificationIntent
    ) -> PaperNotificationIntent: ...

    def get_thread(self, thread_id: UUID) -> PaperThread | None: ...

    def get_thread_for_chat(
        self,
        *,
        organization_id: UUID,
        binding_id: UUID,
        resource_type: str,
        resource_id: UUID | None,
    ) -> PaperThread | None: ...

    def get_or_insert_thread(self, thread: PaperThread) -> PaperThread: ...

    def touch_thread(self, thread: PaperThread) -> PaperThread: ...

    def append_message(self, row: PaperThreadMessage) -> PaperThreadMessage: ...

    def list_messages(self, thread_id: UUID) -> tuple[PaperThreadMessage, ...]: ...

    def save_presented_confirmation(
        self, row: PresentedPaperConfirmation
    ) -> PresentedPaperConfirmation: ...

    def latest_presented_confirmation(
        self, *, thread_id: UUID, organization_id: UUID
    ) -> PresentedPaperConfirmation | None: ...

    def latest_presented_for_binding(
        self, *, organization_id: UUID, binding_id: UUID
    ) -> PresentedPaperConfirmation | None: ...

    def presented_for_binding_action(
        self,
        *,
        organization_id: UUID,
        binding_id: UUID,
        action: TelegramRemoteAction,
    ) -> tuple[PresentedPaperConfirmation, ...]: ...

    def consume_confirmation(
        self, row: PresentedPaperConfirmation
    ) -> PresentedPaperConfirmation: ...


class InMemoryPaperAgentStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._notifications: dict[UUID, PaperNotificationIntent] = {}
        self._notify_by_hash: dict[str, UUID] = {}
        self._threads: dict[UUID, PaperThread] = {}
        self._thread_keys: dict[tuple[UUID, UUID, str, UUID | None], UUID] = {}
        self._messages: dict[UUID, list[PaperThreadMessage]] = {}
        self._confirmations: dict[UUID, PresentedPaperConfirmation] = {}

    def get_notification_by_hash(self, identity_hash: str) -> PaperNotificationIntent | None:
        with self._lock:
            intent_id = self._notify_by_hash.get(identity_hash)
            if intent_id is None:
                return None
            return self._notifications[intent_id]

    def get_or_insert_notification(
        self, intent: PaperNotificationIntent
    ) -> PaperNotificationIntent:
        with self._lock:
            existing_id = self._notify_by_hash.get(intent.identity_hash)
            if existing_id is not None:
                existing = self._notifications[existing_id]
                if existing.content_hash != intent.content_hash:
                    raise ConflictingPaperNotificationError(
                        "Paper notification identity is bound to different content."
                    )
                if existing.intent_id != intent.intent_id:
                    raise ConflictingPaperNotificationError(
                        "Paper notification hash is bound to a different intent id."
                    )
                return existing
            occupied = self._notifications.get(intent.intent_id)
            if occupied is not None:
                raise ConflictingPaperNotificationError(
                    "Paper notification intent id is already bound."
                )
            self._notifications[intent.intent_id] = intent
            self._notify_by_hash[intent.identity_hash] = intent.intent_id
            return intent

    def get_thread(self, thread_id: UUID) -> PaperThread | None:
        with self._lock:
            return self._threads.get(thread_id)

    def get_thread_for_chat(
        self,
        *,
        organization_id: UUID,
        binding_id: UUID,
        resource_type: str,
        resource_id: UUID | None,
    ) -> PaperThread | None:
        key = (organization_id, binding_id, resource_type, resource_id)
        with self._lock:
            thread_id = self._thread_keys.get(key)
            if thread_id is None:
                return None
            return self._threads[thread_id]

    def get_or_insert_thread(self, thread: PaperThread) -> PaperThread:
        key = (
            thread.organization_id,
            thread.binding_id,
            thread.resource_type,
            thread.resource_id,
        )
        with self._lock:
            existing_id = self._thread_keys.get(key)
            if existing_id is not None:
                return self._threads[existing_id]
            self._threads[thread.thread_id] = thread
            self._thread_keys[key] = thread.thread_id
            self._messages.setdefault(thread.thread_id, [])
            return thread

    def touch_thread(self, thread: PaperThread) -> PaperThread:
        with self._lock:
            self._threads[thread.thread_id] = thread
            return thread

    def append_message(self, row: PaperThreadMessage) -> PaperThreadMessage:
        with self._lock:
            self._messages.setdefault(row.thread_id, []).append(row)
            return row

    def list_messages(self, thread_id: UUID) -> tuple[PaperThreadMessage, ...]:
        with self._lock:
            return tuple(self._messages.get(thread_id, ()))

    def save_presented_confirmation(
        self, row: PresentedPaperConfirmation
    ) -> PresentedPaperConfirmation:
        with self._lock:
            existing = self._confirmations.get(row.confirmation_id)
            if existing is not None:
                return existing
            self._confirmations[row.confirmation_id] = row
            return row

    def latest_presented_confirmation(
        self, *, thread_id: UUID, organization_id: UUID
    ) -> PresentedPaperConfirmation | None:
        with self._lock:
            rows = [
                row
                for row in self._confirmations.values()
                if row.thread_id == thread_id
                and row.organization_id == organization_id
                and row.consumed_at is None
            ]
            if not rows:
                return None
            return max(rows, key=lambda row: row.presented_at)

    def latest_presented_for_binding(
        self, *, organization_id: UUID, binding_id: UUID
    ) -> PresentedPaperConfirmation | None:
        with self._lock:
            rows = [
                row
                for row in self._confirmations.values()
                if row.organization_id == organization_id
                and row.consumed_at is None
                and self._threads.get(row.thread_id) is not None
                and self._threads[row.thread_id].binding_id == binding_id
            ]
            if not rows:
                return None
            return max(rows, key=lambda row: row.presented_at)

    def presented_for_binding_action(
        self,
        *,
        organization_id: UUID,
        binding_id: UUID,
        action: TelegramRemoteAction,
    ) -> tuple[PresentedPaperConfirmation, ...]:
        with self._lock:
            rows = [
                row
                for row in self._confirmations.values()
                if row.organization_id == organization_id
                and row.consumed_at is None
                and row.action is action
                and self._threads.get(row.thread_id) is not None
                and self._threads[row.thread_id].binding_id == binding_id
            ]
            return tuple(rows)

    def consume_confirmation(self, row: PresentedPaperConfirmation) -> PresentedPaperConfirmation:
        with self._lock:
            self._confirmations[row.confirmation_id] = row
            return row


class InMemoryPaperContext:
    """Read-only fake paper/journal/learning facts for tests."""

    def __init__(
        self,
        *,
        status: PaperTradeStatusView | None = None,
        journal: JournalOutcomeView | None = None,
        learning: LearningSummaryView | None = None,
        strategy: StrategyDraftView | None = None,
    ) -> None:
        self.status = status or PaperTradeStatusView(
            open_positions=0,
            open_orders=0,
            summary="No open paper positions.",
        )
        self.journal = journal
        self.learning = learning
        self.strategy = strategy

    def paper_trade_status(self, *, organization_id: UUID, user_id: UUID) -> PaperTradeStatusView:
        del organization_id, user_id
        return self.status

    def journal_outcome(
        self, *, organization_id: UUID, user_id: UUID, trade_id: UUID | None
    ) -> JournalOutcomeView | None:
        del organization_id, user_id, trade_id
        return self.journal

    def learning_summary(
        self, *, organization_id: UUID, user_id: UUID, candidate_id: UUID | None
    ) -> LearningSummaryView | None:
        del organization_id, user_id, candidate_id
        return self.learning

    def strategy_discussion(
        self, *, organization_id: UUID, user_id: UUID, strategy_id: UUID | None
    ) -> StrategyDraftView | None:
        del organization_id, user_id, strategy_id
        return self.strategy
