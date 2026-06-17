"""Paper validation service (Slice 35, 39 — paper only)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.repositories.paper_validation import PaperValidationRunRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import (
    PaperValidationRecommendation,
    PaperValidationStatus,
)
from app.schemas.paper_validation import (
    PaperValidationMetrics,
    PaperValidationRun,
    PaperValidationRunStart,
    PaperValidationSummary,
)
from app.services.paper_validation_runtime_service import PaperValidationRuntimeService


class PaperValidationService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runs = PaperValidationRunRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._runtime = PaperValidationRuntimeService(session, self._settings)

    def start(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: PaperValidationRunStart | None = None,
    ) -> PaperValidationRun:
        return self._runtime.start(
            strategy_id,
            payload,
            organization_id=organization_id,
            user_id=user_id,
        )

    def get_run(
        self,
        strategy_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PaperValidationRun:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None or row.strategy_id != strategy_id:
            raise NotFoundError("Paper validation run not found.")
        return self._runtime._to_schema(row)

    def refresh_metrics(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRun:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Paper validation run not found.")
        metrics = self._runtime.get_metrics(run_id, organization_id=organization_id)
        row.metrics = metrics.model_dump(mode="json")
        recommendation = self._recommend(metrics, eligible=row.paper_eligible)
        row.recommendation = recommendation.value
        if metrics.paper_trades_count >= 10:
            row.status = (
                PaperValidationStatus.PASSED
                if metrics.expectancy > 0 and metrics.profit_factor >= 1.0
                else PaperValidationStatus.FAILED
            )
            row.ended_at = datetime.now(UTC)
        return self._runtime._to_schema(row)

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
            runs=[self._runtime._to_schema(row) for row in rows],
            total=total,
        )

    @staticmethod
    def _recommend(
        metrics: PaperValidationMetrics,
        *,
        eligible: bool,
    ) -> PaperValidationRecommendation:
        if metrics.paper_trades_count == 0:
            return PaperValidationRecommendation.INSUFFICIENT_DATA
        if not eligible:
            return PaperValidationRecommendation.RESTRICT
        if metrics.expectancy <= 0 or metrics.profit_factor < 1.0:
            return PaperValidationRecommendation.IMPROVE
        if metrics.win_rate >= 0.45 and metrics.profit_factor >= 1.1:
            return PaperValidationRecommendation.CONTINUE
        return PaperValidationRecommendation.IMPROVE
