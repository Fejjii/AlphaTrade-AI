"""Helpers for canonical Candidate Telegram alert tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.candidate_alerts.contracts import CandidateAlertRecipient
from app.candidate_alerts.gateway import CandidateAlertGateway
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.signal_fusion.lifecycle import CandidateLifecycleService, in_memory_candidate_lifecycle
from app.telegram_security.clock import FrozenClock
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import FakeTelegramTransport
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import (
    ACCOUNT_ID,
    ORG_ID,
    USER_ID,
    make_assessment,
    make_creation_command,
    make_evidence_window,
)
from tests.support.telegram_security import BOT, CHAT, TokenSeq, enroll

FIRST_SLICE_EXPLANATION = (
    "Bearish Liquidity Sweep with CVD Divergence and Aggressive Sell Imbalance "
    "at 4h Resistance: CONFIRMED_SETUP; all mandatory first-slice predicates passed."
)


@dataclass
class AlertWorld:
    gateway: CandidateAlertGateway
    protocol: TelegramSecurityProtocol
    lifecycle: CandidateLifecycleService
    transport: FakeTelegramTransport
    binding_id: UUID
    recipient: CandidateAlertRecipient
    candidate: Candidate
    assessment: SetupAssessment
    window: CanonicalEvidenceWindowV1


def enabled_alert_world(*, explanation: str = FIRST_SLICE_EXPLANATION) -> AlertWorld:
    clock = FrozenClock(EVALUATED_AT)
    transport = FakeTelegramTransport()
    protocol = TelegramSecurityProtocol.in_memory(
        enabled=True,
        clock=clock,
        transport=transport,
        token_factory=TokenSeq(),
    )
    lifecycle = in_memory_candidate_lifecycle(now=EVALUATED_AT)
    gateway = CandidateAlertGateway(lifecycle=lifecycle, protocol=protocol, clock=clock)
    _, binding_id = enroll(protocol, organization_id=ORG_ID, user_id=USER_ID)
    window = make_evidence_window()
    assessment = make_assessment(window, explanation=explanation)
    candidate = lifecycle.create_from_confirmed_setup(
        make_creation_command(window=window, assessment=assessment)
    )
    recipient = CandidateAlertRecipient(
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        binding_id=binding_id,
        bot_id=BOT,
        chat_id=CHAT,
    )
    return AlertWorld(
        gateway=gateway,
        protocol=protocol,
        lifecycle=lifecycle,
        transport=transport,
        binding_id=binding_id,
        recipient=recipient,
        candidate=candidate,
        assessment=assessment,
        window=window,
    )
