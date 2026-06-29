"""Repository for non-executable paper validation run plans (Slice 81)."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import ClassVar

from sqlalchemy import func, select

from app.db.models import PaperValidationRunPlan
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import PaperValidationRunPlanStatus


class PaperValidationRunPlanRepository(SQLAlchemyRepository[PaperValidationRunPlan]):
    model = PaperValidationRunPlan

    _ACTIVE_STATUSES: ClassVar[set[str]] = {
        PaperValidationRunPlanStatus.PLANNED.value,
        PaperValidationRunPlanStatus.NEEDS_REVISION.value,
    }

    def get_active_for_candidate(
        self,
        organization_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> PaperValidationRunPlan | None:
        return self._session.scalar(
            select(PaperValidationRunPlan).where(
                PaperValidationRunPlan.organization_id == organization_id,
                PaperValidationRunPlan.candidate_id == candidate_id,
                PaperValidationRunPlan.plan_status.in_(self._ACTIVE_STATUSES),
            )
        )

    def get_for_org(
        self,
        plan_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> PaperValidationRunPlan | None:
        return self._session.scalar(
            select(PaperValidationRunPlan).where(
                PaperValidationRunPlan.id == plan_id,
                PaperValidationRunPlan.organization_id == organization_id,
            )
        )

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        status: PaperValidationRunPlanStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationRunPlan], int]:
        filters = [PaperValidationRunPlan.organization_id == organization_id]
        if status is not None:
            filters.append(PaperValidationRunPlan.plan_status == status.value)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationRunPlan).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationRunPlan)
                .where(*filters)
                .order_by(PaperValidationRunPlan.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def summary_for_org(self, organization_id: uuid.UUID) -> dict[str, object]:
        rows = list(
            self._session.scalars(
                select(PaperValidationRunPlan).where(
                    PaperValidationRunPlan.organization_id == organization_id
                )
            ).all()
        )
        by_status = Counter(row.plan_status for row in rows)
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
            "total_planned": by_status.get(PaperValidationRunPlanStatus.PLANNED.value, 0),
            "total_needs_revision": by_status.get(
                PaperValidationRunPlanStatus.NEEDS_REVISION.value, 0
            ),
            "total_archived": by_status.get(PaperValidationRunPlanStatus.ARCHIVED.value, 0),
            "by_condition": dict(by_condition),
            "by_symbol": dict(by_symbol),
            "latest_created_at": latest_created_at,
        }
