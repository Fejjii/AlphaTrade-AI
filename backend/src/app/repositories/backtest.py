"""Backtest run persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import BacktestRun
from app.repositories.base import SQLAlchemyRepository


class BacktestRunRepository(SQLAlchemyRepository[BacktestRun]):
    model = BacktestRun

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BacktestRun], int]:
        filters = [
            BacktestRun.strategy_id == strategy_id,
            BacktestRun.organization_id == organization_id,
        ]
        count_stmt = select(func.count()).select_from(BacktestRun).where(*filters)
        list_stmt = (
            select(BacktestRun)
            .where(*filters)
            .order_by(BacktestRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_scoped(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> BacktestRun | None:
        stmt = select(BacktestRun).where(
            BacktestRun.id == run_id,
            BacktestRun.organization_id == organization_id,
        )
        return self._session.scalar(stmt)
