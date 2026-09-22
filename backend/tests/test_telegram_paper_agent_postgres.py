"""PostgreSQL paper Telegram identity: restart convergence and tenant isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.persistence.telegram_paper_agent import PostgresPaperAgentStore
from app.telegram_paper_agent.contracts import (
    PaperNotificationIntent,
    PaperNotificationKind,
    PaperThread,
)
from app.telegram_paper_agent.errors import ConflictingPaperNotificationError
from app.telegram_paper_agent.identity import (
    build_paper_notification_identity,
    paper_telegram_revision_id,
    paper_thread_id,
)
from app.telegram_security.clock import FrozenClock
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import ACCOUNT_ID, ORG_ID, USER_ID
from tests.support.postgres_persistence import persistence_session_factory, requires_postgres
from tests.support.telegram_security import OTHER_ORG

RESOURCE = uuid4()


@requires_postgres
def test_postgres_notification_identity_converges_after_restart() -> None:
    factory = persistence_session_factory()
    store = PostgresPaperAgentStore(factory)
    clock = FrozenClock(EVALUATED_AT)
    intent_id, digest = build_paper_notification_identity(
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        kind=PaperNotificationKind.WATCHER_SCAN_BLOCKED,
        resource_type="watcher_scan",
        resource_id=RESOURCE,
        content_hash="a" * 64,
    )
    intent = PaperNotificationIntent(
        intent_id=intent_id,
        identity_hash=digest,
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        kind=PaperNotificationKind.WATCHER_SCAN_BLOCKED,
        resource_type="watcher_scan",
        resource_id=RESOURCE,
        content_hash="a" * 64,
        telegram_revision_id=paper_telegram_revision_id(
            resource_id=RESOURCE, content_hash="a" * 64
        ),
        text="Watcher paper alert (not a trade).",
        created_at=clock.now(),
    )
    first = store.get_or_insert_notification(intent)
    restarted = PostgresPaperAgentStore(factory)
    second = restarted.get_or_insert_notification(intent)
    assert second.intent_id == first.intent_id
    assert restarted.get_notification_by_hash(digest) is not None


@requires_postgres
def test_postgres_thread_is_tenant_scoped() -> None:
    factory = persistence_session_factory()
    store = PostgresPaperAgentStore(factory)
    clock = FrozenClock(EVALUATED_AT)
    binding_id = uuid4()
    thread = PaperThread(
        thread_id=paper_thread_id(
            organization_id=ORG_ID,
            binding_id=binding_id,
            resource_type="candidate",
            resource_id=RESOURCE,
        ),
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        binding_id=binding_id,
        bot_id="bot-100",
        chat_id="tg-chat-1",
        resource_type="candidate",
        resource_id=RESOURCE,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    stored = store.get_or_insert_thread(thread)
    found = store.get_thread_for_chat(
        organization_id=ORG_ID,
        binding_id=binding_id,
        resource_type="candidate",
        resource_id=RESOURCE,
    )
    assert found is not None
    assert found.thread_id == stored.thread_id
    missing = store.get_thread_for_chat(
        organization_id=OTHER_ORG,
        binding_id=binding_id,
        resource_type="candidate",
        resource_id=RESOURCE,
    )
    assert missing is None


@requires_postgres
def test_postgres_chat_thread_null_resource_converges() -> None:
    factory = persistence_session_factory()
    store = PostgresPaperAgentStore(factory)
    clock = FrozenClock(EVALUATED_AT)
    binding_id = uuid4()
    thread = PaperThread(
        thread_id=paper_thread_id(
            organization_id=ORG_ID,
            binding_id=binding_id,
            resource_type="telegram_chat",
            resource_id=None,
        ),
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        binding_id=binding_id,
        bot_id="bot-100",
        chat_id="tg-chat-1",
        resource_type="telegram_chat",
        resource_id=None,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    first = store.get_or_insert_thread(thread)
    restarted = PostgresPaperAgentStore(factory)
    second = restarted.get_or_insert_thread(thread)
    assert second.thread_id == first.thread_id
    found = restarted.get_thread_for_chat(
        organization_id=ORG_ID,
        binding_id=binding_id,
        resource_type="telegram_chat",
        resource_id=None,
    )
    assert found is not None
    assert found.thread_id == first.thread_id


@requires_postgres
def test_postgres_conflicting_notification_content_fails_closed() -> None:
    factory = persistence_session_factory()
    store = PostgresPaperAgentStore(factory)
    clock = FrozenClock(EVALUATED_AT)
    intent_id, digest = build_paper_notification_identity(
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        kind=PaperNotificationKind.JOURNAL_OUTCOME,
        resource_type="journal_trade",
        resource_id=RESOURCE,
        content_hash="b" * 64,
    )
    base = PaperNotificationIntent(
        intent_id=intent_id,
        identity_hash=digest,
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        kind=PaperNotificationKind.JOURNAL_OUTCOME,
        resource_type="journal_trade",
        resource_id=RESOURCE,
        content_hash="b" * 64,
        telegram_revision_id=paper_telegram_revision_id(
            resource_id=RESOURCE, content_hash="b" * 64
        ),
        text="Paper journal outcome (facts only, not a live fill).",
        created_at=clock.now(),
    )
    store.get_or_insert_notification(base)
    with pytest.raises(ConflictingPaperNotificationError):
        store.get_or_insert_notification(base.model_copy(update={"content_hash": "c" * 64}))
