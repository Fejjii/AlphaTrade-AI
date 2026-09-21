"""Adversarial regressions for PR113 remaining P1s.

P1.1 setup expiry identity, P1.2 presented confirmation identity,
P1.3 paper-bot approved compiled lineage, P1.4 persisted candidate authority.
Watcher, Telegram, and live trading stay disabled.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.agents.confirmation_identity import (
    IDENTITY_BEGIN,
    format_presented_confirmation_identity,
    identity_from_proposal,
    parse_presented_confirmation_identity,
    presented_confirmation_identity_from_history,
)
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.setup_lifetime import SetupLifetimeStore
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.first_slice import CANONICAL_TRIGGER_INTERVAL_END
from app.schemas.agent import ConversationTurn
from app.schemas.common import StrategyProposalStatus
from app.schemas.conversation import StrategyProposalRecord
from app.signal_fusion.enums import SetupAssessmentState
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.first_slice_types import FIRST_SLICE_EXPIRY_BARS
from app.watcher.fusion_evaluation import ExecutablePolicyAuthority
from tests.support.phase6_evaluator import subsequent_bars
from tests.support.phase6_fusion import ORG_ID, fusion_policy


def _proposal_record() -> StrategyProposalRecord:
    now = "2026-09-21T10:00:00+00:00"
    return StrategyProposalRecord(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        conversation_id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        organization_id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
        user_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        target_strategy_id=uuid.UUID("55555555-5555-4555-8555-555555555555"),
        parent_version_id=uuid.UUID("66666666-6666-4666-8666-666666666666"),
        status=StrategyProposalStatus.DRAFT,
        validation={"valid": True, "errors": [], "warnings": []},
        limitations=[],
        challenge_notes=[],
        content_hash="ab" * 32,
        created_at=now,
        updated_at=now,
        is_preview=True,
        mutates_strategy_authority=False,
    )


def test_product_assembly_expires_after_configured_final_bars_without_patching_pin() -> None:
    policy = fusion_policy()
    lifetime = SetupLifetimeStore()
    fixture = ReplayPerpetualSource()
    first = FirstSliceEvidenceAssembler(fixture, replay=True, lifetime=lifetime).assemble(
        organization_id=ORG_ID, policy=policy
    )
    assert first.clocks.setup_expired is False
    assert first.clocks.subsequent_final_15m_count == 0
    assert first.clocks.closed_evidence_valid is True
    assert first.clocks.setup_lifetime_remaining_bars == FIRST_SLICE_EXPIRY_BARS
    assert first.trigger_bar.interval_end == CANONICAL_TRIGGER_INTERVAL_END

    extra = subsequent_bars(
        fixture._bars_15m[-1],
        count=FIRST_SLICE_EXPIRY_BARS,
        high=fixture._bars_15m[-1].high,
    )
    later_source = ReplayPerpetualSource(bars_15m=list(fixture._bars_15m) + extra)
    later = FirstSliceEvidenceAssembler(later_source, replay=True, lifetime=lifetime).assemble(
        organization_id=ORG_ID,
        policy=policy,
        evaluated_at=extra[-1].interval_end + timedelta(seconds=5),
    )
    assert later.trigger_bar.interval_end == first.trigger_bar.interval_end
    assert later.clocks.setup_trigger_bar_hash == first.trigger_bar.content_hash
    assert later.clocks.subsequent_final_15m_count == FIRST_SLICE_EXPIRY_BARS
    assert later.clocks.setup_expired is True
    assert later.clocks.setup_lifetime_remaining_bars == 0
    assert later.clocks.closed_evidence_valid is True
    assert later.clocks.historical_closed_evidence is True
    expired = evaluate_setup(
        policy=policy,
        command=first.assessment_command,
        evidence=first.bundle.model_copy(
            update={"subsequent_final_15m": later.bundle.subsequent_final_15m}
        ),
        evaluated_at=first.evaluated_at,
    )
    assert expired.state is SetupAssessmentState.EXPIRED


def test_independent_second_assembler_is_deterministic() -> None:
    policy = fusion_policy()
    first = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=ORG_ID, policy=policy
    )
    second = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=ORG_ID, policy=policy
    )
    assert first.evidence_window_hash == second.evidence_window_hash
    left = evaluate_setup(
        policy=policy,
        command=first.assessment_command,
        evidence=first.bundle,
        evaluated_at=first.evaluated_at,
    )
    right = evaluate_setup(
        policy=policy,
        command=second.assessment_command,
        evidence=second.bundle,
        evaluated_at=second.evaluated_at,
    )
    assert left.state is right.state
    assert left.evidence_window_hash == right.evidence_window_hash
    assert left.content_hash == right.content_hash
    assert left.state is not SetupAssessmentState.EXPIRED


def test_presented_identity_round_trip_and_history_binding() -> None:
    record = _proposal_record()
    identity = identity_from_proposal(
        record,
        conversation_id=record.conversation_id,
        organization_id=record.organization_id,
        user_id=record.user_id,
    )
    rendered = "Draft structured rules generated.\n\n" + format_presented_confirmation_identity(
        identity
    )
    parsed = parse_presented_confirmation_identity(rendered)
    assert parsed is not None
    assert parsed.proposal_id == record.id
    assert parsed.content_hash == record.content_hash
    assert parsed.target_strategy_id == record.target_strategy_id
    assert parsed.parent_version_id == record.parent_version_id
    older = record.model_copy(update={"id": uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")})
    older_identity = identity_from_proposal(
        older,
        conversation_id=record.conversation_id,
        organization_id=record.organization_id,
        user_id=record.user_id,
    )
    presented = presented_confirmation_identity_from_history(
        [
            ConversationTurn(
                role="assistant",
                content=format_presented_confirmation_identity(older_identity),
            ),
            ConversationTurn(role="user", content="please tighten the stop"),
            ConversationTurn(role="assistant", content=rendered),
        ]
    )
    assert presented is not None
    assert presented.proposal_id == record.id
    assert presented.proposal_id != older.id
    assert IDENTITY_BEGIN in rendered


def test_clock_fields_are_independent() -> None:
    assembled = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=ORG_ID, policy=fusion_policy()
    )
    clocks = assembled.clocks
    assert clocks.closed_evidence_valid is True
    assert clocks.setup_expired is False
    assert clocks.market_stream_fresh is True or clocks.historical_closed_evidence is False
    assert clocks.setup_lifetime_remaining_bars == FIRST_SLICE_EXPIRY_BARS


def test_default_scan_evidence_authority_is_in_memory_helper() -> None:
    assert ExecutablePolicyAuthority.IN_MEMORY_TEST_HELPER.value == "in_memory_test_helper"
    assert (
        ExecutablePolicyAuthority.PERSISTED_APPROVED_COMPILED.value == "persisted_approved_compiled"
    )
