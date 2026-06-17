"""Market watcher observation repository (Slice 41)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import MarketWatcherObservation
from app.repositories.base import SQLAlchemyRepository


class MarketWatcherObservationRepository(SQLAlchemyRepository[MarketWatcherObservation]):
    model = MarketWatcherObservation

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketWatcherObservation], int]:
        filters = [MarketWatcherObservation.organization_id == organization_id]
        if symbol is not None:
            filters.append(MarketWatcherObservation.symbol == symbol)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(MarketWatcherObservation).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(MarketWatcherObservation)
                .where(*filters)
                .order_by(MarketWatcherObservation.observed_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def latest_for_org(self, organization_id: uuid.UUID) -> datetime | None:
        return self._session.scalar(
            select(func.max(MarketWatcherObservation.observed_at)).where(
                MarketWatcherObservation.organization_id == organization_id
            )
        )
