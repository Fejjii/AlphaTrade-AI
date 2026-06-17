"""Market watcher bridge decision repository (Slice 42)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import MarketWatcherBridgeDecision
from app.repositories.base import SQLAlchemyRepository


class MarketWatcherBridgeRepository(SQLAlchemyRepository[MarketWatcherBridgeDecision]):
    model = MarketWatcherBridgeDecision

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketWatcherBridgeDecision], int]:
        filters = [MarketWatcherBridgeDecision.organization_id == organization_id]
        total = int(
            self._session.scalar(
                select(func.count()).select_from(MarketWatcherBridgeDecision).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(MarketWatcherBridgeDecision)
                .where(*filters)
                .order_by(MarketWatcherBridgeDecision.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total
