"""Approval request persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import ApprovalRequest
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import ApprovalStatus


class ApprovalRepository(SQLAlchemyRepository[ApprovalRequest]):
    model = ApprovalRequest

    def get_by_proposal(self, proposal_id: uuid.UUID) -> ApprovalRequest | None:
        stmt = select(ApprovalRequest).where(ApprovalRequest.proposal_id == proposal_id)
        return self._session.scalar(stmt)

    def list_approvals(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        status: ApprovalStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApprovalRequest], int]:
        filters = []
        if organization_id is not None:
            filters.append(ApprovalRequest.organization_id == organization_id)
        if user_id is not None:
            filters.append(ApprovalRequest.user_id == user_id)
        if status is not None:
            filters.append(ApprovalRequest.status == status)

        count_stmt = select(func.count()).select_from(ApprovalRequest)
        list_stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt.limit(limit).offset(offset)).all()), total
