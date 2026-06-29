"""Repository for manual paper validation session results (Slice 83 — record only)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import PaperValidationSessionResult
from app.repositories.base import SQLAlchemyRepository


class PaperValidationSessionResultRepository(SQLAlchemyRepository[PaperValidationSessionResult]):
    model = PaperValidationSessionResult

    def get_for_session(
        self,
        organization_id: uuid.UUID,
        run_session_id: uuid.UUID,
    ) -> PaperValidationSessionResult | None:
        return self._session.scalar(
            select(PaperValidationSessionResult).where(
                PaperValidationSessionResult.organization_id == organization_id,
                PaperValidationSessionResult.run_session_id == run_session_id,
            )
        )
