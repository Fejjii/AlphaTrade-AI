"""Paper validation run persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import PaperValidationRun
from app.repositories.base import SQLAlchemyRepository


class PaperValidationRunRepository(SQLAlchemyRepository[PaperValidationRun]):
    model = PaperValidationRun

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationRun], int]:
        filters = [
            PaperValidationRun.strategy_id == strategy_id,
            PaperValidationRun.organization_id == organization_id,
        ]
        count_stmt = select(func.count()).select_from(PaperValidationRun).where(*filters)
        list_stmt = (
            select(PaperValidationRun)
            .where(*filters)
            .order_by(PaperValidationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total
