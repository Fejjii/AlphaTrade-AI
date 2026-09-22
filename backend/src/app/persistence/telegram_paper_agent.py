"""PostgreSQL adapter for paper Telegram notification/thread identity."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.telegram_paper_agent import (
    TelegramPaperConfirmationRow,
    TelegramPaperMessageRow,
    TelegramPaperNotificationRow,
    TelegramPaperThreadRow,
)
from app.persistence.unique import is_unique_violation
from app.telegram_paper_agent.contracts import (
    DiscussionIntent,
    PaperNotificationIntent,
    PaperNotificationKind,
    PaperThread,
    PaperThreadMessage,
    PresentedPaperConfirmation,
)
from app.telegram_paper_agent.errors import ConflictingPaperNotificationError
from app.telegram_security.actions import TelegramRemoteAction

_T = TypeVar("_T")
_NOTIFY_UNIQUES = ("uq_tg_paper_notify_identity", "uq_tg_paper_notify_org_intent")
_THREAD_UNIQUES = (
    "uq_tg_paper_thread_scope_resource",
    "uq_tg_paper_thread_scope_null_resource",
)


class PostgresPaperAgentStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._local = threading.local()

    def _current(self) -> Session | None:
        session = getattr(self._local, "session", None)
        return session if isinstance(session, Session) else None

    def _run(self, work: Callable[[Session], _T]) -> _T:
        current = self._current()
        if current is not None:
            return work(current)
        session = self._session_factory()
        self._local.session = session
        try:
            with session.begin():
                return work(session)
        finally:
            session.close()
            self._local.session = None

    def get_notification_by_hash(self, identity_hash: str) -> PaperNotificationIntent | None:
        def work(session: Session) -> PaperNotificationIntent | None:
            row = session.scalars(
                select(TelegramPaperNotificationRow).where(
                    TelegramPaperNotificationRow.identity_hash == identity_hash
                )
            ).first()
            return None if row is None else _notification_from_row(row)

        return self._run(work)

    def get_or_insert_notification(
        self, intent: PaperNotificationIntent
    ) -> PaperNotificationIntent:
        def work(session: Session) -> PaperNotificationIntent:
            existing = session.get(TelegramPaperNotificationRow, intent.intent_id)
            if existing is not None:
                loaded = _notification_from_row(existing)
                if loaded.identity_hash != intent.identity_hash:
                    raise ConflictingPaperNotificationError(
                        "Paper notification intent id is already bound."
                    )
                if loaded.content_hash != intent.content_hash:
                    raise ConflictingPaperNotificationError(
                        "Paper notification identity is bound to different content."
                    )
                return loaded
            hashed = session.scalars(
                select(TelegramPaperNotificationRow).where(
                    TelegramPaperNotificationRow.identity_hash == intent.identity_hash
                )
            ).first()
            if hashed is not None:
                loaded = _notification_from_row(hashed)
                if loaded.content_hash != intent.content_hash:
                    raise ConflictingPaperNotificationError(
                        "Paper notification identity is bound to different content."
                    )
                return loaded
            try:
                with session.begin_nested():
                    session.add(_notification_to_row(intent))
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_NOTIFY_UNIQUES):
                    raise
                hashed = session.scalars(
                    select(TelegramPaperNotificationRow).where(
                        TelegramPaperNotificationRow.identity_hash == intent.identity_hash
                    )
                ).first()
                if hashed is None:
                    raise
                return _notification_from_row(hashed)
            return intent

        return self._run(work)

    def get_thread(self, thread_id: UUID) -> PaperThread | None:
        def work(session: Session) -> PaperThread | None:
            row = session.get(TelegramPaperThreadRow, thread_id)
            return None if row is None else _thread_from_row(row)

        return self._run(work)

    def get_thread_for_chat(
        self,
        *,
        organization_id: UUID,
        binding_id: UUID,
        resource_type: str,
        resource_id: UUID | None,
    ) -> PaperThread | None:
        def work(session: Session) -> PaperThread | None:
            stmt = select(TelegramPaperThreadRow).where(
                TelegramPaperThreadRow.organization_id == organization_id,
                TelegramPaperThreadRow.binding_id == binding_id,
                TelegramPaperThreadRow.resource_type == resource_type,
            )
            if resource_id is None:
                stmt = stmt.where(TelegramPaperThreadRow.resource_id.is_(None))
            else:
                stmt = stmt.where(TelegramPaperThreadRow.resource_id == resource_id)
            row = session.scalars(stmt).first()
            return None if row is None else _thread_from_row(row)

        return self._run(work)

    def get_or_insert_thread(self, thread: PaperThread) -> PaperThread:
        def work(session: Session) -> PaperThread:
            existing = session.get(TelegramPaperThreadRow, thread.thread_id)
            if existing is not None:
                return _thread_from_row(existing)
            found = self.get_thread_for_chat(
                organization_id=thread.organization_id,
                binding_id=thread.binding_id,
                resource_type=thread.resource_type,
                resource_id=thread.resource_id,
            )
            if found is not None:
                return found
            try:
                with session.begin_nested():
                    session.add(_thread_to_row(thread))
                    session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_THREAD_UNIQUES):
                    raise
                loaded = session.get(TelegramPaperThreadRow, thread.thread_id)
                if loaded is not None:
                    return _thread_from_row(loaded)
                recovered = self.get_thread_for_chat(
                    organization_id=thread.organization_id,
                    binding_id=thread.binding_id,
                    resource_type=thread.resource_type,
                    resource_id=thread.resource_id,
                )
                if recovered is None:
                    raise
                return recovered
            return thread

        return self._run(work)

    def touch_thread(self, thread: PaperThread) -> PaperThread:
        def work(session: Session) -> PaperThread:
            current = session.get(TelegramPaperThreadRow, thread.thread_id)
            if current is None:
                session.add(_thread_to_row(thread))
                session.flush()
                return thread
            current.updated_at = thread.updated_at
            current.notification_id = thread.notification_id
            session.flush()
            return _thread_from_row(current)

        return self._run(work)

    def append_message(self, row: PaperThreadMessage) -> PaperThreadMessage:
        def work(session: Session) -> PaperThreadMessage:
            session.add(_message_to_row(row))
            session.flush()
            return row

        return self._run(work)

    def list_messages(self, thread_id: UUID) -> tuple[PaperThreadMessage, ...]:
        def work(session: Session) -> tuple[PaperThreadMessage, ...]:
            rows = session.scalars(
                select(TelegramPaperMessageRow)
                .where(TelegramPaperMessageRow.thread_id == thread_id)
                .order_by(TelegramPaperMessageRow.created_at)
            ).all()
            return tuple(_message_from_row(row) for row in rows)

        return self._run(work)

    def save_presented_confirmation(
        self, row: PresentedPaperConfirmation
    ) -> PresentedPaperConfirmation:
        def work(session: Session) -> PresentedPaperConfirmation:
            existing = session.get(TelegramPaperConfirmationRow, row.confirmation_id)
            if existing is not None:
                return _confirmation_from_row(existing)
            session.add(_confirmation_to_row(row))
            session.flush()
            return row

        return self._run(work)

    def latest_presented_confirmation(
        self, *, thread_id: UUID, organization_id: UUID
    ) -> PresentedPaperConfirmation | None:
        def work(session: Session) -> PresentedPaperConfirmation | None:
            row = session.scalars(
                select(TelegramPaperConfirmationRow)
                .where(
                    TelegramPaperConfirmationRow.thread_id == thread_id,
                    TelegramPaperConfirmationRow.organization_id == organization_id,
                    TelegramPaperConfirmationRow.consumed_at.is_(None),
                )
                .order_by(TelegramPaperConfirmationRow.presented_at.desc())
            ).first()
            return None if row is None else _confirmation_from_row(row)

        return self._run(work)

    def latest_presented_for_binding(
        self, *, organization_id: UUID, binding_id: UUID
    ) -> PresentedPaperConfirmation | None:
        def work(session: Session) -> PresentedPaperConfirmation | None:
            row = session.scalars(
                select(TelegramPaperConfirmationRow)
                .join(
                    TelegramPaperThreadRow,
                    TelegramPaperThreadRow.thread_id == TelegramPaperConfirmationRow.thread_id,
                )
                .where(
                    TelegramPaperConfirmationRow.organization_id == organization_id,
                    TelegramPaperConfirmationRow.consumed_at.is_(None),
                    TelegramPaperThreadRow.binding_id == binding_id,
                )
                .order_by(TelegramPaperConfirmationRow.presented_at.desc())
            ).first()
            return None if row is None else _confirmation_from_row(row)

        return self._run(work)

    def presented_for_binding_action(
        self,
        *,
        organization_id: UUID,
        binding_id: UUID,
        action: TelegramRemoteAction,
    ) -> tuple[PresentedPaperConfirmation, ...]:
        def work(session: Session) -> tuple[PresentedPaperConfirmation, ...]:
            rows = session.scalars(
                select(TelegramPaperConfirmationRow)
                .join(
                    TelegramPaperThreadRow,
                    TelegramPaperThreadRow.thread_id == TelegramPaperConfirmationRow.thread_id,
                )
                .where(
                    TelegramPaperConfirmationRow.organization_id == organization_id,
                    TelegramPaperConfirmationRow.consumed_at.is_(None),
                    TelegramPaperConfirmationRow.action == action.value,
                    TelegramPaperThreadRow.binding_id == binding_id,
                )
            ).all()
            return tuple(_confirmation_from_row(row) for row in rows)

        return self._run(work)

    def consume_confirmation(self, row: PresentedPaperConfirmation) -> PresentedPaperConfirmation:
        def work(session: Session) -> PresentedPaperConfirmation:
            current = session.get(TelegramPaperConfirmationRow, row.confirmation_id)
            if current is None:
                session.add(_confirmation_to_row(row))
                session.flush()
                return row
            current.consumed_at = row.consumed_at
            session.flush()
            return _confirmation_from_row(current)

        return self._run(work)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _aware_opt(value: datetime | None) -> datetime | None:
    return None if value is None else _aware(value)


def _notification_to_row(row: PaperNotificationIntent) -> TelegramPaperNotificationRow:
    return TelegramPaperNotificationRow(
        intent_id=row.intent_id,
        identity_hash=row.identity_hash,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        kind=row.kind.value,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        content_hash=row.content_hash,
        telegram_revision_id=row.telegram_revision_id,
        candidate_id=row.candidate_id,
        watcher_lineage_id=row.watcher_lineage_id,
        watcher_reason_code=row.watcher_reason_code,
        text=row.text,
        created_at=row.created_at,
    )


def _notification_from_row(row: TelegramPaperNotificationRow) -> PaperNotificationIntent:
    return PaperNotificationIntent(
        intent_id=row.intent_id,
        identity_hash=row.identity_hash,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        kind=PaperNotificationKind(row.kind),
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        content_hash=row.content_hash,
        telegram_revision_id=row.telegram_revision_id,
        candidate_id=row.candidate_id,
        watcher_lineage_id=row.watcher_lineage_id,
        watcher_reason_code=row.watcher_reason_code,
        text=row.text,
        created_at=_aware(row.created_at),
    )


def _thread_to_row(row: PaperThread) -> TelegramPaperThreadRow:
    return TelegramPaperThreadRow(
        thread_id=row.thread_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        binding_id=row.binding_id,
        bot_id=row.bot_id,
        chat_id=row.chat_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        notification_id=row.notification_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _thread_from_row(row: TelegramPaperThreadRow) -> PaperThread:
    return PaperThread(
        thread_id=row.thread_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        binding_id=row.binding_id,
        bot_id=row.bot_id,
        chat_id=row.chat_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        notification_id=row.notification_id,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _message_to_row(row: PaperThreadMessage) -> TelegramPaperMessageRow:
    return TelegramPaperMessageRow(
        message_id=row.message_id,
        thread_id=row.thread_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        role=row.role,
        intent=row.intent.value,
        content=row.content,
        receipt_id=row.receipt_id,
        created_at=row.created_at,
    )


def _message_from_row(row: TelegramPaperMessageRow) -> PaperThreadMessage:
    return PaperThreadMessage(
        message_id=row.message_id,
        thread_id=row.thread_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        role="user" if row.role == "user" else "assistant",
        intent=DiscussionIntent(row.intent),
        content=row.content,
        receipt_id=row.receipt_id,
        created_at=_aware(row.created_at),
    )


def _confirmation_to_row(row: PresentedPaperConfirmation) -> TelegramPaperConfirmationRow:
    return TelegramPaperConfirmationRow(
        confirmation_id=row.confirmation_id,
        thread_id=row.thread_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        action=row.action.value,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        content_hash=row.content_hash,
        revision_id=row.revision_id,
        payload_hash=row.payload_hash,
        presented_at=row.presented_at,
        consumed_at=row.consumed_at,
    )


def _confirmation_from_row(row: TelegramPaperConfirmationRow) -> PresentedPaperConfirmation:
    return PresentedPaperConfirmation(
        confirmation_id=row.confirmation_id,
        thread_id=row.thread_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        action=TelegramRemoteAction(row.action),
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        content_hash=row.content_hash,
        revision_id=row.revision_id,
        payload_hash=row.payload_hash,
        presented_at=_aware(row.presented_at),
        consumed_at=_aware_opt(row.consumed_at),
    )
