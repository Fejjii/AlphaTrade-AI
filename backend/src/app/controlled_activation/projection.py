"""Install the paper Telegram scan hook when the controlled package is armed.

The hook projects a Watcher scan into the durable outbox. It does not mint a
Candidate, override SetupAssessment, override risk, activate a strategy, or
place an order. When the package is disarmed this returns None and the worker
scans without a hook.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid5

from sqlalchemy.orm import Session, sessionmaker

from app.candidate_alerts.gateway import CandidateAlertGateway
from app.controlled_activation.profile import controlled_telegram_projection
from app.core.config import Settings, TelegramInboundMode
from app.paper_interaction.durable_context import build_durable_discussion_context
from app.runtime.canonical import ProductionCanonicalRuntime, build_production_canonical_runtime
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.memory import UtcClock
from app.telegram_activation.controller import TelegramPaperActivation
from app.telegram_activation.errors import TelegramActivationError
from app.telegram_activation.intake import HttpTelegramUpdateSource, TelegramUpdateSource
from app.telegram_activation.policy import PAPER_ACTIVATION_BACKOFF
from app.telegram_activation.transport import (
    GuardedTelegramTransport,
    HttpTelegramTransport,
    OutboundRateLimiter,
)
from app.telegram_paper_agent.contracts import PaperAlertRecipient
from app.telegram_paper_agent.gateway import TelegramPaperAgent
from app.telegram_paper_agent.identity import PAPER_NOTIFY_IDENTITY_NAMESPACE
from app.telegram_security.clock import Clock, SystemClock
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import TelegramTransport
from app.workers.watcher_paper import WatcherPaperScanReport


@dataclass(frozen=True, slots=True)
class ControlledProjection:
    """Armed in-process projection. The worker installs ``hook`` only."""

    hook: Callable[[WatcherPaperScanReport], None]
    agent: TelegramPaperAgent
    controller: TelegramPaperActivation
    recipient: PaperAlertRecipient


def build_controlled_scan_hook(
    settings: Settings,
    session_factory: sessionmaker[Session],
    *,
    transport: TelegramTransport | None = None,
    update_source: TelegramUpdateSource | None = None,
    clock: Clock | None = None,
) -> ControlledProjection | None:
    """Return an armed hook, or None when Telegram is not part of the package.

    A configured projection that cannot bind or arm raises
    ``TelegramActivationError`` so the Watcher does not scan without it.
    """

    if not controlled_telegram_projection(settings):
        return None
    from app.telegram_activation.identity import bot_identity_mismatch

    if bot_identity_mismatch(
        bot_id=settings.telegram_bot_id,
        token=settings.telegram_bot_token,
    ):
        raise TelegramActivationError(
            "Configured Telegram bot id does not match the bot token.",
            reason="bot_identity_mismatch",
        )
    resolved_clock = clock if clock is not None else SystemClock()
    from app.persistence.composition import build_postgres_telegram_security_store
    from app.persistence.telegram_activation import PostgresActivationCursorStore
    from app.persistence.telegram_paper_agent import PostgresPaperAgentStore

    store = build_postgres_telegram_security_store(session_factory)
    binding = store.get_active_binding_for_chat(
        bot_id=settings.telegram_bot_id.strip(),
        chat_id=settings.telegram_chat_id.strip(),
    )
    if binding is None:
        raise TelegramActivationError(
            "No verified private binding matches the configured bot and chat.",
            reason="recipient_binding_missing",
        )
    recipient = PaperAlertRecipient(
        organization_id=binding.organization_id,
        user_id=binding.user_id,
        account_id=uuid5(PAPER_NOTIFY_IDENTITY_NAMESPACE, f"acct:{binding.binding_id}"),
        binding_id=binding.binding_id,
        bot_id=binding.bot_id,
        chat_id=binding.chat_id,
    )
    resolved_transport = transport or _network_transport(
        settings,
        clock=resolved_clock,
        organization_id=recipient.organization_id,
        bot_id=recipient.bot_id,
        chat_id=recipient.chat_id,
        session_factory=session_factory,
    )
    if resolved_transport is None:
        raise TelegramActivationError(
            "Telegram network delivery is not permitted.",
            reason="outbound_transport_disabled",
        )
    protocol = TelegramSecurityProtocol(
        store=store,
        transport=resolved_transport,
        clock=resolved_clock,
        enabled=True,
        retry_backoff=PAPER_ACTIVATION_BACKOFF,
    )
    canonical = build_production_canonical_runtime(
        session_factory,
        settings=settings,
        clock=UtcClock(),
    )
    agent = TelegramPaperAgent(
        protocol=protocol,
        candidates=CandidateAlertGateway(
            lifecycle=canonical.lifecycle,
            protocol=protocol,
            clock=resolved_clock,
        ),
        clock=resolved_clock,
        store=PostgresPaperAgentStore(session_factory),
        context=build_durable_discussion_context(session_factory),
        enabled=True,
    )
    source = update_source or _update_source(settings)
    controller = TelegramPaperActivation(
        settings=settings,
        agent=agent,
        recipient=recipient,
        clock=resolved_clock,
        outbound_ready=True,
        update_source=source,
        cursor_store=PostgresActivationCursorStore(session_factory),
        candidate_loader=lambda organization_id: _latest_candidate(canonical, organization_id),
    )
    controller.arm()
    return ControlledProjection(
        hook=controller.paper_scan_hook(),
        agent=agent,
        controller=controller,
        recipient=recipient,
    )


def _network_transport(
    settings: Settings,
    *,
    clock: Clock,
    organization_id: UUID,
    bot_id: str,
    chat_id: str,
    session_factory: sessionmaker[Session],
) -> TelegramTransport | None:
    if not settings.telegram_network_permitted or not settings.telegram_bot_token.strip():
        return None
    from app.persistence.telegram_activation import PostgresActivationSendLedger

    inner = HttpTelegramTransport(
        token=settings.telegram_bot_token,
        timeout_seconds=settings.telegram_timeout_seconds,
        network_permitted=True,
    )
    return GuardedTelegramTransport(
        inner=inner,
        limiter=OutboundRateLimiter(
            clock,
            per_chat=settings.telegram_outbound_per_chat,
            window=timedelta(seconds=settings.telegram_outbound_window_seconds),
        ),
        ledger=PostgresActivationSendLedger(session_factory),
        organization_id=organization_id,
        bot_id=bot_id,
        chat_id=chat_id,
        clock=clock,
    )


def _latest_candidate(
    runtime: ProductionCanonicalRuntime, organization_id: UUID
) -> Candidate | None:
    rows, _total = runtime.candidate_repository.list_for_organization(organization_id, limit=1)
    if not rows:
        return None
    return rows[0]


def _update_source(settings: Settings) -> TelegramUpdateSource | None:
    if settings.telegram_inbound_mode is not TelegramInboundMode.POLLING:
        return None
    if not settings.telegram_network_permitted or not settings.telegram_bot_token.strip():
        return None
    return HttpTelegramUpdateSource(
        token=settings.telegram_bot_token,
        timeout_seconds=settings.telegram_timeout_seconds,
        network_permitted=True,
    )
