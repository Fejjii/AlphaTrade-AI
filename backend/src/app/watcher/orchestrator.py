"""Watcher orchestration: scheduling, fencing, lineage, and shared evaluation.

Manual and worker callers share :meth:`WatcherOrchestrator.evaluate`. Worker
retries are idempotent. Stale fence holders cannot publish. Failures never
become successful scans. Source freshness / evidence validity are opaque tokens
only — Agent 1 owns those semantics.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol, cast
from uuid import UUID, uuid4

from app.guardrails.redaction import redact_text
from app.watcher.contracts import (
    EvaluationCommand,
    EvaluationMode,
    EvaluationOutcome,
    EvaluationResult,
    EvaluationStatus,
    RecoveryDisposition,
    ScanAttempt,
    ScanAttemptStatus,
    ScanLineage,
    ScanRequest,
    ScanTrigger,
    ScheduledScan,
    ScheduleResult,
    ScheduleStatus,
    SourceFetchAttempt,
    SubscriptionEvaluationAttempt,
    UnitAttemptKind,
    UnitAttemptStatus,
    WatcherHealthSnapshot,
    WatcherRuntimeConfig,
    WorkerCycleResult,
    WorkerCycleStatus,
)
from app.watcher.errors import SimulatedWorkerCrashError, WatcherIdempotencyConflictError
from app.watcher.hashing import evaluation_input_hash, scan_request_hash
from app.watcher.health import project_health
from app.watcher.observability import emit
from app.watcher.ports import (
    Clock,
    CrashBarrier,
    NoCrashBarrier,
    SideEffectPorts,
    WatcherEvaluationBoundary,
    WatcherStore,
)

_TERMINAL_SUCCESS = ScanAttemptStatus.SUCCEEDED
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_CONFIRMED_SETUP = "confirmed_setup"


class _ConfirmedSetupPersist(Protocol):
    """Optional fusion persist hook. Foundation evaluators do not implement it."""

    def persist_confirmed_setup(
        self, command: EvaluationCommand, outcome: EvaluationOutcome
    ) -> EvaluationOutcome: ...


class WatcherOrchestrator:
    """Isolated watcher worker/manual evaluation orchestrator."""

    def __init__(
        self,
        *,
        store: WatcherStore,
        evaluator: WatcherEvaluationBoundary,
        clock: Clock,
        config: WatcherRuntimeConfig,
        side_effects: SideEffectPorts,
        crash: CrashBarrier | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._store = store
        self._evaluator = evaluator
        self._clock = clock
        self._config = config
        self._side_effects = side_effects
        self._crash = crash if crash is not None else NoCrashBarrier()
        self._id_factory = id_factory or uuid4
        self._held_fencing_tokens: dict[tuple[UUID, str, str], int] = {}

    @property
    def store(self) -> WatcherStore:
        return self._store

    @property
    def side_effects(self) -> SideEffectPorts:
        return self._side_effects

    @property
    def evaluator(self) -> WatcherEvaluationBoundary:
        return self._evaluator

    def health(self, organization_id: UUID, scan_scope: str) -> WatcherHealthSnapshot:
        now = self._clock.now()
        snapshot = project_health(
            organization_id=organization_id,
            scan_scope=scan_scope,
            config=self._config,
            now=now,
            lease=self._store.get_lease(organization_id, scan_scope),
            heartbeat=self._store.get_heartbeat(organization_id, scan_scope),
            latest_attempt=self._store.latest_attempt_for_scope(organization_id, scan_scope),
        )
        self._store.remember_health(snapshot)
        return snapshot

    def schedule(self, request: ScanRequest) -> ScheduleResult:
        request_hash = scan_request_hash(request)
        if not self._config.enabled:
            emit(
                self._store,
                name="watcher_schedule_blocked",
                at=self._clock.now(),
                organization_id=request.organization_id,
                scan_scope=request.scan_scope,
                reason_code="watcher_disabled",
            )
            return ScheduleResult(
                status=ScheduleStatus.BLOCKED,
                replayed=False,
                scheduled_scan_id=None,
                lineage_id=None,
                request_hash=request_hash,
                reason_code="watcher_disabled",
            )

        existing = self._store.get_schedule(
            request.organization_id, request.principal_id, request.idempotency_key
        )
        if existing is not None:
            if existing.request_hash != request_hash:
                raise WatcherIdempotencyConflictError(
                    "Idempotency key is bound to a different scan request.",
                    details={
                        "existing_request_hash": existing.request_hash,
                        "incoming_request_hash": request_hash,
                    },
                )
            emit(
                self._store,
                name="watcher_schedule_replayed",
                at=self._clock.now(),
                lineage_id=existing.lineage_id,
                organization_id=request.organization_id,
                scan_scope=request.scan_scope,
                reason_code="duplicate_scheduled_scan",
            )
            return ScheduleResult(
                status=ScheduleStatus.REPLAYED,
                replayed=True,
                scheduled_scan_id=existing.scheduled_scan_id,
                lineage_id=existing.lineage_id,
                request_hash=existing.request_hash,
                reason_code="duplicate_scheduled_scan",
            )

        now = self._clock.now()
        lineage = ScanLineage(
            lineage_id=self._id_factory(),
            organization_id=request.organization_id,
            principal_id=request.principal_id,
            scan_scope=request.scan_scope,
            request_hash=request_hash,
            policy_id=request.policy_id,
            policy_version=request.policy_version,
            policy_content_hash=request.policy_content_hash,
            trigger_created_by=ScanTrigger.WORKER
            if request.principal_id is None
            else ScanTrigger.MANUAL,
            created_at=now,
        )
        self._store.insert_lineage(lineage)
        scheduled = ScheduledScan(
            scheduled_scan_id=self._id_factory(),
            organization_id=request.organization_id,
            principal_id=request.principal_id,
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            scan_scope=request.scan_scope,
            lineage_id=lineage.lineage_id,
            created_at=now,
        )
        stored = self._store.insert_schedule(scheduled)
        self._crash.checkpoint("after_schedule")
        emit(
            self._store,
            name="watcher_scan_scheduled",
            at=now,
            lineage_id=stored.lineage_id,
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            reason_code="accepted",
        )
        return ScheduleResult(
            status=ScheduleStatus.ACCEPTED,
            replayed=stored.scheduled_scan_id != scheduled.scheduled_scan_id,
            scheduled_scan_id=stored.scheduled_scan_id,
            lineage_id=stored.lineage_id,
            request_hash=stored.request_hash,
            reason_code="accepted",
        )

    def evaluate_manual(
        self,
        request: ScanRequest,
        *,
        mode: EvaluationMode = EvaluationMode.PREVIEW,
    ) -> EvaluationResult:
        request_hash = scan_request_hash(request)
        input_hash = evaluation_input_hash(request)
        command = EvaluationCommand(
            command_id=self._id_factory(),
            request=request,
            request_hash=request_hash,
            evaluation_input_hash=input_hash,
            mode=mode,
            trigger=ScanTrigger.MANUAL,
            correlation_id=self._id_factory(),
        )
        if not self._config.enabled:
            outcome = self._blocked_outcome(command, reason_code="watcher_disabled")
            return EvaluationResult(
                outcome=outcome,
                persisted=False,
                replayed=False,
                lineage_id=None,
                attempt_id=None,
                evaluation_input_hash=input_hash,
                reason_code="watcher_disabled",
            )
        if mode is EvaluationMode.PERSIST_AND_NOTIFY:
            outcome = self._blocked_outcome(command, reason_code="notify_disabled")
            emit(
                self._store,
                name="watcher_notify_blocked",
                at=self._clock.now(),
                organization_id=request.organization_id,
                scan_scope=request.scan_scope,
                reason_code="notify_disabled",
            )
            return EvaluationResult(
                outcome=outcome,
                persisted=False,
                replayed=False,
                lineage_id=None,
                attempt_id=None,
                evaluation_input_hash=input_hash,
                reason_code="notify_disabled",
            )

        outcome = self.evaluate(command)
        if mode is EvaluationMode.PREVIEW:
            return EvaluationResult(
                outcome=outcome,
                persisted=False,
                replayed=False,
                lineage_id=None,
                attempt_id=None,
                evaluation_input_hash=input_hash,
                reason_code=outcome.reason_code,
            )

        scheduled = self.schedule(request)
        if scheduled.lineage_id is None:
            return EvaluationResult(
                outcome=outcome,
                persisted=False,
                replayed=False,
                lineage_id=None,
                attempt_id=None,
                evaluation_input_hash=input_hash,
                reason_code=scheduled.reason_code,
            )
        lineage = self._store.get_lineage(scheduled.lineage_id, request.organization_id)
        assert lineage is not None
        replay = self._replay_if_succeeded(lineage)
        if replay is not None:
            return EvaluationResult(
                outcome=replay[1],
                persisted=True,
                replayed=True,
                lineage_id=lineage.lineage_id,
                attempt_id=replay[0].attempt_id,
                evaluation_input_hash=input_hash,
                reason_code="replay",
            )
        attempt = self._open_attempt(
            lineage=lineage,
            trigger=ScanTrigger.MANUAL,
            mode=mode,
            worker_id=None,
            lease_epoch=None,
            fencing_token=None,
            evaluation_input_hash=input_hash,
        )
        outcome = self._persist_canonical_candidate(command, outcome)
        published = self._publish(
            attempt=attempt,
            lineage=lineage,
            outcome=outcome,
            owner_id=None,
            scan_scope=request.scan_scope,
            require_fence=False,
        )
        return EvaluationResult(
            outcome=published[1] if published[0] else outcome,
            persisted=published[0],
            replayed=False,
            lineage_id=lineage.lineage_id,
            attempt_id=attempt.attempt_id,
            evaluation_input_hash=input_hash,
            reason_code=outcome.reason_code,
        )

    def run_worker(
        self,
        request: ScanRequest,
        *,
        worker_id: str,
        held_fencing_token: int | None = None,
    ) -> WorkerCycleResult:
        now = self._clock.now()
        if not self._config.enabled:
            health = self.health(request.organization_id, request.scan_scope)
            emit(
                self._store,
                name="watcher_worker_blocked",
                at=now,
                organization_id=request.organization_id,
                scan_scope=request.scan_scope,
                reason_code="watcher_disabled",
            )
            return WorkerCycleResult(
                status=WorkerCycleStatus.BLOCKED,
                replayed=False,
                lineage_id=None,
                attempt_id=None,
                request_hash=scan_request_hash(request),
                fencing_token=None,
                lease_epoch=None,
                outcome=None,
                health=health,
                reason_code="watcher_disabled",
                published=False,
            )

        scheduled = self.schedule(request)
        self._crash.checkpoint("after_schedule")
        fence_key = (request.organization_id, request.scan_scope, worker_id)
        presented_token = held_fencing_token
        if presented_token is None:
            presented_token = self._held_fencing_tokens.get(fence_key)
        acquired, lease, claim_reason = self._store.claim_lease(
            scan_scope=request.scan_scope,
            organization_id=request.organization_id,
            owner_id=worker_id,
            ttl_seconds=self._config.lease_ttl_seconds,
            now=self._clock.now(),
            fencing_token=presented_token,
        )
        if acquired:
            self._held_fencing_tokens[fence_key] = lease.fencing_token
        if not acquired:
            emit(
                self._store,
                name="watcher_lease_rejected",
                at=self._clock.now(),
                organization_id=request.organization_id,
                scan_scope=request.scan_scope,
                fencing_token=lease.fencing_token,
                reason_code=claim_reason,
                lease_owner=lease.owner_id,
            )
            health = self.health(request.organization_id, request.scan_scope)
            return WorkerCycleResult(
                status=WorkerCycleStatus.SKIPPED,
                replayed=False,
                lineage_id=scheduled.lineage_id,
                attempt_id=None,
                request_hash=scheduled.request_hash,
                fencing_token=None,
                lease_epoch=None,
                outcome=None,
                health=health,
                reason_code=claim_reason,
                published=False,
            )

        emit(
            self._store,
            name="watcher_lease_claimed",
            at=self._clock.now(),
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            fencing_token=lease.fencing_token,
            reason_code=claim_reason,
            lease_epoch=lease.lease_epoch,
            worker_id=worker_id,
        )
        self._store.record_heartbeat(
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            owner_id=worker_id,
            lease_epoch=lease.lease_epoch,
            fencing_token=lease.fencing_token,
            now=self._clock.now(),
            detail="lease_claimed",
        )
        self._crash.checkpoint("after_lease_claim")

        assert scheduled.lineage_id is not None
        lineage = self._store.get_lineage(scheduled.lineage_id, request.organization_id)
        assert lineage is not None
        replay = self._replay_if_succeeded(lineage)
        if replay is not None:
            health = self.health(request.organization_id, request.scan_scope)
            return WorkerCycleResult(
                status=WorkerCycleStatus.SUCCEEDED,
                replayed=True,
                lineage_id=lineage.lineage_id,
                attempt_id=replay[0].attempt_id,
                request_hash=lineage.request_hash,
                fencing_token=lease.fencing_token,
                lease_epoch=lease.lease_epoch,
                outcome=replay[1],
                health=health,
                reason_code="replay",
                published=False,
            )

        attempt = self._resume_or_open_worker_attempt(
            lineage=lineage,
            worker_id=worker_id,
            lease_epoch=lease.lease_epoch,
            fencing_token=lease.fencing_token,
            evaluation_input_hash=evaluation_input_hash(request),
        )
        self._crash.checkpoint("after_scan_attempt")
        emit(
            self._store,
            name="watcher_scan_attempt_started",
            at=self._clock.now(),
            lineage_id=lineage.lineage_id,
            attempt_id=attempt.attempt_id,
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            fencing_token=lease.fencing_token,
            attempt_number=attempt.attempt_number,
        )

        command = EvaluationCommand(
            command_id=self._id_factory(),
            request=request,
            request_hash=lineage.request_hash,
            evaluation_input_hash=evaluation_input_hash(request),
            mode=EvaluationMode.PERSIST_EVIDENCE,
            trigger=ScanTrigger.WORKER,
            lineage_id=lineage.lineage_id,
            attempt_id=attempt.attempt_id,
            lease_epoch=lease.lease_epoch,
            fencing_token=lease.fencing_token,
            worker_id=worker_id,
            correlation_id=self._id_factory(),
        )
        try:
            outcome = self.evaluate(command)
        except SimulatedWorkerCrashError:
            raise
        except Exception as exc:
            outcome = EvaluationOutcome(
                command_id=command.command_id,
                request_hash=command.request_hash,
                evaluation_input_hash=command.evaluation_input_hash,
                status=EvaluationStatus.FAILED,
                reason_code="evaluation_exception",
                error=_sanitize(str(exc)),
                candidate_ids=(),
            )
        self._crash.checkpoint("after_evaluation")

        if not self._store.renew_lease(
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            owner_id=worker_id,
            fencing_token=lease.fencing_token,
            ttl_seconds=self._config.lease_ttl_seconds,
            now=self._clock.now(),
        ):
            return self._reject_stale(
                attempt=attempt,
                lineage=lineage,
                request=request,
                worker_id=worker_id,
                fencing_token=lease.fencing_token,
                reason_code="lease_renewal_lost",
            )

        if not self._store.fence_is_active(
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            owner_id=worker_id,
            fencing_token=lease.fencing_token,
            now=self._clock.now(),
        ):
            return self._reject_stale(
                attempt=attempt,
                lineage=lineage,
                request=request,
                worker_id=worker_id,
                fencing_token=lease.fencing_token,
                reason_code="stale_fence",
            )

        self._persist_unit_attempts(attempt, lineage, outcome)
        self._crash.checkpoint("after_child_attempts")

        if not self._store.fence_is_active(
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            owner_id=worker_id,
            fencing_token=lease.fencing_token,
            now=self._clock.now(),
        ):
            return self._reject_stale(
                attempt=attempt,
                lineage=lineage,
                request=request,
                worker_id=worker_id,
                fencing_token=lease.fencing_token,
                reason_code="stale_fence",
            )

        try:
            outcome = self._persist_canonical_candidate(command, outcome)
        except SimulatedWorkerCrashError:
            raise
        except Exception as exc:
            outcome = EvaluationOutcome(
                command_id=command.command_id,
                request_hash=command.request_hash,
                evaluation_input_hash=command.evaluation_input_hash,
                status=EvaluationStatus.FAILED,
                reason_code="candidate_creation_failed",
                error=_sanitize(str(exc)),
                candidate_ids=(),
            )

        if not self._store.fence_is_active(
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            owner_id=worker_id,
            fencing_token=lease.fencing_token,
            now=self._clock.now(),
        ):
            return self._reject_stale(
                attempt=attempt,
                lineage=lineage,
                request=request,
                worker_id=worker_id,
                fencing_token=lease.fencing_token,
                reason_code="stale_fence",
            )

        published, final_outcome = self._publish(
            attempt=attempt,
            lineage=lineage,
            outcome=outcome,
            owner_id=worker_id,
            scan_scope=request.scan_scope,
            require_fence=True,
            fencing_token=lease.fencing_token,
        )
        self._crash.checkpoint("after_publish")
        self._store.record_heartbeat(
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            owner_id=worker_id,
            lease_epoch=lease.lease_epoch,
            fencing_token=lease.fencing_token,
            now=self._clock.now(),
            detail=final_outcome.status.value,
        )
        health = self.health(request.organization_id, request.scan_scope)
        status = _cycle_status(final_outcome.status, published)
        emit(
            self._store,
            name="watcher_scan_finished",
            at=self._clock.now(),
            lineage_id=lineage.lineage_id,
            attempt_id=attempt.attempt_id,
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            fencing_token=lease.fencing_token,
            reason_code=final_outcome.reason_code,
            published=published,
            evaluation_status=final_outcome.status.value,
        )
        return WorkerCycleResult(
            status=status,
            replayed=False,
            lineage_id=lineage.lineage_id,
            attempt_id=attempt.attempt_id,
            request_hash=lineage.request_hash,
            fencing_token=lease.fencing_token,
            lease_epoch=lease.lease_epoch,
            outcome=final_outcome,
            health=health,
            reason_code=final_outcome.reason_code,
            published=published,
        )

    def evaluate(self, command: EvaluationCommand) -> EvaluationOutcome:
        """Shared evaluation boundary used by manual and worker callers."""

        if command.mode is EvaluationMode.PERSIST_AND_NOTIFY:
            return self._blocked_outcome(command, reason_code="notify_disabled")
        raw = self._evaluator.evaluate(command)
        return _honest_outcome(raw)

    def _persist_canonical_candidate(
        self, command: EvaluationCommand, outcome: EvaluationOutcome
    ) -> EvaluationOutcome:
        persist = getattr(self._evaluator, "persist_confirmed_setup", None)
        if not callable(persist):
            return outcome
        boundary = cast(_ConfirmedSetupPersist, self._evaluator)
        return _honest_outcome(boundary.persist_confirmed_setup(command, outcome))

    def _blocked_outcome(
        self, command: EvaluationCommand, *, reason_code: str
    ) -> EvaluationOutcome:
        return EvaluationOutcome(
            command_id=command.command_id,
            request_hash=command.request_hash,
            evaluation_input_hash=command.evaluation_input_hash,
            status=EvaluationStatus.BLOCKED,
            reason_code=reason_code,
            candidate_ids=(),
        )

    def _replay_if_succeeded(
        self, lineage: ScanLineage
    ) -> tuple[ScanAttempt, EvaluationOutcome] | None:
        if lineage.terminal_status is not _TERMINAL_SUCCESS or lineage.terminal_attempt_id is None:
            return None
        attempt = self._store.get_attempt(lineage.terminal_attempt_id)
        if attempt is None or attempt.status is not ScanAttemptStatus.SUCCEEDED:
            return None
        outcome = EvaluationOutcome(
            command_id=attempt.attempt_id,
            request_hash=lineage.request_hash,
            evaluation_input_hash=attempt.evaluation_input_hash or lineage.request_hash,
            status=EvaluationStatus.SUCCEEDED,
            reason_code=attempt.outcome_reason_code or "replay",
            candidate_ids=(),
        )
        emit(
            self._store,
            name="watcher_scan_replayed",
            at=self._clock.now(),
            lineage_id=lineage.lineage_id,
            attempt_id=attempt.attempt_id,
            organization_id=lineage.organization_id,
            scan_scope=lineage.scan_scope,
            reason_code="replay",
        )
        return attempt, outcome

    def _resume_or_open_worker_attempt(
        self,
        *,
        lineage: ScanLineage,
        worker_id: str,
        lease_epoch: int,
        fencing_token: int,
        evaluation_input_hash: str,
    ) -> ScanAttempt:
        attempts = self._store.list_attempts(lineage.lineage_id)
        if attempts:
            latest = attempts[-1]
            if (
                latest.status is ScanAttemptStatus.STARTED
                and latest.fencing_token == fencing_token
                and latest.worker_id == worker_id
            ):
                heartbeat = latest.model_copy(update={"heartbeat_at": self._clock.now()})
                return self._store.update_attempt(heartbeat)
        recovered_from = attempts[-1].attempt_id if attempts else None
        disposition = (
            RecoveryDisposition.RETRY if recovered_from is not None else RecoveryDisposition.NONE
        )
        return self._open_attempt(
            lineage=lineage,
            trigger=ScanTrigger.WORKER,
            mode=EvaluationMode.PERSIST_EVIDENCE,
            worker_id=worker_id,
            lease_epoch=lease_epoch,
            fencing_token=fencing_token,
            evaluation_input_hash=evaluation_input_hash,
            recovered_from_attempt_id=recovered_from,
            recovery_disposition=disposition,
        )

    def _open_attempt(
        self,
        *,
        lineage: ScanLineage,
        trigger: ScanTrigger,
        mode: EvaluationMode,
        worker_id: str | None,
        lease_epoch: int | None,
        fencing_token: int | None,
        evaluation_input_hash: str,
        recovered_from_attempt_id: UUID | None = None,
        recovery_disposition: RecoveryDisposition = RecoveryDisposition.NONE,
    ) -> ScanAttempt:
        now = self._clock.now()
        attempt_number = len(self._store.list_attempts(lineage.lineage_id)) + 1
        attempt = ScanAttempt(
            attempt_id=self._id_factory(),
            lineage_id=lineage.lineage_id,
            attempt_number=attempt_number,
            worker_id=worker_id,
            lease_epoch=lease_epoch,
            fencing_token=fencing_token,
            trigger=trigger,
            mode=mode,
            status=ScanAttemptStatus.STARTED,
            started_at=now,
            heartbeat_at=now,
            evaluation_input_hash=evaluation_input_hash,
            recovered_from_attempt_id=recovered_from_attempt_id,
            recovery_disposition=recovery_disposition,
        )
        return self._store.insert_attempt(attempt)

    def _persist_unit_attempts(
        self,
        attempt: ScanAttempt,
        lineage: ScanLineage,
        outcome: EvaluationOutcome,
    ) -> None:
        now = self._clock.now()
        for unit in outcome.unit_attempts:
            if unit.kind is UnitAttemptKind.SOURCE_FETCH:
                self._store.insert_source_fetch(
                    SourceFetchAttempt(
                        fetch_attempt_id=self._id_factory(),
                        scan_attempt_id=attempt.attempt_id,
                        lineage_id=lineage.lineage_id,
                        lease_epoch=attempt.lease_epoch,
                        fencing_token=attempt.fencing_token,
                        subject_id=unit.subject_id,
                        status=unit.status,
                        reason_code=unit.reason_code,
                        source_freshness_token=unit.source_freshness_token,
                        created_at=now,
                        finished_at=now,
                        sanitized_error=_sanitize(unit.error) if unit.error else None,
                    )
                )
                continue
            self._store.insert_subscription_eval(
                SubscriptionEvaluationAttempt(
                    subscription_attempt_id=self._id_factory(),
                    scan_attempt_id=attempt.attempt_id,
                    lineage_id=lineage.lineage_id,
                    lease_epoch=attempt.lease_epoch,
                    fencing_token=attempt.fencing_token,
                    subject_id=unit.subject_id,
                    status=unit.status,
                    reason_code=unit.reason_code,
                    evidence_validity_token=unit.evidence_validity_token,
                    created_at=now,
                    finished_at=now,
                    sanitized_error=_sanitize(unit.error) if unit.error else None,
                )
            )

    def _publish(
        self,
        *,
        attempt: ScanAttempt,
        lineage: ScanLineage,
        outcome: EvaluationOutcome,
        owner_id: str | None,
        scan_scope: str,
        require_fence: bool,
        fencing_token: int | None = None,
    ) -> tuple[bool, EvaluationOutcome]:
        if require_fence:
            assert owner_id is not None
            assert fencing_token is not None
            if not self._store.fence_is_active(
                organization_id=lineage.organization_id,
                scan_scope=scan_scope,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=self._clock.now(),
            ):
                rejected = self._mark_attempt(
                    attempt,
                    ScanAttemptStatus.REJECTED_STALE_FENCE,
                    reason_code="stale_fence",
                    error="stale fence holder cannot publish",
                    recovery=RecoveryDisposition.ABANDON_STALE_FENCE,
                )
                emit(
                    self._store,
                    name="watcher_stale_fence_rejected",
                    at=self._clock.now(),
                    lineage_id=lineage.lineage_id,
                    attempt_id=rejected.attempt_id,
                    organization_id=lineage.organization_id,
                    scan_scope=scan_scope,
                    fencing_token=fencing_token,
                    reason_code="stale_fence",
                )
                blocked = outcome.model_copy(
                    update={
                        "status": EvaluationStatus.FAILED,
                        "reason_code": "stale_fence",
                        "error": "stale fence holder cannot publish",
                    }
                )
                return False, blocked

        attempt_status = _attempt_status_for(outcome.status)
        current = self._store.get_lineage(lineage.lineage_id, lineage.organization_id)
        assert current is not None
        if current.terminal_status is _TERMINAL_SUCCESS and current.terminal_attempt_id is not None:
            converged = self._mark_attempt(
                attempt,
                ScanAttemptStatus.CONVERGED_REPLAY,
                reason_code="converged_replay",
                recovery=RecoveryDisposition.REPLAY,
            )
            replay_outcome = EvaluationOutcome(
                command_id=converged.attempt_id,
                request_hash=lineage.request_hash,
                evaluation_input_hash=outcome.evaluation_input_hash,
                status=EvaluationStatus.SUCCEEDED,
                reason_code="converged_replay",
                candidate_ids=(),
            )
            return False, replay_outcome

        cas = self._store.cas_lineage_terminal(
            lineage.lineage_id,
            attempt.attempt_id,
            attempt_status.value,
            lineage.organization_id,
        )
        if cas.terminal_attempt_id != attempt.attempt_id:
            converged = self._mark_attempt(
                attempt,
                ScanAttemptStatus.CONVERGED_REPLAY,
                reason_code="converged_replay",
                recovery=RecoveryDisposition.REPLAY,
            )
            replay_outcome = EvaluationOutcome(
                command_id=converged.attempt_id,
                request_hash=lineage.request_hash,
                evaluation_input_hash=outcome.evaluation_input_hash,
                status=EvaluationStatus.SUCCEEDED
                if cas.terminal_status is _TERMINAL_SUCCESS
                else outcome.status,
                reason_code="converged_replay",
                candidate_ids=(),
            )
            return False, replay_outcome

        self._mark_attempt(
            attempt,
            attempt_status,
            reason_code=outcome.reason_code,
            error=outcome.error,
        )
        return True, outcome

    def _reject_stale(
        self,
        *,
        attempt: ScanAttempt,
        lineage: ScanLineage,
        request: ScanRequest,
        worker_id: str,
        fencing_token: int,
        reason_code: str,
    ) -> WorkerCycleResult:
        rejected = self._mark_attempt(
            attempt,
            ScanAttemptStatus.REJECTED_STALE_FENCE,
            reason_code=reason_code,
            error="stale fence holder cannot publish",
            recovery=RecoveryDisposition.ABANDON_STALE_FENCE,
        )
        emit(
            self._store,
            name="watcher_stale_fence_rejected",
            at=self._clock.now(),
            lineage_id=lineage.lineage_id,
            attempt_id=rejected.attempt_id,
            organization_id=request.organization_id,
            scan_scope=request.scan_scope,
            fencing_token=fencing_token,
            reason_code=reason_code,
            worker_id=worker_id,
        )
        health = self.health(request.organization_id, request.scan_scope)
        return WorkerCycleResult(
            status=WorkerCycleStatus.REJECTED_STALE_FENCE,
            replayed=False,
            lineage_id=lineage.lineage_id,
            attempt_id=rejected.attempt_id,
            request_hash=lineage.request_hash,
            fencing_token=fencing_token,
            lease_epoch=attempt.lease_epoch,
            outcome=EvaluationOutcome(
                command_id=rejected.attempt_id,
                request_hash=lineage.request_hash,
                evaluation_input_hash=attempt.evaluation_input_hash or lineage.request_hash,
                status=EvaluationStatus.FAILED,
                reason_code=reason_code,
                error="stale fence holder cannot publish",
                candidate_ids=(),
            ),
            health=health,
            reason_code=reason_code,
            published=False,
        )

    def _mark_attempt(
        self,
        attempt: ScanAttempt,
        status: ScanAttemptStatus,
        *,
        reason_code: str,
        error: str | None = None,
        recovery: RecoveryDisposition | None = None,
    ) -> ScanAttempt:
        updated = attempt.model_copy(
            update={
                "status": status,
                "finished_at": self._clock.now(),
                "heartbeat_at": self._clock.now(),
                "outcome_reason_code": reason_code,
                "sanitized_error": _sanitize(error) if error else None,
                "recovery_disposition": recovery or attempt.recovery_disposition,
            }
        )
        return self._store.update_attempt(updated)


def _honest_outcome(outcome: EvaluationOutcome) -> EvaluationOutcome:
    unit_failures = sum(
        1 for unit in outcome.unit_attempts if unit.status is UnitAttemptStatus.FAILED
    )
    failed_units = max(outcome.failed_units, unit_failures)
    if outcome.status is EvaluationStatus.SUCCEEDED and (failed_units > 0 or outcome.error):
        return outcome.model_copy(
            update={
                "status": EvaluationStatus.FAILED,
                "reason_code": "failure_not_propagated",
                "failed_units": failed_units,
                "error": outcome.error or "unit failure cannot be a successful scan",
                "candidate_ids": (),
            }
        )
    if outcome.candidate_ids:
        if not _canonical_candidate_publication_allowed(outcome, failed_units=failed_units):
            return outcome.model_copy(
                update={
                    "status": EvaluationStatus.FAILED,
                    "reason_code": "candidate_creation_forbidden",
                    "error": "watcher forbids non-canonical candidate publication",
                    "candidate_ids": (),
                    "failed_units": max(failed_units, 1),
                }
            )
        return outcome.model_copy(update={"failed_units": failed_units})
    return outcome.model_copy(update={"failed_units": failed_units, "candidate_ids": ()})


def _canonical_candidate_publication_allowed(
    outcome: EvaluationOutcome, *, failed_units: int
) -> bool:
    """Allow exactly one candidate when persist produced canonical CONFIRMED_SETUP."""

    if outcome.status is not EvaluationStatus.SUCCEEDED:
        return False
    if failed_units > 0 or outcome.error:
        return False
    if len(outcome.candidate_ids) != 1:
        return False
    if outcome.reason_code != _CONFIRMED_SETUP:
        return False
    token = outcome.evidence_validity_token
    return token is not None and _SHA256_HEX.fullmatch(token) is not None


def _attempt_status_for(status: EvaluationStatus) -> ScanAttemptStatus:
    return {
        EvaluationStatus.SUCCEEDED: ScanAttemptStatus.SUCCEEDED,
        EvaluationStatus.FAILED: ScanAttemptStatus.FAILED,
        EvaluationStatus.DEGRADED: ScanAttemptStatus.DEGRADED,
        EvaluationStatus.BLOCKED: ScanAttemptStatus.BLOCKED,
    }[status]


def _cycle_status(status: EvaluationStatus, published: bool) -> WorkerCycleStatus:
    if not published and status is EvaluationStatus.FAILED:
        return WorkerCycleStatus.REJECTED_STALE_FENCE
    return {
        EvaluationStatus.SUCCEEDED: WorkerCycleStatus.SUCCEEDED,
        EvaluationStatus.FAILED: WorkerCycleStatus.FAILED,
        EvaluationStatus.DEGRADED: WorkerCycleStatus.DEGRADED,
        EvaluationStatus.BLOCKED: WorkerCycleStatus.BLOCKED,
    }[status]


def _sanitize(text: str) -> str:
    return redact_text(text)[:255]
