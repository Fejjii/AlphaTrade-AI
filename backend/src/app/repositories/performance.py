"""Persistence for performance snapshots and per-strategy daily rollups."""

from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import select

from app.db.models import PerformanceSnapshot, StrategyPerformanceDaily
from app.repositories.base import SQLAlchemyRepository


class PerformanceSnapshotRepository(SQLAlchemyRepository[PerformanceSnapshot]):
    model = PerformanceSnapshot

    def latest(self, *, organization_id: uuid.UUID | None = None) -> PerformanceSnapshot | None:
        stmt = select(PerformanceSnapshot)
        if organization_id is not None:
            stmt = stmt.where(PerformanceSnapshot.organization_id == organization_id)
        stmt = stmt.order_by(PerformanceSnapshot.as_of.desc()).limit(1)
        return self._session.scalar(stmt)


class StrategyPerformanceDailyRepository(SQLAlchemyRepository[StrategyPerformanceDaily]):
    model = StrategyPerformanceDaily

    def get_for_day(
        self,
        *,
        organization_id: uuid.UUID | None,
        strategy_id: str,
        day: date_type,
    ) -> StrategyPerformanceDaily | None:
        stmt = select(StrategyPerformanceDaily).where(
            StrategyPerformanceDaily.organization_id == organization_id,
            StrategyPerformanceDaily.strategy_id == strategy_id,
            StrategyPerformanceDaily.day == day,
        )
        return self._session.scalar(stmt)
