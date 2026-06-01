"""Watchlist persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import WatchlistItem
from app.repositories.base import SQLAlchemyRepository


class WatchlistRepository(SQLAlchemyRepository[WatchlistItem]):
    model = WatchlistItem

    def list_items(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WatchlistItem], int]:
        filters = [
            WatchlistItem.organization_id == organization_id,
            WatchlistItem.user_id == user_id,
        ]
        count_stmt = select(func.count()).select_from(WatchlistItem).where(*filters)
        list_stmt = (
            select(WatchlistItem)
            .where(*filters)
            .order_by(WatchlistItem.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_scoped(
        self,
        item_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WatchlistItem | None:
        stmt = select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.organization_id == organization_id,
            WatchlistItem.user_id == user_id,
        )
        return self._session.scalar(stmt)
