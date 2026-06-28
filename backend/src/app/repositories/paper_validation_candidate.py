"""Repository for non-executable paper validation candidates (Slice 80)."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import ClassVar

from sqlalchemy import func, select

from app.db.models import PaperValidationCandidate
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import PaperValidationCandidateStatus


class PaperValidationCandidateRepository(SQLAlchemyRepository[PaperValidationCandidate]):
    model = PaperValidationCandidate

    _ACTIVE_STATUSES: ClassVar[set[str]] = {
        PaperValidationCandidateStatus.QUEUED.value,
        PaperValidationCandidateStatus.REVIEWING.value,
    }

    def get_active_for_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> PaperValidationCandidate | None:
        return self._session.scalar(
            select(PaperValidationCandidate).where(
                PaperValidationCandidate.organization_id == organization_id,
                PaperValidationCandidate.draft_id == draft_id,
                PaperValidationCandidate.candidate_status.in_(self._ACTIVE_STATUSES),
            )
        )

    def get_for_org(
        self,
        candidate_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationCandidate | None:
        return self._session.scalar(
            select(PaperValidationCandidate).where(
                PaperValidationCandidate.id == candidate_id,
                PaperValidationCandidate.organization_id == organization_id,
            )
        )

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationCandidateStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationCandidate], int]:
        filters = [PaperValidationCandidate.organization_id == organization_id]
        if status is not None:
            filters.append(PaperValidationCandidate.candidate_status == status.value)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationCandidate).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationCandidate)
                .where(*filters)
                .order_by(PaperValidationCandidate.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def summary_for_org(self, organization_id: uuid.UUID) -> dict[str, object]:
        rows = list(
            self._session.scalars(
                select(PaperValidationCandidate).where(
                    PaperValidationCandidate.organization_id == organization_id
                )
            ).all()
        )
        by_status = Counter(row.candidate_status for row in rows)
        by_condition: Counter[str] = Counter()
        by_symbol: Counter[str] = Counter()
        latest_created_at = None
        for row in rows:
            if row.condition:
                by_condition[row.condition] += 1
            if row.symbol:
                by_symbol[row.symbol] += 1
            if latest_created_at is None or row.created_at > latest_created_at:
                latest_created_at = row.created_at
        return {
            "total_queued": by_status.get(PaperValidationCandidateStatus.QUEUED.value, 0),
            "total_reviewing": by_status.get(PaperValidationCandidateStatus.REVIEWING.value, 0),
            "total_archived": by_status.get(PaperValidationCandidateStatus.ARCHIVED.value, 0),
            "by_condition": dict(by_condition),
            "by_symbol": dict(by_symbol),
            "latest_created_at": latest_created_at,
        }
