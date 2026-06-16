"""Backtest placeholder service (Slice 34 — no live execution)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.db.models import BacktestRun as BacktestRunModel
from app.db.models import UserStrategy as UserStrategyModel
from app.repositories.backtest import BacktestRunRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.backtest import (
    BacktestAssumptions,
    BacktestPlaceholderResult,
    BacktestRun,
    BacktestRunCreate,
)
from app.schemas.common import BacktestRunStatus, BacktestStatus, StrategyValidationStatus
from app.schemas.strategy_library import StrategyCard


class BacktestService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runs = BacktestRunRepository(session)
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)

    def create(
        self,
        strategy_id: uuid.UUID,
        payload: BacktestRunCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BacktestRun:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")

        version = self._versions.latest(strategy_id)
        assumptions = payload.assumptions or BacktestAssumptions()

        run = BacktestRunModel(
            strategy_id=strategy_id,
            strategy_version_id=version.id if version else None,
            organization_id=organization_id,
            user_id=user_id,
            status=BacktestRunStatus.QUEUED,
            assumptions=assumptions.model_dump(mode="json"),
        )
        self._runs.add(run)

        if self._settings.provider_mode == "mock" or not self._settings.enable_real_trading:
            self._complete_mock(run, strategy, version)

        return self._to_schema(run)

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BacktestRun], int]:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        rows, total = self._runs.list_for_strategy(
            strategy_id, organization_id=organization_id, limit=limit, offset=offset
        )
        return [self._to_schema(row) for row in rows], total

    def get(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> BacktestRun:
        row = self._runs.get_scoped(run_id, organization_id=organization_id)
        if row is None:
            raise NotFoundError("Backtest run not found.")
        return self._to_schema(row)

    def _complete_mock(
        self,
        run: BacktestRunModel,
        strategy: UserStrategyModel,
        version: object | None,
    ) -> None:
        run.status = BacktestRunStatus.COMPLETED
        card = StrategyCard.model_validate(version.card) if version else None
        meets = card is not None and len(card.success_criteria) > 0
        result = BacktestPlaceholderResult(
            win_rate=0.48,
            profit_factor=1.35,
            max_drawdown_pct=12.5,
            trade_count=int(run.assumptions.get("sample_size", 100)),
            meets_success_criteria=meets,
        )
        run.result = result.model_dump(mode="json")

        if version is not None and meets:
            version.backtest_status = BacktestStatus.COMPLETED
            if version.validation_status == StrategyValidationStatus.IN_REVIEW:
                version.validation_status = StrategyValidationStatus.VALIDATED

    @staticmethod
    def _to_schema(row: BacktestRunModel) -> BacktestRun:
        assumptions = BacktestAssumptions.model_validate(row.assumptions or {})
        result = None
        if row.result:
            result = BacktestPlaceholderResult.model_validate(row.result)
        return BacktestRun(
            id=row.id,
            strategy_id=row.strategy_id,
            strategy_version_id=row.strategy_version_id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            status=row.status,
            assumptions=assumptions,
            result=result,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
