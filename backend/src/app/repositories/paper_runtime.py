"""Paper signal, trade, and metric snapshot persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import PaperSignal, PaperTrade, PaperValidationMetricSnapshot
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import PaperTradeStatus


class PaperSignalRepository(SQLAlchemyRepository[PaperSignal]):
    model = PaperSignal

    def list_for_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperSignal], int]:
        filters = [
            PaperSignal.paper_validation_run_id == run_id,
            PaperSignal.organization_id == organization_id,
        ]
        total = int(
            self._session.scalar(select(func.count()).select_from(PaperSignal).where(*filters)) or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperSignal)
                .where(*filters)
                .order_by(PaperSignal.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total


class PaperTradeRepository(SQLAlchemyRepository[PaperTrade]):
    model = PaperTrade

    def list_for_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        status: PaperTradeStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PaperTrade], int]:
        filters = [
            PaperTrade.paper_validation_run_id == run_id,
            PaperTrade.organization_id == organization_id,
        ]
        if status is not None:
            filters.append(PaperTrade.status == status)
        total = int(
            self._session.scalar(select(func.count()).select_from(PaperTrade).where(*filters)) or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperTrade)
                .where(*filters)
                .order_by(PaperTrade.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def list_open_for_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> list[PaperTrade]:
        rows, _ = self.list_for_run(
            run_id,
            organization_id=organization_id,
            status=PaperTradeStatus.OPEN,
            limit=500,
        )
        return rows


class PaperMetricSnapshotRepository(SQLAlchemyRepository[PaperValidationMetricSnapshot]):
    model = PaperValidationMetricSnapshot
