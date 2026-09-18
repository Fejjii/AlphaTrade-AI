"""Journal lifecycle application bridge to learning attribution.

``JournalLifecycleProjector`` remains the only JournalTrade writer. This
service attributes learning facts after projection. It does not dispatch
execution, mutate SetupAssessment, or create Candidates.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.learning_attribution.contracts import AttributionCommand, AttributionResult
from app.learning_attribution.memory import InMemoryAttributionStore
from app.learning_attribution.ports import AttributionStore
from app.learning_attribution.service import LearningAttributionService
from app.services.audit_service import AuditService
from app.services.journal_lifecycle_projector import JournalLifecycleProjector


class JournalLifecycleLearningService:
    """Connect canonical journal projection to record-only learning attribution."""

    def __init__(
        self,
        session: Session,
        audit_service: AuditService,
        store: AttributionStore | None = None,
    ) -> None:
        self._projector = JournalLifecycleProjector(session, audit_service)
        self._attribution = LearningAttributionService(
            session,
            self._projector,
            store if store is not None else InMemoryAttributionStore(),
        )

    @property
    def projector(self) -> JournalLifecycleProjector:
        return self._projector

    @property
    def attribution(self) -> LearningAttributionService:
        return self._attribution

    def apply(self, command: AttributionCommand) -> AttributionResult:
        return self._attribution.apply(command)
