"""Watcher → Phase 6 fusion evaluation boundary.

One typed orchestration service. Watcher does not implement trading predicates,
does not compute a second evidence hash, and does not mint candidate identity.
Canonical flow:

    scan evidence → CanonicalEvidenceWindowV1 → evaluate_setup → SetupAssessment
    → Candidate only when CONFIRMED_SETUP, persist mode, and publish is authorized

Setup truth stays independent of balance, portfolio, risk, leverage, execution
availability, and account state. Action eligibility is out of scope.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol, cast
from uuid import UUID

from app.signal_fusion.adapters import AssessmentCommand, evidence_window_from_assessment_command
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.enums import EvidenceAdapterKind, SetupAssessmentState
from app.signal_fusion.errors import (
    CandidateCreationAuthorityError,
    EvidenceIdentityMismatchError,
    EvidenceWindowContractError,
    FormingObservationNotExecutableError,
    SignalFusionContractError,
    TenantAssertionSelectionError,
)
from app.signal_fusion.evaluator import evaluate_setup
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.lifecycle import CandidateCreationCommand, CandidateLifecycleService
from app.signal_fusion.memory import InMemoryCandidateRepository
from app.signal_fusion.policy import FusionPolicy
from app.signal_fusion.ports import CandidateRepository
from app.watcher.contracts import (
    EvaluationCommand,
    EvaluationMode,
    EvaluationOutcome,
    EvaluationStatus,
    FrozenModel,
    UnitAttempt,
    UnitAttemptKind,
    UnitAttemptStatus,
)
from app.watcher.errors import StaleFenceError, WatcherTenantMismatchError


class BoundEvaluationClock:
    """Clock bound to the current scan's ``evaluated_at``. Not wall time."""

    def __init__(self) -> None:
        self._now: datetime | None = None

    def bind(self, moment: datetime) -> None:
        self._now = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)

    def now(self) -> datetime:
        if self._now is None:
            raise RuntimeError("Watcher fusion evaluation clock is unbound.")
        return self._now


class WatcherCanonicalScanEvidence(FrozenModel):
    """Canonical first-slice inputs for one tenant-scoped scan.

    Watcher orchestration must not invent hashes or candidate IDs from this
    payload. ``CanonicalEvidenceWindowV1`` remains the sole evidence identity.
    """

    organization_id: UUID
    policy: FusionPolicy
    assessment_command: AssessmentCommand
    evidence: FirstSliceEvidenceBundle
    evaluated_at: datetime
    previous_assessment: SetupAssessment | None = None


class WatcherScanEvidencePort(Protocol):
    """Loads already-normalized first-slice evidence. Does not evaluate setup."""

    def load(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None: ...


class CandidatePersistenceFence(Protocol):
    """Binds worker lease identity around CandidateLifecycleService writes."""

    def bind_from_evaluation_command(
        self, command: EvaluationCommand
    ) -> AbstractContextManager[None]: ...


class InMemoryWatcherScanEvidence:
    """Tenant-scoped in-memory evidence map. Compatible with any WatcherStore."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_scope: dict[tuple[UUID, str], WatcherCanonicalScanEvidence] = {}

    def bind(self, snapshot: WatcherCanonicalScanEvidence, *, scan_scope: str) -> None:
        key = (snapshot.organization_id, scan_scope)
        with self._lock:
            self._by_scope[key] = snapshot

    def load(self, command: EvaluationCommand) -> WatcherCanonicalScanEvidence | None:
        key = (command.request.organization_id, command.request.scan_scope)
        with self._lock:
            snapshot = self._by_scope.get(key)
        if snapshot is None:
            return None
        if snapshot.organization_id != command.request.organization_id:
            raise WatcherTenantMismatchError(
                "Canonical scan evidence belongs to a different organization."
            )
        return snapshot


@dataclass(frozen=True, slots=True)
class _PreparedScan:
    """Canonical assessor output. Does not persist Candidate state."""

    snapshot: WatcherCanonicalScanEvidence
    bound_command: AssessmentCommand
    window: CanonicalEvidenceWindowV1 | None
    assessment: SetupAssessment


class WatcherFusionEvaluationService:
    """Shared manual/worker evaluation boundary for the first-slice strategy."""

    def __init__(
        self,
        *,
        evidence: WatcherScanEvidencePort,
        lifecycle: CandidateLifecycleService,
        clock: BoundEvaluationClock,
        persistence_fence: CandidatePersistenceFence | None = None,
    ) -> None:
        self._evidence = evidence
        self._lifecycle = lifecycle
        self._clock = clock
        self._persistence_fence = persistence_fence
        self._published_candidate_ids: list[UUID] = []

    @property
    def lifecycle(self) -> CandidateLifecycleService:
        return self._lifecycle

    @property
    def published_candidate_ids(self) -> tuple[UUID, ...]:
        return tuple(self._published_candidate_ids)

    def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
        """Evaluate setup truth only. Candidate persistence is fence-gated."""

        if command.mode is EvaluationMode.PERSIST_AND_NOTIFY:
            return _outcome(
                command,
                status=EvaluationStatus.BLOCKED,
                reason_code="notify_disabled",
                failed_units=0,
            )
        prepared = self._prepare(command)
        if isinstance(prepared, EvaluationOutcome):
            return prepared
        return self._assessment_outcome(command, prepared)

    def persist_confirmed_setup(
        self,
        command: EvaluationCommand,
        outcome: EvaluationOutcome,
    ) -> EvaluationOutcome:
        """Persist one canonical Candidate after orchestration authorizes publish.

        ``evaluate`` never inserts Candidate state. A stale worker that loses its
        fence before this method runs cannot mint Candidate authority.
        """

        if command.mode is EvaluationMode.PERSIST_AND_NOTIFY:
            return _outcome(
                command,
                status=EvaluationStatus.BLOCKED,
                reason_code="notify_disabled",
                failed_units=0,
            )
        if command.mode is not EvaluationMode.PERSIST_EVIDENCE:
            return outcome.model_copy(update={"candidate_ids": ()})
        if outcome.status is not EvaluationStatus.SUCCEEDED:
            return outcome.model_copy(update={"candidate_ids": ()})
        if outcome.reason_code != SetupAssessmentState.CONFIRMED_SETUP.value:
            return outcome.model_copy(update={"candidate_ids": ()})
        if outcome.error or outcome.failed_units > 0:
            return outcome.model_copy(update={"candidate_ids": ()})

        prepared = self._prepare(command)
        if isinstance(prepared, EvaluationOutcome):
            return prepared
        if (
            prepared.assessment.state is not SetupAssessmentState.CONFIRMED_SETUP
            or prepared.assessment.evidence_window_hash != outcome.evidence_validity_token
        ):
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="candidate_creation_failed",
                failed_units=1,
                error="confirmed setup did not recompute identically for persist",
                evidence_validity_token=prepared.assessment.evidence_window_hash,
                unit_reason=prepared.assessment.state.value,
            )
        try:
            candidate_ids = self._maybe_create_candidate(
                command=command,
                bound_command=prepared.bound_command,
                assessment=prepared.assessment,
                window=prepared.window,
            )
        except StaleFenceError:
            raise
        except SignalFusionContractError as exc:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="candidate_creation_failed",
                failed_units=1,
                error=str(exc),
                evidence_validity_token=prepared.assessment.evidence_window_hash,
                unit_reason=prepared.assessment.state.value,
            )
        except Exception as exc:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="candidate_creation_failed",
                failed_units=1,
                error=str(exc),
                evidence_validity_token=prepared.assessment.evidence_window_hash,
                unit_reason=prepared.assessment.state.value,
            )
        return self._assessment_outcome(command, prepared, candidate_ids=candidate_ids)

    def _prepare(self, command: EvaluationCommand) -> EvaluationOutcome | _PreparedScan:
        try:
            snapshot = self._evidence.load(command)
        except WatcherTenantMismatchError as exc:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="organization_mismatch",
                failed_units=1,
                error=str(exc),
            )
        except Exception as exc:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="canonical_evidence_unavailable",
                failed_units=1,
                error=str(exc),
            )
        if snapshot is None:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="missing_canonical_evidence",
                failed_units=1,
                error="canonical first-slice evidence is required",
            )
        if snapshot.organization_id != command.request.organization_id:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="organization_mismatch",
                failed_units=1,
                error="scan organization_id does not match canonical evidence",
            )
        if snapshot.assessment_command.organization_id != command.request.organization_id:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="organization_mismatch",
                failed_units=1,
                error="assessment command organization_id does not match the scan",
            )
        if snapshot.policy.organization_id != command.request.organization_id:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="organization_mismatch",
                failed_units=1,
                error="fusion policy organization_id does not match the scan",
            )

        self._clock.bind(snapshot.evaluated_at)
        bound_command = snapshot.assessment_command.model_copy(
            update={
                "adapter_kind": EvidenceAdapterKind.WATCHER,
                "scan_id": command.lineage_id or command.command_id,
                "correlation_id": command.correlation_id,
            }
        )
        window = _canonical_window(bound_command)
        try:
            assessment = evaluate_setup(
                policy=snapshot.policy,
                command=bound_command,
                evidence=snapshot.evidence,
                evaluated_at=snapshot.evaluated_at,
                previous_assessment=snapshot.previous_assessment,
                account_context=None,
            )
        except Exception as exc:
            return _outcome(
                command,
                status=EvaluationStatus.FAILED,
                reason_code="evaluation_exception",
                failed_units=1,
                error=str(exc),
            )
        return _PreparedScan(
            snapshot=snapshot,
            bound_command=bound_command,
            window=window,
            assessment=assessment,
        )

    def _assessment_outcome(
        self,
        command: EvaluationCommand,
        prepared: _PreparedScan,
        *,
        candidate_ids: tuple[UUID, ...] = (),
    ) -> EvaluationOutcome:
        return _outcome(
            command,
            status=EvaluationStatus.SUCCEEDED,
            reason_code=prepared.assessment.state.value,
            failed_units=0,
            evidence_validity_token=prepared.assessment.evidence_window_hash,
            candidate_ids=candidate_ids,
            unit_reason=prepared.assessment.state.value,
        )

    def _maybe_create_candidate(
        self,
        *,
        command: EvaluationCommand,
        bound_command: AssessmentCommand,
        assessment: SetupAssessment,
        window: CanonicalEvidenceWindowV1 | None,
    ) -> tuple[UUID, ...]:
        if assessment.state is not SetupAssessmentState.CONFIRMED_SETUP:
            return ()
        if command.mode is not EvaluationMode.PERSIST_EVIDENCE:
            return ()
        if window is None:
            raise CandidateCreationAuthorityError(
                "CONFIRMED_SETUP cannot persist without CanonicalEvidenceWindowV1."
            )
        with _persistence_fence_context(self._persistence_fence, command):
            created = self._lifecycle.create_from_confirmed_setup(
                CandidateCreationCommand(
                    assessment=assessment,
                    evidence_window=window,
                    executable_setup=bound_command.executable_setup,
                    evidence_identity=bound_command.evidence_identity,
                    idempotency_key=f"watcher:{assessment.evidence_window_hash}",
                    correlation_id=assessment.correlation_id,
                )
            )
        self._published_candidate_ids.append(created.candidate_id)
        return (created.candidate_id,)


def build_fusion_evaluation_service(
    *,
    evidence: WatcherScanEvidencePort,
    repository: CandidateRepository | None = None,
    lifecycle: CandidateLifecycleService | None = None,
    clock: BoundEvaluationClock | None = None,
    persistence_fence: CandidatePersistenceFence | None = None,
) -> WatcherFusionEvaluationService:
    """Compose the fusion evaluation boundary with in-memory candidate authority."""

    bound_clock = clock if clock is not None else BoundEvaluationClock()
    resolved_repository = repository
    if lifecycle is None:
        resolved_repository = repository or InMemoryCandidateRepository()
        lifecycle = CandidateLifecycleService(
            repository=resolved_repository,
            clock=bound_clock,
        )
    resolved_fence = persistence_fence
    if resolved_fence is None:
        resolved_fence = _candidate_persistence_fence(resolved_repository)
    return WatcherFusionEvaluationService(
        evidence=evidence,
        lifecycle=lifecycle,
        clock=bound_clock,
        persistence_fence=resolved_fence,
    )


def _candidate_persistence_fence(
    repository: CandidateRepository | None,
) -> CandidatePersistenceFence | None:
    if repository is None:
        return None
    bind = getattr(repository, "bind_from_evaluation_command", None)
    if callable(bind):
        return cast(CandidatePersistenceFence, repository)
    return None


def _persistence_fence_context(
    fence: CandidatePersistenceFence | None, command: EvaluationCommand
) -> AbstractContextManager[None]:
    if fence is None:
        return nullcontext()
    return fence.bind_from_evaluation_command(command)


def _canonical_window(command: AssessmentCommand) -> CanonicalEvidenceWindowV1 | None:
    try:
        return evidence_window_from_assessment_command(command)
    except (
        EvidenceIdentityMismatchError,
        FormingObservationNotExecutableError,
        EvidenceWindowContractError,
        TenantAssertionSelectionError,
        SignalFusionContractError,
        ValueError,
    ):
        return None


def _outcome(
    command: EvaluationCommand,
    *,
    status: EvaluationStatus,
    reason_code: str,
    failed_units: int,
    error: str | None = None,
    evidence_validity_token: str | None = None,
    candidate_ids: tuple[UUID, ...] = (),
    unit_reason: str | None = None,
) -> EvaluationOutcome:
    subjects = command.request.watchlist_item_ids or (command.command_id,)
    unit_status = UnitAttemptStatus.SUCCEEDED
    if status is EvaluationStatus.FAILED:
        unit_status = UnitAttemptStatus.FAILED
    if status is EvaluationStatus.BLOCKED:
        unit_status = UnitAttemptStatus.SKIPPED
    units = tuple(
        UnitAttempt(
            kind=UnitAttemptKind.SUBSCRIPTION_EVALUATION,
            subject_id=subject_id,
            status=unit_status,
            reason_code=unit_reason or reason_code,
            evidence_validity_token=evidence_validity_token,
            error=error,
        )
        for subject_id in subjects
    )
    return EvaluationOutcome(
        command_id=command.command_id,
        request_hash=command.request_hash,
        evaluation_input_hash=command.evaluation_input_hash,
        status=status,
        reason_code=reason_code,
        evaluated_units=len(units),
        failed_units=failed_units,
        unit_attempts=units,
        evidence_validity_token=evidence_validity_token,
        error=error,
        candidate_ids=candidate_ids,
    )


__all__ = [
    "BoundEvaluationClock",
    "CandidatePersistenceFence",
    "InMemoryWatcherScanEvidence",
    "WatcherCanonicalScanEvidence",
    "WatcherFusionEvaluationService",
    "WatcherScanEvidencePort",
    "build_fusion_evaluation_service",
]
