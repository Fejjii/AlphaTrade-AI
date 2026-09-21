"""Helpers for paper Telegram agent tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.candidate_alerts.gateway import CandidateAlertGateway
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.telegram_paper_agent.contracts import PaperAlertRecipient
from app.telegram_paper_agent.gateway import TelegramPaperAgent
from app.telegram_paper_agent.memory import InMemoryPaperContext
from app.telegram_security.clock import FrozenClock
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import FakeTelegramTransport
from tests.support.candidate_alerts import enabled_alert_world
from tests.support.phase6_fusion import ACCOUNT_ID


@dataclass
class PaperAgentWorld:
    agent: TelegramPaperAgent
    protocol: TelegramSecurityProtocol
    lifecycle: CandidateLifecycleService
    transport: FakeTelegramTransport
    binding_id: UUID
    recipient: PaperAlertRecipient
    candidate: Candidate
    assessment: SetupAssessment
    window: CanonicalEvidenceWindowV1


def enabled_paper_agent_world(*, context: InMemoryPaperContext | None = None) -> PaperAgentWorld:
    inner = enabled_alert_world()
    clock = FrozenClock(inner.candidate.created_at)
    gateway = CandidateAlertGateway(
        lifecycle=inner.lifecycle, protocol=inner.protocol, clock=clock, store=inner.gateway.store
    )
    agent = TelegramPaperAgent(
        protocol=inner.protocol,
        candidates=gateway,
        clock=clock,
        context=context or InMemoryPaperContext(),
        enabled=True,
    )
    recipient = PaperAlertRecipient(
        organization_id=inner.recipient.organization_id,
        user_id=inner.recipient.user_id,
        account_id=ACCOUNT_ID,
        binding_id=inner.binding_id,
        bot_id=inner.recipient.bot_id,
        chat_id=inner.recipient.chat_id,
    )
    return PaperAgentWorld(
        agent=agent,
        protocol=inner.protocol,
        lifecycle=inner.lifecycle,
        transport=inner.transport,
        binding_id=inner.binding_id,
        recipient=recipient,
        candidate=inner.candidate,
        assessment=inner.assessment,
        window=inner.window,
    )
