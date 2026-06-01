"""Organization quota persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import OrganizationQuota as OrganizationQuotaModel
from app.repositories.base import SQLAlchemyRepository


class QuotaRepository(SQLAlchemyRepository[OrganizationQuotaModel]):
    model = OrganizationQuotaModel

    def get_by_organization(self, organization_id: uuid.UUID) -> OrganizationQuotaModel | None:
        stmt = select(OrganizationQuotaModel).where(
            OrganizationQuotaModel.organization_id == organization_id
        )
        return self._session.scalar(stmt)
