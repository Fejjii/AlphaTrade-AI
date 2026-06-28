"""Repository for non-executable paper validation drafts (Slice 78)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import PaperValidationDraft
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import PaperValidationDraftStatus


class PaperValidationDraftRepository(SQLAlchemyRepository[PaperValidationDraft]):
    model = PaperValidationDraft

    def get_active_for_alert(
        self,
        organization_id: uuid.UUID,
        source_alert_id: uuid.UUID,
    ) -> PaperValidationDraft | None:
        return self._session.scalar(
            select(PaperValidationDraft).where(
                PaperValidationDraft.organization_id == organization_id,
                PaperValidationDraft.source_alert_id == source_alert_id,
                PaperValidationDraft.status == PaperValidationDraftStatus.DRAFT.value,
            )
        )

    def get_for_org(
        self,
        draft_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationDraft | None:
        return self._session.scalar(
            select(PaperValidationDraft).where(
                PaperValidationDraft.id == draft_id,
                PaperValidationDraft.organization_id == organization_id,
            )
        )

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationDraftStatus | None = PaperValidationDraftStatus.DRAFT,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationDraft], int]:
        filters = [PaperValidationDraft.organization_id == organization_id]
        if status is not None:
            filters.append(PaperValidationDraft.status == status.value)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationDraft).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationDraft)
                .where(*filters)
                .order_by(PaperValidationDraft.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def latest_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationDraftStatus = PaperValidationDraftStatus.DRAFT,
    ) -> PaperValidationDraft | None:
        return self._session.scalar(
            select(PaperValidationDraft)
            .where(
                PaperValidationDraft.organization_id == organization_id,
                PaperValidationDraft.status == status.value,
            )
            .order_by(PaperValidationDraft.created_at.desc())
            .limit(1)
        )
