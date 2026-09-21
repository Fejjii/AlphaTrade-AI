"""Canonical observation binding: consumed CVD/flow/coverage identity."""

from __future__ import annotations

from app.market_contracts.hashing import semantic_content_hash
from app.market_contracts.observation import observation_from_ohlcv
from app.signal_fusion.adapters import evidence_window_from_assessment_command
from app.signal_fusion.enums import EvidenceRole, SetupAssessmentState
from app.signal_fusion.evaluator import evaluate_setup
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_evaluator import make_world


def test_cvd_signed_flow_and_coverage_observations_are_semantic() -> None:
    world = make_world()
    by_role = dict(
        zip(world.command.selected_roles, world.command.public_observations, strict=True)
    )
    assert by_role[EvidenceRole.TRIGGER_OHLCV].observation_type.value == "ohlcv"
    assert by_role[EvidenceRole.CONTEXT_OHLCV].observation_type.value == "ohlcv"
    assert by_role[EvidenceRole.CVD_WINDOW].observation_type.value == "cvd"
    assert by_role[EvidenceRole.SIGNED_FLOW].observation_type.value == "volume"
    assert by_role[EvidenceRole.TRADE_EVENT].observation_type.value == "trade"
    assert world.evidence.snapshot is not None
    assert by_role[EvidenceRole.CVD_WINDOW].payload_content_hash
    assert by_role[EvidenceRole.SIGNED_FLOW].payload_content_hash
    assert by_role[EvidenceRole.TRADE_EVENT].payload_content_hash == (
        world.evidence.snapshot.coverage.content_hash
    )


def test_changing_consumed_cvd_changes_canonical_identity() -> None:
    confirmed = make_world()
    diverged = make_world(trade_mode="cvd_fail")
    left = evidence_window_from_assessment_command(confirmed.command)
    right = evidence_window_from_assessment_command(diverged.command)
    assert left.content_hash != right.content_hash
    left_eval = evaluate_setup(
        policy=confirmed.policy,
        command=confirmed.command,
        evidence=confirmed.evidence,
        evaluated_at=confirmed.evaluated_at,
    )
    right_eval = evaluate_setup(
        policy=diverged.policy,
        command=diverged.command,
        evidence=diverged.evidence,
        evaluated_at=diverged.evaluated_at,
    )
    assert left_eval.state is SetupAssessmentState.CONFIRMED_SETUP
    assert right_eval.state is not SetupAssessmentState.CONFIRMED_SETUP
    assert left_eval.evidence_window_hash != right_eval.evidence_window_hash


def test_ohlcv_placeholder_for_cvd_fails_closed() -> None:
    world = make_world()
    fake = observation_from_ohlcv(
        world.trigger,
        identity=world.command.evidence_identity,
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=world.command.public_observations[0].freshness_state,
    )
    observations = list(world.command.public_observations)
    roles = list(world.command.selected_roles)
    cvd_index = roles.index(EvidenceRole.CVD_WINDOW)
    observations[cvd_index] = fake
    dishonest = world.command.model_copy(update={"public_observations": tuple(observations)})
    honest_hash = evidence_window_from_assessment_command(world.command).content_hash
    dishonest_hash = evidence_window_from_assessment_command(dishonest).content_hash
    assert honest_hash != dishonest_hash
    assessment = evaluate_setup(
        policy=world.policy,
        command=dishonest,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )
    assert assessment.state is not SetupAssessmentState.CONFIRMED_SETUP


def test_transport_observed_at_does_not_fork_envelope_hash() -> None:
    world = make_world()
    cvd_obs = dict(
        zip(world.command.selected_roles, world.command.public_observations, strict=True)
    )[EvidenceRole.CVD_WINDOW]
    shifted = cvd_obs.model_copy(update={"observed_at": EVALUATED_AT.replace(second=8)})
    assert semantic_content_hash(cvd_obs) == semantic_content_hash(shifted)
