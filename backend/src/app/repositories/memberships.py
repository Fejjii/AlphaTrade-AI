"""Membership persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import Membership
from app.repositories.base import SQLAlchemyRepository


class MembershipRepository(SQLAlchemyRepository[Membership]):
    model = Membership

    def get_primary_for_user(self, user_id: uuid.UUID) -> Membership | None:
        stmt = (
            select(Membership)
            .where(Membership.user_id == user_id)
            .order_by(Membership.created_at.asc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def get_for_user_and_org(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Membership | None:
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
        return self._session.scalars(stmt).one_or_none()
