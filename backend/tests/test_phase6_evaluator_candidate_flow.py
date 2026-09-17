"""Combined Phase 6 evaluator → canonical candidate authority flow.

The evaluator remains setup-truth only. CandidateLifecycleService remains the
only candidate authority. This module wires the two against CanonicalEvidenceWindowV1
without PostgreSQL, watcher, Telegram, eligibility, or execution.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.market_contracts.first_slice import FIRST_SLICE_PATTERN_NAME
from app.signal_fusion.adapters import evidence_window_from_assessment_command
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.enums import CandidateState, SetupAssessmentState
from app.signal_fusion.errors import (
    CandidateCreationAuthorityError,
    ExpiredCandidateAssessmentError,
)
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.lifecycle import (
    CandidateCreationCommand,
    CandidateLifecycleService,
    in_memory_candidate_lifecycle,
)
from tests.fixtures.phase6_first_slice.factory import build_fixture_corpus
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_evaluator import EvaluatorWorld, make_world, subsequent_bars


def _evaluate(world: EvaluatorWorld) -> SetupAssessment:
    return evaluate_setup(
        policy=world.policy,
        command=world.command,
        evidence=world.evidence,
        evaluated_at=world.evaluated_at,
    )


def _creation_command(
    world: EvaluatorWorld,
    assessment: SetupAssessment,
    *,
    idempotency_key: str = "eval-candidate-create-1",
    correlation_id: UUID | None = None,
) -> CandidateCreationCommand:
    window = evidence_window_from_assessment_command(world.command)
    return CandidateCreationCommand(
        assessment=assessment,
        evidence_window=window,
        executable_setup=world.command.executable_setup,
        evidence_identity=world.command.evidence_identity,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id or assessment.correlation_id,
    )


def _service() -> CandidateLifecycleService:
    return in_memory_candidate_lifecycle(now=EVALUATED_AT)


def test_confirmed_setup_creates_exactly_one_active_candidate() -> None:
    world = make_world()
    assessment = _evaluate(world)
    assert assessment.state is SetupAssessmentState.CONFIRMED_SETUP
    window = evidence_window_from_assessment_command(world.command)
    assert assessment.evidence_window_hash == window.content_hash
    assert "Bearish Liquidity Sweep with CVD Divergence" in assessment.explanation
    assert "exhaustion" not in assessment.explanation.lower()

    service = _service()
    first = service.create_from_confirmed_setup(_creation_command(world, assessment))
    duplicate_eval = _evaluate(world)
    second = service.create_from_confirmed_setup(
        _creation_command(
            world,
            duplicate_eval,
            idempotency_key="eval-candidate-create-2",
            correlation_id=uuid4(),
        )
    )
    assert first.state is CandidateState.ACTIVE
    assert second.candidate_id == first.candidate_id
    assert second.content_hash == first.content_hash
    assert service.get_by_uniqueness(first.uniqueness_tuple()) == first
    assert len({first.candidate_id, second.candidate_id}) == 1


def test_duplicate_semantic_evaluation_does_not_create_second_candidate() -> None:
    watcher = make_world()
    detector = make_world()
    left = _evaluate(watcher)
    right = _evaluate(detector)
    assert left.state is right.state is SetupAssessmentState.CONFIRMED_SETUP
    assert left.evidence_window_hash == right.evidence_window_hash

    service = _service()
    first = service.create_from_confirmed_setup(_creation_command(watcher, left))
    second = service.create_from_confirmed_setup(
        _creation_command(detector, right, idempotency_key="eval-candidate-create-detector")
    )
    assert first.candidate_id == second.candidate_id
    assert first.uniqueness_tuple().canonical_hash() == second.uniqueness_tuple().canonical_hash()


@pytest.mark.parametrize(
    ("expected", "world_factory"),
    [
        (
            SetupAssessmentState.NO_SETUP,
            lambda: make_world(bar_15m_count=10, pattern_bars=True, include_snapshot=False),
        ),
        (SetupAssessmentState.WATCH, lambda: make_world(pattern_bars=False)),
        (
            SetupAssessmentState.PARTIAL_MATCH,
            lambda: make_world(trigger_volume=Decimal("20")),
        ),
    ],
)
def test_non_confirmed_evaluator_states_cannot_create_candidate(
    expected: SetupAssessmentState, world_factory: Callable[[], EvaluatorWorld]
) -> None:
    world = world_factory()
    assessment = _evaluate(world)
    assert assessment.state is expected
    with pytest.raises(CandidateCreationAuthorityError, match="cannot create"):
        _service().create_from_confirmed_setup(_creation_command(world, assessment))


def test_invalidated_assessment_cannot_create_active_candidate() -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=1, high=Decimal("100500"))
    world = make_world(subsequent=tuple(later))
    assessment = _evaluate(world)
    assert assessment.state is SetupAssessmentState.INVALIDATED
    with pytest.raises(CandidateCreationAuthorityError, match="INVALIDATED"):
        _service().create_from_confirmed_setup(_creation_command(world, assessment))


def test_expired_assessment_cannot_create_active_candidate() -> None:
    base = make_world()
    later = subsequent_bars(base.trigger, count=2, high=Decimal("100010"))
    world = make_world(subsequent=tuple(later))
    assessment = _evaluate(world)
    assert assessment.state is SetupAssessmentState.EXPIRED
    with pytest.raises(ExpiredCandidateAssessmentError, match="EXPIRED"):
        _service().create_from_confirmed_setup(_creation_command(world, assessment))


def test_golden_fixture_corpus_is_preserved() -> None:
    corpus = {fixture.fixture_id: fixture for fixture in build_fixture_corpus()}
    confirmed = corpus["confirmed-setup"]
    assert confirmed.strategy_name == FIRST_SLICE_PATTERN_NAME
    assert confirmed.expected.candidate_creation is True
    assert confirmed.expected.assessment_state is SetupAssessmentState.CONFIRMED_SETUP
    assert corpus["no-setup"].expected.candidate_creation is False
    assert corpus["watch"].expected.candidate_creation is False
    assert corpus["partial-match"].expected.candidate_creation is False
    assert "exhaustion" not in FIRST_SLICE_PATTERN_NAME.lower()
