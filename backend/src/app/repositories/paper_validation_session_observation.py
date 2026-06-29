"""Repository for manual paper validation session observations (Slice 83 — record only)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import PaperValidationSessionObservation
from app.repositories.base import SQLAlchemyRepository


class PaperValidationSessionObservationRepository(
    SQLAlchemyRepository[PaperValidationSessionObservation]
):
    model = PaperValidationSessionObservation

    def list_for_session(
        self,
        organization_id: uuid.UUID,
        run_session_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationSessionObservation], int]:
        filters = [
            PaperValidationSessionObservation.organization_id == organization_id,
            PaperValidationSessionObservation.run_session_id == run_session_id,
        ]
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationSessionObservation).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationSessionObservation)
                .where(*filters)
                .order_by(PaperValidationSessionObservation.created_at.asc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total
