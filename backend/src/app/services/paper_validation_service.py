"""Paper validation placeholder service (Slice 34 — paper only)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import PaperValidationRun as PaperValidationRunModel
from app.repositories.paper_validation import PaperValidationRunRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import PaperValidationStatus, StrategyValidationStatus
from app.schemas.paper_validation import PaperValidationRun, PaperValidationSummary


class PaperValidationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._runs = PaperValidationRunRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)

    def start(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperValidationRun:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = self._versions.latest(strategy_id)
        eligible = False
        if version is not None:
            eligible = version.validation_status in {
                StrategyValidationStatus.VALIDATED,
                StrategyValidationStatus.IN_REVIEW,
            }
            version.paper_validation_status = PaperValidationStatus.IN_PROGRESS

        strategy.paper_eligible = eligible

        run = PaperValidationRunModel(
            strategy_id=strategy_id,
            organization_id=organization_id,
            user_id=user_id,
            status=PaperValidationStatus.IN_PROGRESS,
            paper_eligible=eligible,
            notes="Paper validation placeholder started — no exchange orders.",
        )
        self._runs.add(run)
        return self._to_schema(run)

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PaperValidationSummary:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = self._versions.latest(strategy_id)
        rows, total = self._runs.list_for_strategy(
            strategy_id, organization_id=organization_id, limit=limit, offset=offset
        )
        latest_status = version.paper_validation_status if version else None
        return PaperValidationSummary(
            strategy_id=strategy_id,
            paper_eligible=strategy.paper_eligible,
            latest_status=latest_status,
            runs=[self._to_schema(row) for row in rows],
            total=total,
        )

    @staticmethod
    def _to_schema(row: PaperValidationRunModel) -> PaperValidationRun:
        return PaperValidationRun(
            id=row.id,
            strategy_id=row.strategy_id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            status=row.status,
            paper_eligible=row.paper_eligible,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
