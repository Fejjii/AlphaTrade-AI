"""Manual chart level persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import ManualChartLevel
from app.repositories.base import SQLAlchemyRepository


class ManualChartLevelRepository(SQLAlchemyRepository[ManualChartLevel]):
    model = ManualChartLevel

    def list_scoped(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ManualChartLevel], int]:
        filters = [ManualChartLevel.organization_id == organization_id]
        if user_id is not None:
            filters.append(ManualChartLevel.user_id == user_id)
        if symbol is not None:
            filters.append(ManualChartLevel.symbol == symbol.upper())
        if exchange is not None:
            filters.append(ManualChartLevel.exchange == exchange)
        if enabled_only:
            filters.append(ManualChartLevel.enabled.is_(True))
        count_stmt = select(func.count()).select_from(ManualChartLevel).where(*filters)
        list_stmt = (
            select(ManualChartLevel)
            .where(*filters)
            .order_by(ManualChartLevel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_scoped(
        self,
        level_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> ManualChartLevel | None:
        stmt = select(ManualChartLevel).where(
            ManualChartLevel.id == level_id,
            ManualChartLevel.organization_id == organization_id,
        )
        if user_id is not None:
            stmt = stmt.where(ManualChartLevel.user_id == user_id)
        return self._session.scalar(stmt)

    def get_many_scoped(
        self,
        level_ids: list[uuid.UUID],
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> list[ManualChartLevel]:
        if not level_ids:
            return []
        stmt = select(ManualChartLevel).where(
            ManualChartLevel.id.in_(level_ids),
            ManualChartLevel.organization_id == organization_id,
        )
        if user_id is not None:
            stmt = stmt.where(ManualChartLevel.user_id == user_id)
        return list(self._session.scalars(stmt).all())
