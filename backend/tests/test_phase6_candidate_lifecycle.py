"""Phase 6 candidate lifecycle: uniqueness, idempotency, tenant isolation, terminals."""

from __future__ import annotations

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.market_contracts.enums import MarketType, SourceFamily, VenueId
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.identity import EvidenceMarketIdentity
from app.schemas.common import Timeframe, TradeDirection
from app.signal_fusion.adapters import DownstreamPaperValidationCandidateRef
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.enums import (
    CandidateReasonCode,
    CandidateState,
    EvidenceRole,
    SetupAssessmentState,
)
from app.signal_fusion.errors import (
    CandidateCreationAuthorityError,
    CandidateNotFoundError,
    ConflictingCandidateIdempotencyError,
    ConflictingCandidateTransitionError,
    ExpiredCandidateAssessmentError,
    IllegalCandidateTransitionError,
    LegacyCandidateAuthorityError,
)
from app.signal_fusion.lifecycle import (
    CandidateCreationCommand,
    CandidateLifecycleService,
    deterministic_candidate_id,
    in_memory_candidate_lifecycle,
    uniqueness_from_confirmed,
)
from app.signal_fusion.memory import InMemoryCandidateRepository
from app.signal_fusion.types import (
    ExecutableSetupRef,
    SelectedPublicObservation,
    SemanticSourceIdentity,
    selected_observation_from_public,
)
from tests.support.phase5_market import EVALUATED_AT, TRIGGER_OPEN, eth_instrument
from tests.support.phase6_fusion import (
    ASSESSMENT_ID,
    COMPILED_SETUP_ID,
    CORRELATION_B,
    ORG_ID,
    SETUP_CONTENT_HASH,
    blofin_evidence_identity,
    eth_evidence_identity,
    executable_setup,
    interval,
    make_assessment,
    make_creation_command,
    make_evidence_window,
    public_observation,
)

ORG_B = UUID("aaaaaaaa-bbbb-cccc-dddd-aaaaaaaaaaaa")
STRATEGY_VERSION_B = UUID("dddddddd-dddd-dddd-dddd-000000000002")
COMPILED_SETUP_B = UUID("eeeeeeee-eeee-eeee-eeee-000000000002")
ASSESSMENT_B = UUID("11111111-1111-1111-1111-000000000002")

_TERMINAL_REASON = {
    CandidateState.REJECTED: CandidateReasonCode.REJECTED,
    CandidateState.SKIPPED: CandidateReasonCode.SKIPPED,
    CandidateState.EXPIRED: CandidateReasonCode.EXPIRED,
    CandidateState.INVALIDATED: CandidateReasonCode.INVALIDATED,
}


def _service() -> CandidateLifecycleService:
    return in_memory_candidate_lifecycle(now=EVALUATED_AT)


def _create(
    service: CandidateLifecycleService | None = None,
) -> tuple[CandidateLifecycleService, Candidate]:
    lifecycle = service or _service()
    candidate = lifecycle.create_from_confirmed_setup(make_creation_command())
    return lifecycle, candidate


def _transition(
    service: CandidateLifecycleService,
    candidate_id: UUID,
    new_state: CandidateState,
    *,
    organization_id: UUID = ORG_ID,
    idempotency_key: str = "candidate-transition-1",
    correlation_id: UUID = CORRELATION_B,
) -> Candidate:
    reason = (
        CandidateReasonCode.PLAN_CREATED
        if new_state is CandidateState.PLAN_CREATED
        else _TERMINAL_REASON[new_state]
    )
    return service.transition(
        organization_id=organization_id,
        candidate_id=candidate_id,
        new_state=new_state,
        reason_codes=(reason,),
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )


def test_first_confirmed_setup_creates_one_active_candidate() -> None:
    service, candidate = _create()
    assert candidate.state is CandidateState.ACTIVE
    assert candidate.transition_version == 1
    assert candidate.organization_id == ORG_ID
    assert candidate.setup_definition_id == COMPILED_SETUP_ID
    assert candidate.assessment_id == ASSESSMENT_ID
    keyed = service.get_by_uniqueness(candidate.uniqueness_tuple())
    assert keyed is not None
    assert keyed.candidate_id == candidate.candidate_id
    by_id = service.get_by_candidate_id(ORG_ID, candidate.candidate_id)
    assert by_id is not None
    assert by_id.content_hash == candidate.content_hash
    assert service.latest_projection(ORG_ID, candidate.candidate_id) == candidate
    assert service.transition_history(ORG_ID, candidate.candidate_id) == ()
    assert deterministic_candidate_id(candidate.uniqueness_tuple()) == candidate.candidate_id


def test_duplicate_exact_confirmation_converges() -> None:
    service, first = _create()
    second = service.create_from_confirmed_setup(
        make_creation_command(idempotency_key="candidate-create-2", correlation_id=CORRELATION_B)
    )
    third = service.create_from_confirmed_setup(
        make_creation_command(
            assessment=make_assessment(make_evidence_window(), assessment_id=ASSESSMENT_B)
        )
    )
    assert first.candidate_id == second.candidate_id == third.candidate_id
    assert first.content_hash == second.content_hash == third.content_hash
    assert first.state is CandidateState.ACTIVE
    assert service.latest_projection(ORG_ID, first.candidate_id) == first


def test_concurrent_duplicate_creation_converges() -> None:
    repository = InMemoryCandidateRepository()
    service = in_memory_candidate_lifecycle(now=EVALUATED_AT, repository=repository)
    command = make_creation_command()
    start = threading.Barrier(8)

    def worker(_index: int) -> Candidate:
        start.wait()
        return service.create_from_confirmed_setup(command)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))

    identities = {item.candidate_id for item in results}
    hashes = {item.content_hash for item in results}
    assert len(identities) == 1
    assert len(hashes) == 1
    assert all(item.state is CandidateState.ACTIVE for item in results)
    stored = repository.get_by_id(ORG_ID, results[0].candidate_id)
    assert stored is not None
    assert stored.candidate_id == results[0].candidate_id


def test_different_evidence_window_creates_distinct_candidate() -> None:
    service, first = _create()
    adjacent = make_evidence_window(
        interval=interval(
            start=TRIGGER_OPEN + timedelta(minutes=15),
            end=TRIGGER_OPEN + timedelta(minutes=30),
        )
    )
    second = service.create_from_confirmed_setup(make_creation_command(window=adjacent))
    assert first.candidate_id != second.candidate_id
    assert first.evidence_window_hash != second.evidence_window_hash
    assert first.uniqueness_tuple().canonical_hash() != second.uniqueness_tuple().canonical_hash()


def test_different_organization_creates_distinct_candidate() -> None:
    service, first = _create()
    window = make_evidence_window(organization_id=ORG_B)
    second = service.create_from_confirmed_setup(
        make_creation_command(
            window=window,
            assessment=make_assessment(window, organization_id=ORG_B),
        )
    )
    assert first.candidate_id != second.candidate_id
    assert first.organization_id != second.organization_id
    assert service.get_by_candidate_id(ORG_B, first.candidate_id) is None
    assert service.get_by_candidate_id(ORG_ID, second.candidate_id) is None


def test_different_strategy_version_creates_distinct_candidate() -> None:
    service, first = _create()
    window = make_evidence_window(strategy_version_id=STRATEGY_VERSION_B)
    second = service.create_from_confirmed_setup(
        make_creation_command(
            window=window,
            assessment=make_assessment(window, strategy_version_id=STRATEGY_VERSION_B),
        )
    )
    assert first.candidate_id != second.candidate_id
    assert first.strategy_version_id != second.strategy_version_id


@pytest.mark.parametrize(
    "label",
    [
        "compiled_setup",
        "fusion_policy_version",
        "direction",
        "venue",
        "instrument",
        "timeframe",
    ],
)
def test_remaining_uniqueness_dimensions_do_not_converge(label: str) -> None:
    service, first = _create()
    command = _distinct_command(label)
    second = service.create_from_confirmed_setup(command)
    assert first.candidate_id != second.candidate_id
    assert first.uniqueness_tuple().canonical_hash() != second.uniqueness_tuple().canonical_hash()


def _observations_for(
    identity_m15: EvidenceMarketIdentity, identity_h4: EvidenceMarketIdentity
) -> tuple[SelectedPublicObservation, ...]:
    return (
        selected_observation_from_public(
            public_observation(index=0, market_identity=identity_m15),
            role=EvidenceRole.TRIGGER_OHLCV,
        ),
        selected_observation_from_public(
            public_observation(index=1, timeframe=Timeframe.H4, market_identity=identity_h4),
            role=EvidenceRole.CONTEXT_OHLCV,
        ),
        selected_observation_from_public(
            public_observation(index=2, market_identity=identity_m15),
            role=EvidenceRole.CVD_WINDOW,
        ),
    )


def _distinct_command(label: str) -> CandidateCreationCommand:
    if label == "compiled_setup":
        setup = ExecutableSetupRef(
            setup_definition_id=COMPILED_SETUP_B,
            kind=executable_setup().kind,
            content_hash=SETUP_CONTENT_HASH,
        )
        window = make_evidence_window(compiled_setup_definition_id=COMPILED_SETUP_B)
        return make_creation_command(
            window=window,
            setup=setup,
            assessment=make_assessment(window, setup=setup),
        )
    if label == "fusion_policy_version":
        window = make_evidence_window(fusion_policy_version="alt-fusion/v2")
        return make_creation_command(
            window=window,
            assessment=make_assessment(window, fusion_policy_version="alt-fusion/v2"),
        )
    if label == "direction":
        window = make_evidence_window(direction=TradeDirection.LONG)
        return make_creation_command(window=window)
    if label == "venue":
        blofin_m15 = blofin_evidence_identity(Timeframe.M15)
        blofin_h4 = blofin_evidence_identity(Timeframe.H4)
        window = make_evidence_window(
            evidence_identity=blofin_m15,
            selected_public_observations=_observations_for(blofin_m15, blofin_h4),
            source_set=(
                SemanticSourceIdentity(
                    venue=VenueId.BLOFIN,
                    market_type=MarketType.PERPETUAL,
                    source_family=SourceFamily.BINANCE_USDM_FUTURES_PUBLIC,
                ),
            ),
        )
        return make_creation_command(window=window, evidence_identity=blofin_m15)
    if label == "instrument":
        eth_m15 = eth_evidence_identity(Timeframe.M15)
        eth_h4 = eth_evidence_identity(Timeframe.H4)
        identity = first_slice_identity(timeframe=Timeframe.M15, replay=True).model_copy(
            update={"instrument": eth_instrument()}
        )
        window = make_evidence_window(
            evidence_identity=identity,
            selected_public_observations=_observations_for(eth_m15, eth_h4),
        )
        return make_creation_command(window=window, evidence_identity=identity)
    if label == "timeframe":
        identity = first_slice_identity(timeframe=Timeframe.H1, replay=True)
        window = make_evidence_window(evidence_identity=identity)
        return make_creation_command(window=window, evidence_identity=identity)
    raise AssertionError(f"unknown uniqueness dimension {label}")


def test_terminal_transition_cannot_resurrect() -> None:
    service, candidate = _create()
    rejected = _transition(service, candidate.candidate_id, CandidateState.REJECTED)
    assert rejected.state is CandidateState.REJECTED
    with pytest.raises(IllegalCandidateTransitionError, match="resurrected"):
        service.transition(
            organization_id=ORG_ID,
            candidate_id=candidate.candidate_id,
            new_state=CandidateState.ACTIVE,
            reason_codes=(CandidateReasonCode.CONFIRMED_SETUP,),
            idempotency_key="resurrect-active",
            correlation_id=CORRELATION_B,
        )
    with pytest.raises(IllegalCandidateTransitionError, match="resurrected"):
        _transition(
            service,
            candidate.candidate_id,
            CandidateState.PLAN_CREATED,
            idempotency_key="resurrect-plan",
        )
    latest = service.latest_projection(ORG_ID, candidate.candidate_id)
    assert latest is not None
    assert latest.state is CandidateState.REJECTED


@pytest.mark.parametrize("terminal", sorted(_TERMINAL_REASON, key=lambda item: item.value))
def test_terminal_replay_is_idempotent(terminal: CandidateState) -> None:
    service, candidate = _create()
    first = _transition(
        service, candidate.candidate_id, terminal, idempotency_key=f"term-{terminal.value}-1"
    )
    replay = _transition(
        service, candidate.candidate_id, terminal, idempotency_key=f"term-{terminal.value}-2"
    )
    assert first.state is terminal
    assert replay.candidate_id == first.candidate_id
    assert replay.content_hash == first.content_hash
    assert replay.transition_version == 2
    history = service.transition_history(ORG_ID, candidate.candidate_id)
    assert len(history) == 1
    assert history[0].new_state is terminal
    assert history[0].previous_state is CandidateState.ACTIVE
    assert history[0].transition_version == 2


def test_plan_created_lineage() -> None:
    service, candidate = _create()
    planned = _transition(service, candidate.candidate_id, CandidateState.PLAN_CREATED)
    replay = _transition(
        service,
        candidate.candidate_id,
        CandidateState.PLAN_CREATED,
        idempotency_key="plan-replay",
    )
    assert planned.state is CandidateState.PLAN_CREATED
    assert replay.content_hash == planned.content_hash
    assert planned.transition_version == 2
    history = service.transition_history(ORG_ID, candidate.candidate_id)
    assert len(history) == 1
    rejected = _transition(
        service,
        candidate.candidate_id,
        CandidateState.REJECTED,
        idempotency_key="plan-then-reject",
    )
    assert rejected.state is CandidateState.REJECTED
    assert rejected.transition_version == 3
    lineage = service.transition_history(ORG_ID, candidate.candidate_id)
    assert [item.transition_version for item in lineage] == [2, 3]
    assert [item.new_state for item in lineage] == [
        CandidateState.PLAN_CREATED,
        CandidateState.REJECTED,
    ]
    assert lineage[0].content_hash == history[0].content_hash


def test_conflicting_terminal_transition_fails_closed() -> None:
    service, candidate = _create()
    _transition(service, candidate.candidate_id, CandidateState.REJECTED)
    with pytest.raises(ConflictingCandidateTransitionError, match="Conflicting terminal"):
        _transition(
            service,
            candidate.candidate_id,
            CandidateState.SKIPPED,
            idempotency_key="conflict-skip",
        )
    latest = service.latest_projection(ORG_ID, candidate.candidate_id)
    assert latest is not None
    assert latest.state is CandidateState.REJECTED
    assert len(service.transition_history(ORG_ID, candidate.candidate_id)) == 1


@pytest.mark.parametrize(
    "state",
    [
        SetupAssessmentState.NO_SETUP,
        SetupAssessmentState.WATCH,
        SetupAssessmentState.PARTIAL_MATCH,
    ],
)
def test_non_confirmed_assessment_cannot_create_candidate(state: SetupAssessmentState) -> None:
    service = _service()
    window = make_evidence_window()
    previous = None if state is SetupAssessmentState.NO_SETUP else SetupAssessmentState.NO_SETUP
    if state is SetupAssessmentState.WATCH:
        previous = SetupAssessmentState.NO_SETUP
    elif state is SetupAssessmentState.PARTIAL_MATCH:
        previous = SetupAssessmentState.WATCH
    assessment = make_assessment(window, state=state, previous_state=previous)
    with pytest.raises(CandidateCreationAuthorityError, match="cannot create"):
        service.create_from_confirmed_setup(
            make_creation_command(window=window, assessment=assessment)
        )


def test_expired_assessment_cannot_create_active_candidate() -> None:
    service = _service()
    window = make_evidence_window()
    expired_state = make_assessment(
        window,
        state=SetupAssessmentState.EXPIRED,
        previous_state=SetupAssessmentState.CONFIRMED_SETUP,
    )
    with pytest.raises(ExpiredCandidateAssessmentError, match="EXPIRED"):
        service.create_from_confirmed_setup(
            make_creation_command(window=window, assessment=expired_state)
        )
    elapsed = make_assessment(
        window,
        assessed_at=EVALUATED_AT - timedelta(seconds=1),
        valid_until=EVALUATED_AT,
    )
    with pytest.raises(ExpiredCandidateAssessmentError, match="Elapsed"):
        service.create_from_confirmed_setup(
            make_creation_command(window=window, assessment=elapsed)
        )


def test_invalidated_assessment_cannot_create_active_candidate() -> None:
    service = _service()
    window = make_evidence_window()
    assessment = make_assessment(
        window,
        state=SetupAssessmentState.INVALIDATED,
        previous_state=SetupAssessmentState.CONFIRMED_SETUP,
    )
    with pytest.raises(CandidateCreationAuthorityError, match="INVALIDATED"):
        service.create_from_confirmed_setup(
            make_creation_command(window=window, assessment=assessment)
        )


def test_legacy_paper_validation_candidate_cannot_become_authority() -> None:
    service = _service()
    ref = DownstreamPaperValidationCandidateRef(
        paper_validation_candidate_id=uuid4(),
        canonical_candidate_id=uuid4(),
    )
    with pytest.raises(LegacyCandidateAuthorityError, match="downstream"):
        service.create_from_paper_validation_candidate(ref)
    with pytest.raises(LegacyCandidateAuthorityError, match="downstream"):
        service.create_from_paper_validation_candidate(object())
    signature = inspect.signature(service.create_from_confirmed_setup)
    assert "paper_validation" not in signature.parameters
    assert "paper_validation_candidate" not in signature.parameters


def test_tenant_isolation() -> None:
    service, candidate = _create()
    assert service.get_by_candidate_id(ORG_B, candidate.candidate_id) is None
    assert service.latest_projection(ORG_B, candidate.candidate_id) is None
    assert service.transition_history(ORG_B, candidate.candidate_id) == ()
    with pytest.raises(CandidateNotFoundError):
        _transition(service, candidate.candidate_id, CandidateState.REJECTED, organization_id=ORG_B)
    window_b = make_evidence_window(organization_id=ORG_B)
    other = service.create_from_confirmed_setup(
        make_creation_command(
            window=window_b,
            assessment=make_assessment(window_b, organization_id=ORG_B),
        )
    )
    assert other.candidate_id != candidate.candidate_id
    assert service.get_by_uniqueness(candidate.uniqueness_tuple()) == candidate
    assert service.get_by_uniqueness(other.uniqueness_tuple()) == other
    assert service.get_by_candidate_id(ORG_ID, other.candidate_id) is None


def test_append_only_transition_ordering() -> None:
    service, candidate = _create()
    _transition(service, candidate.candidate_id, CandidateState.PLAN_CREATED)
    first_history = service.transition_history(ORG_ID, candidate.candidate_id)
    first_hash = first_history[0].content_hash
    _transition(
        service,
        candidate.candidate_id,
        CandidateState.EXPIRED,
        idempotency_key="expire-after-plan",
    )
    history = service.transition_history(ORG_ID, candidate.candidate_id)
    assert [item.transition_version for item in history] == [2, 3]
    assert history[0].content_hash == first_hash
    assert history[0] == first_history[0]
    assert history[1].previous_state is CandidateState.PLAN_CREATED
    assert history[1].new_state is CandidateState.EXPIRED
    with pytest.raises(ValidationError, match="frozen"):
        history[0].new_state = CandidateState.SKIPPED  # type: ignore[misc]


def test_content_hash_stability() -> None:
    left_service, left = _create()
    _right_service, right = _create()
    assert left.candidate_id == right.candidate_id
    assert left.content_hash == right.content_hash
    assert left.uniqueness_tuple().canonical_hash() == right.uniqueness_tuple().canonical_hash()
    replay = left_service.create_from_confirmed_setup(make_creation_command())
    assert replay.content_hash == left.content_hash
    command = make_creation_command()
    uniqueness = uniqueness_from_confirmed(
        command.assessment, command.evidence_window, command.executable_setup
    )
    assert uniqueness.canonical_hash() == left.uniqueness_tuple().canonical_hash()
    assert uniqueness.canonical_bytes() == left.uniqueness_tuple().canonical_bytes()


def test_in_memory_repository_is_not_a_database() -> None:
    repository = InMemoryCandidateRepository()
    assert not hasattr(repository, "session")
    assert not hasattr(repository, "engine")
    assert "sqlalchemy" not in type(repository).__module__
    service = in_memory_candidate_lifecycle(now=EVALUATED_AT, repository=repository)
    candidate = service.create_from_confirmed_setup(make_creation_command())
    assert repository.get_by_id(ORG_ID, candidate.candidate_id) == candidate


def test_creation_idempotency_key_exact_retry_converges() -> None:
    service = _service()
    first = service.create_from_confirmed_setup(make_creation_command())
    replay = service.create_from_confirmed_setup(make_creation_command())
    assert replay.candidate_id == first.candidate_id
    assert replay.content_hash == first.content_hash
    assert replay.idempotency_key == first.idempotency_key


def test_creation_idempotency_key_conflict_fails_closed() -> None:
    service = _service()
    first = service.create_from_confirmed_setup(make_creation_command())
    adjacent = make_evidence_window(
        interval=interval(
            start=TRIGGER_OPEN + timedelta(minutes=15),
            end=TRIGGER_OPEN + timedelta(minutes=30),
        )
    )
    with pytest.raises(ConflictingCandidateIdempotencyError, match="already bound"):
        service.create_from_confirmed_setup(
            make_creation_command(window=adjacent, idempotency_key="candidate-create-1")
        )
    stored = service.get_by_candidate_id(ORG_ID, first.candidate_id)
    assert stored is not None
    assert stored.content_hash == first.content_hash


def test_concurrent_identical_creation_key_converges() -> None:
    repository = InMemoryCandidateRepository()
    service = in_memory_candidate_lifecycle(now=EVALUATED_AT, repository=repository)
    command = make_creation_command(idempotency_key="candidate-create-shared")
    start = threading.Barrier(8)

    def worker(_index: int) -> Candidate:
        start.wait()
        return service.create_from_confirmed_setup(command)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))

    assert {item.candidate_id for item in results} == {results[0].candidate_id}
    assert {item.content_hash for item in results} == {results[0].content_hash}


def test_concurrent_conflicting_creation_key_first_writer_wins() -> None:
    repository = InMemoryCandidateRepository()
    service = in_memory_candidate_lifecycle(now=EVALUATED_AT, repository=repository)
    baseline = make_creation_command(idempotency_key="candidate-create-conflict")
    adjacent = make_evidence_window(
        interval=interval(
            start=TRIGGER_OPEN + timedelta(minutes=15),
            end=TRIGGER_OPEN + timedelta(minutes=30),
        )
    )
    conflicting = make_creation_command(
        window=adjacent, idempotency_key="candidate-create-conflict"
    )
    start = threading.Barrier(8)
    outcomes: list[Candidate | str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        command = baseline if index % 2 == 0 else conflicting
        start.wait()
        try:
            created = service.create_from_confirmed_setup(command)
        except ConflictingCandidateIdempotencyError:
            with lock:
                outcomes.append("conflict")
            return
        with lock:
            outcomes.append(created)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))

    created = [item for item in outcomes if not isinstance(item, str)]
    conflicts = [item for item in outcomes if item == "conflict"]
    assert created
    assert conflicts
    assert len({item.candidate_id for item in created}) == 1


def test_transition_exact_key_replay_preserves_original_record() -> None:
    service, candidate = _create()
    first = _transition(service, candidate.candidate_id, CandidateState.REJECTED)
    replay = _transition(service, candidate.candidate_id, CandidateState.REJECTED)
    assert replay.content_hash == first.content_hash
    assert replay.transition_version == 2
    history = service.transition_history(ORG_ID, candidate.candidate_id)
    assert len(history) == 1
    assert history[0].idempotency_key == "candidate-transition-1"
    assert history[0].correlation_id == CORRELATION_B


def test_transition_same_key_conflicting_payload_fails_closed() -> None:
    service, candidate = _create()
    first = _transition(service, candidate.candidate_id, CandidateState.REJECTED)
    with pytest.raises(ConflictingCandidateIdempotencyError, match="semantic transition"):
        service.transition(
            organization_id=ORG_ID,
            candidate_id=candidate.candidate_id,
            new_state=CandidateState.REJECTED,
            reason_codes=(CandidateReasonCode.REJECTED,),
            idempotency_key="candidate-transition-1",
            correlation_id=uuid4(),
        )
    latest = service.latest_projection(ORG_ID, candidate.candidate_id)
    assert latest is not None
    assert latest.content_hash == first.content_hash
    assert len(service.transition_history(ORG_ID, candidate.candidate_id)) == 1


def test_transition_different_key_conflicting_payload_fails_closed() -> None:
    service, candidate = _create()
    first = _transition(service, candidate.candidate_id, CandidateState.PLAN_CREATED)
    with pytest.raises(ConflictingCandidateTransitionError, match="already-applied"):
        service.transition(
            organization_id=ORG_ID,
            candidate_id=candidate.candidate_id,
            new_state=CandidateState.PLAN_CREATED,
            reason_codes=(CandidateReasonCode.PLAN_CREATED,),
            idempotency_key="candidate-transition-conflict",
            correlation_id=uuid4(),
        )
    latest = service.latest_projection(ORG_ID, candidate.candidate_id)
    assert latest is not None
    assert latest.content_hash == first.content_hash
    history = service.transition_history(ORG_ID, candidate.candidate_id)
    assert len(history) == 1
    assert history[0].idempotency_key == "candidate-transition-1"


def test_concurrent_conflicting_same_state_first_writer_wins() -> None:
    repository = InMemoryCandidateRepository()
    service = in_memory_candidate_lifecycle(now=EVALUATED_AT, repository=repository)
    candidate = service.create_from_confirmed_setup(make_creation_command())
    start = threading.Barrier(8)
    outcomes: list[Candidate | str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        start.wait()
        try:
            updated = service.transition(
                organization_id=ORG_ID,
                candidate_id=candidate.candidate_id,
                new_state=CandidateState.REJECTED,
                reason_codes=(CandidateReasonCode.REJECTED,),
                idempotency_key=f"reject-key-{index % 2}",
                correlation_id=uuid4(),
            )
        except (ConflictingCandidateIdempotencyError, ConflictingCandidateTransitionError):
            with lock:
                outcomes.append("conflict")
            return
        with lock:
            outcomes.append(updated)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))

    created = [item for item in outcomes if not isinstance(item, str)]
    conflicts = [item for item in outcomes if item == "conflict"]
    assert created
    assert conflicts
    assert {item.content_hash for item in created} == {created[0].content_hash}
    history = service.transition_history(ORG_ID, candidate.candidate_id)
    assert len(history) == 1
    assert history[0].new_state is CandidateState.REJECTED
