"""Deterministic in-memory attribution store. Not a JournalTrade writer."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from app.learning_attribution.contracts import AttributionEvent, AttributionRecord
from app.learning_attribution.errors import (
    CrossTenantAttributionError,
    LearningAttributionConflictError,
)
from app.schemas.common import JournalLifecycleEventType


def _event_key(
    *,
    organization_id: UUID,
    account_id: UUID,
    source_system: str,
    source_aggregate: str,
    event_type: str,
    source_event_id: str,
    source_event_version: int,
    supersession: int,
) -> tuple[object, ...]:
    return (
        organization_id,
        account_id,
        source_system,
        source_aggregate,
        event_type,
        source_event_id,
        source_event_version,
        supersession,
    )


class InMemoryAttributionStore:
    """Thread-safe substitute for the later PostgreSQL attribution tables."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_candidate: dict[tuple[UUID, UUID], AttributionRecord] = {}
        self._by_lifecycle: dict[tuple[UUID, UUID], UUID] = {}
        self._events: dict[tuple[object, ...], tuple[UUID, AttributionEvent]] = {}

    def get(self, *, organization_id: UUID, candidate_id: UUID) -> AttributionRecord | None:
        with self._lock:
            return self._by_candidate.get((organization_id, candidate_id))

    def get_by_lifecycle(
        self,
        *,
        organization_id: UUID,
        execution_lifecycle_id: UUID,
    ) -> AttributionRecord | None:
        with self._lock:
            candidate_id = self._by_lifecycle.get((organization_id, execution_lifecycle_id))
            if candidate_id is None:
                return None
            return self._by_candidate.get((organization_id, candidate_id))

    def find_event(
        self,
        *,
        organization_id: UUID,
        source_system: str,
        source_aggregate: str,
        event_type: str,
        source_event_id: str,
        source_event_version: int,
        supersession: int,
        account_id: UUID,
    ) -> AttributionEvent | None:
        key = _event_key(
            organization_id=organization_id,
            account_id=account_id,
            source_system=source_system,
            source_aggregate=source_aggregate,
            event_type=event_type,
            source_event_id=source_event_id,
            source_event_version=source_event_version,
            supersession=supersession,
        )
        with self._lock:
            found = self._events.get(key)
            return None if found is None else found[1]

    def put(self, record: AttributionRecord) -> None:
        org = record.organization_id
        candidate_id = record.candidate_id
        with self._lock:
            existing = self._by_candidate.get((org, candidate_id))
            if existing is not None and existing.organization_id != org:
                raise CrossTenantAttributionError()
            lifecycle_id = record.execution_lifecycle_id
            if lifecycle_id is not None:
                owner = self._by_lifecycle.get((org, lifecycle_id))
                if owner is not None and owner != candidate_id:
                    raise LearningAttributionConflictError(
                        "Execution lifecycle is already bound to a different candidate.",
                        details={
                            "reason": "lifecycle_candidate_conflict",
                            "execution_lifecycle_id": str(lifecycle_id),
                        },
                    )
                self._by_lifecycle[(org, lifecycle_id)] = candidate_id
            for event in record.events:
                key = _event_key(
                    organization_id=org,
                    account_id=record.facts.account_id,
                    source_system=event.source_system,
                    source_aggregate=event.source_aggregate,
                    event_type=event.event_type.value
                    if isinstance(event.event_type, JournalLifecycleEventType)
                    else str(event.event_type),
                    source_event_id=event.source_event_id,
                    source_event_version=event.source_event_version,
                    supersession=event.supersession,
                )
                prior = self._events.get(key)
                if prior is not None and prior[1].event_content_hash != event.event_content_hash:
                    raise LearningAttributionConflictError(
                        "Attribution source identity replayed with conflicting content.",
                        details={"reason": "conflicting_source_identity"},
                    )
                self._events[key] = (candidate_id, event)
            self._by_candidate[(org, candidate_id)] = record

    def list_for_organization(self, organization_id: UUID) -> tuple[AttributionRecord, ...]:
        with self._lock:
            records = [
                record for (org, _), record in self._by_candidate.items() if org == organization_id
            ]
            return tuple(sorted(records, key=lambda item: str(item.candidate_id)))
