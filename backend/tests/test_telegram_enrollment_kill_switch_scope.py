"""Tenant scope for Telegram enrollment versus paper-action kill switches.

Enrollment does not mint Candidates, start Watcher paper workflows, or deliver
automated Telegram actions. An unrelated organization's kill switch must not
pause it. The bound tenant switch still blocks that tenant's paper actions and
Telegram delivery. Real trading stays impossible.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.candidate_alerts.gateway import CandidateAlertGateway
from app.core.config import Settings
from app.core.paper_safety import assert_paper_execution_allowed
from app.db.models import KillSwitchState, Organization
from app.persistence.composition import build_postgres_telegram_security_protocol
from app.persistence.runtime_status import TELEGRAM_COMPONENT, load_runtime_rows
from app.persistence.telegram_activation import PostgresActivationCursorStore
from app.runtime_safety.paper_actions import (
    automated_paper_actions_blocked,
    read_enrollment_runtime_kill_switch,
    read_kill_switch_active,
    read_process_kill_switch,
)
from app.signal_fusion.lifecycle import in_memory_candidate_lifecycle
from app.telegram_activation.controller import TelegramPaperActivation
from app.telegram_activation.cursor import enrollment_cursor_owner
from app.telegram_activation.intake import ParsedTelegramUpdate, RecordedUpdateSource
from app.telegram_activation.policy import PAPER_ACTIVATION_BACKOFF
from app.telegram_activation.runtime import TelegramPaperRuntime, build_telegram_runtime
from app.telegram_paper_agent.contracts import PaperAlertRecipient
from app.telegram_paper_agent.gateway import TelegramPaperAgent
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import ChatType, OutboxState
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import FakeTelegramTransport
from app.watcher.memory import FakeClock, InMemoryWatcherStore, SideEffectProbe
from app.workers.watcher_paper import WatcherPaperRuntime
from app.workers.watcher_paper_targets import PaperScanTarget
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres
from tests.support.telegram_security import (
    ACCOUNT,
    BOT,
    CHAT,
    ORG,
    OTHER_ORG,
    USER,
    TokenSeq,
    enroll,
    message_identity,
)

TOKEN = "123456789:AAHtestTokenValueForStagingPackage"
TENANT_A = OTHER_ORG
TENANT_B = ORG

_STAGING = {
    "environment": "staging",
    "jwt_secret": "x" * 32,
    "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
    "redis_url": "redis://redis.example.com:6379/0",
    "qdrant_url": "https://qdrant.example.com",
    "openai_api_key": "sk-test-not-a-real-key",
    "cors_origins": "https://app.example.com",
    "auth_refresh_cookie_enabled": True,
    "auth_cookie_secure": True,
    "auth_cookie_samesite": "none",
    "enable_real_trading": False,
    "execution_mode": "paper",
    "exchange_mode": "paper_internal",
    "provider_mode": "fallback",
    "rate_limit_use_redis": True,
    "rate_limit_allow_in_memory_fallback": False,
    "trusted_proxy_hops": 1,
    "debug": False,
}


class _UnreadableSettings:
    @property
    def global_kill_switch_active(self) -> bool:
        raise RuntimeError("kill switch settings unreadable")


class _BrokenSession:
    def scalar(self, _statement: object) -> object:
        raise RuntimeError("kill switch unreadable")


def _enrollment_settings(*, global_kill_switch_active: bool = False) -> Settings:
    return Settings(
        **{
            **_STAGING,
            "perpetual_evidence_source": "binance_usdm",
            "telegram_interaction_enabled": True,
            "telegram_inbound_mode": "polling",
            "telegram_network_permitted": True,
            "telegram_bot_id": BOT,
            "telegram_bot_token": TOKEN,
            "global_kill_switch_active": global_kill_switch_active,
        }
    )


def _projection_settings() -> Settings:
    return Settings(
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        exchange_mode="paper_internal",
        telegram_interaction_enabled=True,
        telegram_paper_activation_armed=True,
        telegram_inbound_mode="polling",
        telegram_alerts_enabled=False,
        automatic_telegram_delivery_enabled=False,
        telegram_network_permitted=False,
    )


def _seed_switches(
    factory: sessionmaker[Session],
    *,
    tenant_a_active: bool,
    tenant_b_active: bool,
) -> None:
    with factory() as session, session.begin():
        session.add(Organization(id=TENANT_A, name="Tenant A kill switch"))
        session.add(Organization(id=TENANT_B, name="Tenant B kill switch"))
        session.flush()
        session.add(
            KillSwitchState(
                organization_id=TENANT_A,
                active=tenant_a_active,
                reason="tenant-a",
            )
        )
        session.add(
            KillSwitchState(
                organization_id=TENANT_B,
                active=tenant_b_active,
                reason="tenant-b",
            )
        )


def _private_message(*, update_id: int, text: str) -> ParsedTelegramUpdate:
    return ParsedTelegramUpdate(
        update_id=update_id,
        body_size=len(text.encode()),
        kind="message",
        chat_type=ChatType.PRIVATE,
        chat_id=CHAT,
        telegram_user_id="tg-user-1",
        message_id=f"msg-{update_id}",
        text=text,
    )


def _scan_target(organization_id: UUID) -> PaperScanTarget:
    return PaperScanTarget(
        organization_id=organization_id,
        user_id=USER,
        strategy_id=uuid4(),
        strategy_version_id=uuid4(),
        compiled_setup_definition_id=uuid4(),
        compiled_content_hash="ab" * 32,
        fusion_policy_version="v1",
        symbol="BTCUSDT",
    )


def _bound_runtime(
    factory: sessionmaker[Session],
    *,
    organization_id: UUID,
    worker_id: str,
) -> tuple[TelegramPaperRuntime, FakeTelegramTransport, TelegramSecurityProtocol, UUID]:
    clock = FrozenClock()
    transport = FakeTelegramTransport()
    settings = _projection_settings()
    protocol = build_postgres_telegram_security_protocol(
        factory,
        enabled=True,
        clock=clock,
        transport=transport,
        token_factory=TokenSeq(),
        retry_backoff=PAPER_ACTIVATION_BACKOFF,
    )
    _token, binding_id = enroll(
        protocol,
        organization_id=organization_id,
        user_id=USER,
        identity=message_identity(update_id=1, message_id="enroll-1"),
    )
    agent = TelegramPaperAgent(
        protocol=protocol,
        candidates=CandidateAlertGateway(
            lifecycle=in_memory_candidate_lifecycle(now=clock.now()),
            protocol=protocol,
            clock=clock,
        ),
        clock=clock,
        enabled=True,
    )
    controller = TelegramPaperActivation(
        settings=settings,
        agent=agent,
        recipient=PaperAlertRecipient(
            organization_id=organization_id,
            user_id=USER,
            account_id=ACCOUNT,
            binding_id=binding_id,
            bot_id=BOT,
            chat_id=CHAT,
        ),
        clock=clock,
        outbound_ready=True,
        update_source=RecordedUpdateSource(()),
        cursor_store=PostgresActivationCursorStore(factory),
    )
    controller.arm()
    runtime = TelegramPaperRuntime(
        settings=settings,
        session_factory=factory,
        clock=clock,
        worker_id=worker_id,
        posture="projection",
        controller=controller,
    )
    return runtime, transport, protocol, binding_id


def test_enrollment_kill_switch_ignores_tenant_rows_and_fails_closed() -> None:
    assert read_enrollment_runtime_kill_switch(Settings()) is False
    assert read_enrollment_runtime_kill_switch(Settings(global_kill_switch_active=True)) is True
    assert read_enrollment_runtime_kill_switch(None) is True
    assert read_enrollment_runtime_kill_switch(cast(Settings, _UnreadableSettings())) is True
    assert automated_paper_actions_blocked(True) is True
    assert automated_paper_actions_blocked(False) is False

    broken = cast(Session, _BrokenSession())
    assert read_kill_switch_active(broken, Settings(), TENANT_A) is True
    assert read_process_kill_switch(broken, Settings()) is True
    assert automated_paper_actions_blocked(read_kill_switch_active(broken, Settings(), TENANT_A))


def test_real_trading_remains_impossible() -> None:
    with pytest.raises(ValidationError):
        Settings(enable_real_trading=True)
    with pytest.raises(ValidationError):
        Settings(execution_mode="trade")
    with pytest.raises(ValidationError):
        Settings(exchange_mode="trade_live")

    paper = _enrollment_settings()
    assert paper.enable_real_trading is False
    assert paper.real_trading_enabled is False
    assert paper.execution_mode.value == "paper"
    assert paper.exchange_mode.value == "paper_internal"
    assert_paper_execution_allowed(paper)


@requires_postgres
def test_tenant_a_kill_switch_does_not_block_tenant_b_enrollment() -> None:
    factory = phase7_plan_session_factory()
    _seed_switches(factory, tenant_a_active=True, tenant_b_active=False)
    settings = _enrollment_settings()
    clock = FrozenClock()
    starter = build_postgres_telegram_security_protocol(
        factory,
        enabled=True,
        clock=clock,
        transport=FakeTelegramTransport(),
        token_factory=TokenSeq(),
    )
    started = starter.start_enrollment(organization_id=TENANT_B, user_id=USER, bot_id=BOT)
    source = RecordedUpdateSource((_private_message(update_id=11, text=started.token),))
    transport = FakeTelegramTransport()
    runtime = build_telegram_runtime(
        settings,
        factory,
        transport=transport,
        update_source=source,
        clock=clock,
        worker_id="enroll-tenant-b",
    )

    assert runtime.posture == "enrollment"
    cycle = runtime.run_cycle()

    assert cycle.kill_switch_active is False
    assert cycle.poll_applied == 1
    assert cycle.delivered == 0
    assert cycle.last_error_code != "kill_switch_active"
    assert started.token not in cycle.last_error_code
    assert transport.send_count == 0
    binding = starter.store.get_active_binding_for_chat(bot_id=BOT, chat_id=CHAT)
    assert binding is not None
    assert binding.organization_id == TENANT_B
    with factory() as session:
        assert read_process_kill_switch(session, settings) is True
        assert read_kill_switch_active(session, settings, TENANT_A) is True
        assert read_kill_switch_active(session, settings, TENANT_B) is False
        row = load_runtime_rows(session)[TELEGRAM_COMPONENT]
    assert row.telegram_runtime_state == "enrollment"
    assert row.kill_switch_active is False
    assert row.last_error_code != "kill_switch_active"
    cursor = PostgresActivationCursorStore(factory).get_cursor(bot_id=BOT)
    assert cursor is not None
    assert cursor.organization_id == TENANT_B
    assert enrollment_cursor_owner(BOT) != TENANT_B


@requires_postgres
def test_global_kill_switch_still_pauses_enrollment() -> None:
    factory = phase7_plan_session_factory()
    _seed_switches(factory, tenant_a_active=False, tenant_b_active=False)
    settings = _enrollment_settings(global_kill_switch_active=True)
    clock = FrozenClock()
    starter = build_postgres_telegram_security_protocol(
        factory,
        enabled=True,
        clock=clock,
        transport=FakeTelegramTransport(),
        token_factory=TokenSeq(),
    )
    started = starter.start_enrollment(organization_id=TENANT_B, user_id=USER, bot_id=BOT)
    source = RecordedUpdateSource((_private_message(update_id=12, text=started.token),))
    runtime = build_telegram_runtime(
        settings,
        factory,
        transport=FakeTelegramTransport(),
        update_source=source,
        clock=clock,
        worker_id="enroll-global-halt",
    )

    cycle = runtime.run_cycle()

    assert cycle.kill_switch_active is True
    assert cycle.lease_held is True
    assert cycle.poll_applied == 0
    assert cycle.delivered == 0
    assert cycle.last_error_code == "kill_switch_active"
    assert starter.store.get_active_binding_for_chat(bot_id=BOT, chat_id=CHAT) is None
    with factory() as session:
        row = load_runtime_rows(session)[TELEGRAM_COMPONENT]
    assert row.telegram_runtime_state == "paused"
    assert row.kill_switch_active is True


@requires_postgres
def test_active_kill_switch_still_blocks_tenant_a_paper_actions() -> None:
    factory = phase7_plan_session_factory()
    _seed_switches(factory, tenant_a_active=True, tenant_b_active=False)
    settings = Settings()
    probe = SideEffectProbe()
    clock = FakeClock()
    runtime = WatcherPaperRuntime(
        store=InMemoryWatcherStore(),
        lifecycle=in_memory_candidate_lifecycle(now=clock.now()),
        clock=clock,
        enabled=True,
        session_factory=factory,
        settings=settings,
        side_effects=probe,
    )

    with factory() as session:
        assert read_kill_switch_active(session, settings, TENANT_A) is True
        assert automated_paper_actions_blocked(True) is True
        blocked = runtime._scan_target(session, _scan_target(TENANT_A))
        assert read_kill_switch_active(session, settings, TENANT_B) is False
        with pytest.raises(RuntimeError, match="evidence factory"):
            runtime._scan_target(session, _scan_target(TENANT_B))

    assert blocked.status == "blocked"
    assert blocked.reason_code == "kill_switch_active"
    assert blocked.kill_switch_active is True
    assert blocked.candidate_ids == ()
    assert blocked.organization_id == TENANT_A
    assert probe.unused is True
    assert probe.execution == []
    assert probe.telegram == []


@requires_postgres
def test_bound_tenant_kill_switch_blocks_telegram_delivery() -> None:
    factory = phase7_plan_session_factory()
    _seed_switches(factory, tenant_a_active=True, tenant_b_active=False)
    runtime, transport, protocol, binding_id = _bound_runtime(
        factory,
        organization_id=TENANT_A,
        worker_id="deliver-tenant-a",
    )
    protocol.enqueue_outbound(
        organization_id=TENANT_A,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="paper notice",
        idempotency_key="tenant-a-blocked",
    )

    cycle = runtime.run_cycle()

    assert cycle.kill_switch_active is True
    assert cycle.delivered == 0
    assert cycle.poll_applied == 0
    assert cycle.last_error_code == "kill_switch_active"
    assert transport.send_count == 0
    pending = protocol.store.list_outbox(organization_id=TENANT_A)
    assert any(row.state is not OutboxState.ACKNOWLEDGED for row in pending)
    with factory() as session:
        row = load_runtime_rows(session)[TELEGRAM_COMPONENT]
        assert read_kill_switch_active(session, _projection_settings(), TENANT_B) is False
    assert row.telegram_runtime_state == "paused"
    assert row.kill_switch_active is True


@requires_postgres
def test_unrelated_tenant_kill_switch_does_not_block_delivery() -> None:
    factory = phase7_plan_session_factory()
    _seed_switches(factory, tenant_a_active=True, tenant_b_active=False)
    runtime, transport, protocol, binding_id = _bound_runtime(
        factory,
        organization_id=TENANT_B,
        worker_id="deliver-tenant-b",
    )
    protocol.enqueue_outbound(
        organization_id=TENANT_B,
        user_id=USER,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
        text="paper notice",
        idempotency_key="tenant-b-clear",
    )

    cycle = runtime.run_cycle()

    assert cycle.kill_switch_active is False
    assert cycle.delivered == 1
    assert transport.send_count == 1
    assert cycle.last_error_code != "kill_switch_active"
