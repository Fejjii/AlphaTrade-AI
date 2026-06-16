"""Backtest trade persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import BacktestTrade
from app.repositories.base import SQLAlchemyRepository


class BacktestTradeRepository(SQLAlchemyRepository[BacktestTrade]):
    model = BacktestTrade

    def list_for_run(
        self,
        run_id: uuid.UUID,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[BacktestTrade], int]:
        filters = [BacktestTrade.backtest_run_id == run_id]
        count_stmt = select(func.count()).select_from(BacktestTrade).where(*filters)
        list_stmt = (
            select(BacktestTrade)
            .where(*filters)
            .order_by(BacktestTrade.entry_time.asc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total
