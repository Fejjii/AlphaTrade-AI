"""Organization persistence."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import Organization
from app.repositories.base import SQLAlchemyRepository


class OrganizationRepository(SQLAlchemyRepository[Organization]):
    model = Organization

    def get_by_name(self, name: str) -> Organization | None:
        stmt = select(Organization).where(Organization.name == name)
        return self._session.scalars(stmt).one_or_none()
