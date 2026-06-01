"""Organization invitation repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import OrganizationInvitation
from app.repositories.base import SQLAlchemyRepository


class OrganizationInvitationRepository(SQLAlchemyRepository[OrganizationInvitation]):
    model = OrganizationInvitation

    def get_by_hash(self, token_hash: str) -> OrganizationInvitation | None:
        stmt = select(OrganizationInvitation).where(OrganizationInvitation.token_hash == token_hash)
        return self._session.scalars(stmt).one_or_none()

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[OrganizationInvitation]:
        stmt = (
            select(OrganizationInvitation)
            .where(OrganizationInvitation.organization_id == organization_id)
            .order_by(OrganizationInvitation.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())
