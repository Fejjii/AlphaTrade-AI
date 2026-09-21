"""Deterministic first-slice Phase 6 fusion evaluator matrix."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.market_contracts.cursor import TradeStreamSnapshot
from app.signal_fusion.adapters import evidence_window_from_assessment_command
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.enums import (
    AssessmentReasonCode,
    EvidenceAdapterKind,
    SetupAssessmentState,
)
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.first_slice_types import FIRST_SLICE_RULE_IDS
from tests.support.phase5_market import spot_identity
from tests.support.phase6_evaluator import (
    SWING_HIGH,
    make_world,
    subsequent_bars,
)
from tests.support.phase6_fusion import ACCOUNT_ID, USER_ID, eth_evidence_identity


def _rule(assessment: SetupAssessment, rule_id: str):
    matches = [item for item in assessment.rule_results if item.rule_id == rule_id]
    assert len(matches) == 1
    return matches[0]


def test_confirmed_setup_exact_match() -> None:
    world = make_world()
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.CONFIRMED_SETUP
    assert AssessmentReasonCode.ALL_MANDATORY_EVIDENCE_CONFIRMED in assessment.reason_codes
    assert [item.rule_id for item in assessment.rule_results] == list(FIRST_SLICE_RULE_IDS)
    assert all(item.passed for item in assessment.rule_results)
    assert "exhaustion" not in assessment.explanation.lower()
    assert "Bearish Liquidity Sweep with CVD Divergence" in assessment.explanation
    assert "user_id" not in type(assessment).model_fields
    assert "account_id" not in type(assessment).model_fields


def test_no_setup_incomplete_warmup() -> None:
    world = make_world(bar_15m_count=10, pattern_bars=True, include_snapshot=False)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert not _rule(assessment, "complete_warmup").passed


def test_watch_when_preconditions_pass_without_swing() -> None:
    world = make_world(pattern_bars=False)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.WATCH
    assert AssessmentReasonCode.PRECONDITIONS_PASSED in assessment.reason_codes
    assert _rule(assessment, "complete_warmup").passed
    assert not _rule(assessment, "confirmed_swing_high").passed


def test_partial_match_volume_failure() -> None:
    world = make_world(trigger_volume=Decimal("20"))
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.PARTIAL_MATCH
    assert not _rule(assessment, "volume_spike").passed
    assert _rule(assessment, "volume_spike").reason_code == "volume_failure"
    assert _rule(assessment, "htf_resistance_context").passed
    assert _rule(assessment, "ltf_liquidity_sweep").passed


def test_resistance_tolerance_failure_is_watch() -> None:
    world = make_world(resistance_price=SWING_HIGH + Decimal("50000"))
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.WATCH
    assert _rule(assessment, "confirmed_swing_high").passed
    assert not _rule(assessment, "htf_resistance_context").passed
    assert _rule(assessment, "htf_resistance_context").reason_code == "resistance_tolerance_failure"


def test_cvd_divergence_failure_is_partial_match() -> None:
    world = make_world(trade_mode="cvd_fail")
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.PARTIAL_MATCH
    assert _rule(assessment, "ltf_liquidity_sweep").passed
    assert not _rule(assessment, "bearish_cvd_divergence").passed
    assert _rule(assessment, "bearish_cvd_divergence").reason_code == "cvd_divergence_failure"
    assert _rule(assessment, "aggressive_sell_imbalance").passed


def test_aggressive_sell_imbalance_failure_is_partial_match() -> None:
    world = make_world(trade_mode="imbalance_fail")
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.PARTIAL_MATCH
    assert not _rule(assessment, "aggressive_sell_imbalance").passed
    assert (
        _rule(assessment, "aggressive_sell_imbalance").reason_code
        == "aggressive_sell_imbalance_failure"
    )


def test_price_invalidation() -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=1, high=Decimal("100500"))
    world = make_world(subsequent=tuple(later))
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.INVALIDATED
    assert AssessmentReasonCode.PATTERN_INVALIDATED in assessment.reason_codes
    assert not _rule(assessment, "not_invalidated").passed


def test_expiry_after_two_final_15m_bars() -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=2, high=Decimal("100010"))
    world = make_world(subsequent=tuple(later))
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.EXPIRED
    assert AssessmentReasonCode.VALIDITY_INTERVAL_ELAPSED in assessment.reason_codes
    assert not _rule(assessment, "not_expired").passed
    assert _rule(assessment, "not_invalidated").passed


def test_stale_evidence_fail_closed() -> None:
    world = make_world(stale_command=True)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at + timedelta(seconds=30),
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert not _rule(assessment, "freshness").passed
    assert AssessmentReasonCode.REQUIRED_SOURCE_STALE in assessment.reason_codes


def test_wrong_market_fail_closed() -> None:
    world = make_world()
    command = world.command.model_copy(update={"evidence_identity": spot_identity()})
    assessment = evaluate_setup(
        policy=world.policy,
        command=command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert not _rule(assessment, "market_identity").passed
    assert AssessmentReasonCode.WRONG_VENUE_OR_MARKET in assessment.reason_codes


def test_wrong_instrument_fail_closed() -> None:
    world = make_world()
    command = world.command.model_copy(update={"evidence_identity": eth_evidence_identity()})
    assessment = evaluate_setup(
        policy=world.policy,
        command=command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert not _rule(assessment, "market_identity").passed


def test_forming_candle_fail_closed() -> None:
    world = make_world(forming_trigger=True)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert not _rule(assessment, "final_evidence").passed
    assert _rule(assessment, "final_evidence").reason_code == "forming_evidence"


def test_gap_fail_closed() -> None:
    world = make_world()
    assert world.snapshot is not None
    missing = world.snapshot.trades[:10] + world.snapshot.trades[11:]
    forged = TradeStreamSnapshot.model_construct(
        cursor=world.snapshot.cursor,
        trades=missing,
        coverage=world.snapshot.coverage,
        usable=True,
    )
    evidence = world.evidence.model_copy(update={"snapshot": forged})
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    assert not _rule(assessment, "no_unresolved_gap").passed
    assert AssessmentReasonCode.REQUIRED_SOURCE_GAPPED in assessment.reason_codes


def test_missing_evidence_fail_closed() -> None:
    world = make_world(include_snapshot=False)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is SetupAssessmentState.NO_SETUP
    missing = (
        not _rule(assessment, "freshness").passed or not _rule(assessment, "complete_warmup").passed
    )
    assert missing


def test_invalid_manual_resistance_revision() -> None:
    world = make_world(resistance_valid=False)
    assessment = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is not SetupAssessmentState.CONFIRMED_SETUP
    assert not _rule(assessment, "manual_4h_resistance").passed
    assert _rule(assessment, "manual_4h_resistance").reason_code == "invalid_manual_level_revision"


def test_corrected_evidence_revision_changes_window() -> None:
    first = make_world(trigger_revision=1)
    second = make_world(trigger_revision=2, trigger_volume=Decimal("20"))
    left = evaluate_setup(
        policy=first.policy,
        command=first.command,
        evidence=first.evidence,
        evaluated_at=first.evaluated_at,
    )
    right = evaluate_setup(
        policy=second.policy,
        command=second.command,
        evidence=second.evidence,
        evaluated_at=second.evaluated_at,
    )
    assert left.state is SetupAssessmentState.CONFIRMED_SETUP
    assert right.state is SetupAssessmentState.PARTIAL_MATCH
    assert left.evidence_window_hash != right.evidence_window_hash
    assert first.trigger.revision == 1
    assert second.trigger.revision == 2
    assert first.trigger.source_event_id == second.trigger.source_event_id


def test_evidence_order_does_not_change_assessment() -> None:
    left_world = make_world()
    right_world = make_world(shuffle_bars=True, observation_order=(4, 2, 0, 3, 1))
    left = evaluate_setup(
        policy=left_world.policy,
        command=left_world.command,
        evidence=left_world.evidence,
        evaluated_at=left_world.evaluated_at,
    )
    right = evaluate_setup(
        policy=right_world.policy,
        command=right_world.command,
        evidence=right_world.evidence,
        evaluated_at=right_world.evaluated_at,
    )
    assert left.state is SetupAssessmentState.CONFIRMED_SETUP
    assert right.state is SetupAssessmentState.CONFIRMED_SETUP
    assert left.evidence_window_hash == right.evidence_window_hash
    assert left.rule_results == right.rule_results
    assert left.content_hash == right.content_hash


def test_watcher_and_detector_same_canonical_window() -> None:
    watcher = make_world(adapter_kind=EvidenceAdapterKind.WATCHER)
    detector = make_world(adapter_kind=EvidenceAdapterKind.DETECTOR)
    left_window = evidence_window_from_assessment_command(watcher.command)
    right_window = evidence_window_from_assessment_command(detector.command)
    assert left_window.content_hash == right_window.content_hash
    left = evaluate_setup(
        policy=watcher.policy,
        command=watcher.command,
        evidence=watcher.evidence,
        evaluated_at=watcher.evaluated_at,
    )
    right = evaluate_setup(
        policy=detector.policy,
        command=detector.command,
        evidence=detector.evidence,
        evaluated_at=detector.evaluated_at,
    )
    assert left.state is right.state is SetupAssessmentState.CONFIRMED_SETUP
    assert left.evidence_window_hash == right.evidence_window_hash
    assert left.rule_results == right.rule_results
    assert left.content_hash == right.content_hash


def test_account_context_cannot_change_setup_truth() -> None:
    world = make_world()
    left = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        account_context={"user_id": USER_ID, "account_id": ACCOUNT_ID, "leverage": 25},
    )
    right = evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
        account_context=None,
    )
    assert left.content_hash == right.content_hash
    assert left.state is SetupAssessmentState.CONFIRMED_SETUP
