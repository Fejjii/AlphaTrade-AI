"""Attribution persistence port. In-memory for unit tests; PostgreSQL in Phase 8."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.learning_attribution.contracts import AttributionEvent, AttributionRecord


class AttributionStore(Protocol):
    def get(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> AttributionRecord | None: ...

    def get_by_lifecycle(
        self,
        *,
        organization_id: UUID,
        execution_lifecycle_id: UUID,
    ) -> AttributionRecord | None: ...

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
    ) -> AttributionEvent | None: ...

    def put(self, record: AttributionRecord) -> None: ...

    def list_for_organization(self, organization_id: UUID) -> tuple[AttributionRecord, ...]: ...
