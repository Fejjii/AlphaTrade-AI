"""Repository for manual paper validation run sessions (Slice 82 — record only)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import PaperValidationRunSession
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import PaperValidationRunSessionStatus


class PaperValidationRunSessionRepository(SQLAlchemyRepository[PaperValidationRunSession]):
    model = PaperValidationRunSession

    def get_active_for_plan(
        self,
        organization_id: uuid.UUID,
        run_plan_id: uuid.UUID,
    ) -> PaperValidationRunSession | None:
        return self._session.scalar(
            select(PaperValidationRunSession).where(
                PaperValidationRunSession.organization_id == organization_id,
                PaperValidationRunSession.run_plan_id == run_plan_id,
                PaperValidationRunSession.session_status
                == PaperValidationRunSessionStatus.RUNNING.value,
            )
        )

    def get_for_org(
        self,
        session_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRunSession | None:
        return self._session.scalar(
            select(PaperValidationRunSession).where(
                PaperValidationRunSession.id == session_id,
                PaperValidationRunSession.organization_id == organization_id,
            )
        )

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationRunSessionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationRunSession], int]:
        filters = [PaperValidationRunSession.organization_id == organization_id]
        if status is not None:
            filters.append(PaperValidationRunSession.session_status == status.value)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationRunSession).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationRunSession)
                .where(*filters)
                .order_by(PaperValidationRunSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total
