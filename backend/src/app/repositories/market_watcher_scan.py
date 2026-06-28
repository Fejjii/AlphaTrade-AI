"""Market watcher scan summary repository (Slice 75)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import MarketWatcherScanRecord
from app.repositories.base import SQLAlchemyRepository


class MarketWatcherScanRepository(SQLAlchemyRepository[MarketWatcherScanRecord]):
    model = MarketWatcherScanRecord

    def latest_for_org(self, organization_id: uuid.UUID) -> MarketWatcherScanRecord | None:
        return self._session.scalar(
            select(MarketWatcherScanRecord)
            .where(MarketWatcherScanRecord.organization_id == organization_id)
            .order_by(MarketWatcherScanRecord.scanned_at.desc())
            .limit(1)
        )

    def list_recent_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 10,
    ) -> list[MarketWatcherScanRecord]:
        return list(
            self._session.scalars(
                select(MarketWatcherScanRecord)
                .where(MarketWatcherScanRecord.organization_id == organization_id)
                .order_by(MarketWatcherScanRecord.scanned_at.desc())
                .limit(limit)
            ).all()
        )
