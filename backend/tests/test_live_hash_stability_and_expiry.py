"""Live hash stability, quote vs setup clocks, and setup expiry."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.setup_lifetime import SetupLifetimeStore
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.first_slice import CANONICAL_EVALUATED_AT, CANONICAL_TRIGGER_INTERVAL_END
from app.market_contracts.freshness import FIRST_SLICE_TRADE_MAX_AGE_SECONDS
from app.signal_fusion.adapters import evidence_window_from_assessment_command
from app.signal_fusion.enums import SetupAssessmentState
from app.signal_fusion.evaluator import evaluate_setup
from tests.support.phase6_evaluator import make_world, subsequent_bars
from tests.support.phase6_fusion import ORG_ID, fusion_policy


def test_connection_ids_and_equivalent_batches_converge() -> None:
    org = ORG_ID
    policy = fusion_policy()
    first = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=org,
        policy=policy,
        connection_id=uuid4(),
        evaluated_at=CANONICAL_EVALUATED_AT,
    )
    second = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=org,
        policy=policy,
        connection_id=uuid4(),
        evaluated_at=CANONICAL_EVALUATED_AT,
    )
    assert first.connection_id != second.connection_id
    assert first.evidence_window_hash == second.evidence_window_hash
    assert first.cvd.content_hash == second.cvd.content_hash
    assert first.signed_flow.content_hash == second.signed_flow.content_hash
    assert first.completeness.coverage_content_hash == second.completeness.coverage_content_hash


def test_restart_retry_same_semantic_batch_converges() -> None:
    org = ORG_ID
    policy = fusion_policy()
    source = ReplayPerpetualSource()
    first = FirstSliceEvidenceAssembler(source, replay=True).assemble(
        organization_id=org, policy=policy, evaluated_at=CANONICAL_EVALUATED_AT
    )
    restarted = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=org, policy=policy, evaluated_at=CANONICAL_EVALUATED_AT
    )
    assert first.evidence_window_hash == restarted.evidence_window_hash


def test_market_correction_changes_identity() -> None:
    left = make_world(trigger_revision=1)
    right = make_world(trigger_revision=2)
    assert (
        evidence_window_from_assessment_command(left.command).content_hash
        != evidence_window_from_assessment_command(right.command).content_hash
    )


def test_quote_trade_and_setup_clocks_stay_separated() -> None:
    assert FIRST_SLICE_TRADE_MAX_AGE_SECONDS == 10
    org = ORG_ID
    policy = fusion_policy()
    close = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=org,
        policy=policy,
        evaluated_at=CANONICAL_EVALUATED_AT,
    )
    later = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True).assemble(
        organization_id=org,
        policy=policy,
        evaluated_at=CANONICAL_TRIGGER_INTERVAL_END + timedelta(seconds=30),
    )
    assert close.clocks.live_confirmation_window_open is True
    assert close.clocks.historical_closed_evidence is False
    assert close.clocks.subsequent_final_15m_count == 0
    assert close.clocks.trigger_finality.value == "final"
    assert later.clocks.live_confirmation_window_open is False
    assert later.clocks.historical_closed_evidence is True
    assert later.clocks.subsequent_final_15m_count == 0
    assert later.clocks.setup_expired is False
    assert later.clocks.closed_evidence_valid is True
    assert later.clocks.setup_lifetime_remaining_bars == 2
    assert close.clocks.quote_fresh or close.clocks.live_confirmation_window_open
    assert later.clocks.market_stream_fresh or later.clocks.historical_closed_evidence
    assert close.trigger_bar.content_hash == later.trigger_bar.content_hash
    assert close.evidence_window_hash == later.evidence_window_hash


def test_subsequent_closed_bars_expire_setup_on_their_own_clock() -> None:
    world = make_world()
    later = subsequent_bars(world.trigger, count=2, high=world.trigger.high)
    expired_world_evidence = world.evidence.model_copy(
        update={"subsequent_final_15m": tuple(later)}
    )
    live = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    expired = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=expired_world_evidence,
        evaluated_at=world.evaluated_at,
    )
    assert live.state is SetupAssessmentState.CONFIRMED_SETUP
    assert expired.state is SetupAssessmentState.EXPIRED
    assert live.evidence_window_hash == expired.evidence_window_hash

    policy = fusion_policy()
    lifetime = SetupLifetimeStore()
    fixture = ReplayPerpetualSource()
    FirstSliceEvidenceAssembler(fixture, replay=True, lifetime=lifetime).assemble(
        organization_id=ORG_ID, policy=policy, evaluated_at=CANONICAL_EVALUATED_AT
    )
    extra = subsequent_bars(fixture._bars_15m[-1], count=2, high=fixture._bars_15m[-1].high)
    source = ReplayPerpetualSource(bars_15m=list(fixture._bars_15m) + extra)
    assembled = FirstSliceEvidenceAssembler(source, replay=True, lifetime=lifetime).assemble(
        organization_id=ORG_ID,
        policy=policy,
        evaluated_at=extra[-1].interval_end + timedelta(seconds=5),
    )
    assert assembled.clocks.subsequent_final_15m_count == 2
    assert assembled.clocks.setup_expired is True
    assert assembled.trigger_bar.interval_end == CANONICAL_TRIGGER_INTERVAL_END
    assert assembled.clocks.closed_evidence_valid is True
    assert assembled.clocks.setup_lifetime_remaining_bars == 0
