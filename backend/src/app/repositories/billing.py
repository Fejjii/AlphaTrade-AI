"""Billing persistence repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import (
    BillingCustomer as BillingCustomerModel,
)
from app.db.models import (
    BillingEvent as BillingEventModel,
)
from app.db.models import (
    Subscription as SubscriptionModel,
)
from app.db.models import (
    UsageExportBatch as UsageExportBatchModel,
)
from app.db.models import (
    WebhookEvent as WebhookEventModel,
)
from app.repositories.base import SQLAlchemyRepository


class BillingCustomerRepository(SQLAlchemyRepository[BillingCustomerModel]):
    model = BillingCustomerModel

    def get_by_organization(self, organization_id: uuid.UUID) -> BillingCustomerModel | None:
        stmt = select(BillingCustomerModel).where(
            BillingCustomerModel.organization_id == organization_id
        )
        return self._session.scalar(stmt)


class SubscriptionRepository(SQLAlchemyRepository[SubscriptionModel]):
    model = SubscriptionModel

    def get_by_organization(self, organization_id: uuid.UUID) -> SubscriptionModel | None:
        stmt = select(SubscriptionModel).where(SubscriptionModel.organization_id == organization_id)
        return self._session.scalar(stmt)


class BillingEventRepository(SQLAlchemyRepository[BillingEventModel]):
    model = BillingEventModel


class UsageExportBatchRepository(SQLAlchemyRepository[UsageExportBatchModel]):
    model = UsageExportBatchModel

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[UsageExportBatchModel]:
        stmt = (
            select(UsageExportBatchModel)
            .where(UsageExportBatchModel.organization_id == organization_id)
            .order_by(UsageExportBatchModel.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())


class WebhookEventRepository(SQLAlchemyRepository[WebhookEventModel]):
    model = WebhookEventModel

    def get_by_provider_event_id(self, provider_event_id: str) -> WebhookEventModel | None:
        stmt = select(WebhookEventModel).where(
            WebhookEventModel.provider_event_id == provider_event_id
        )
        return self._session.scalar(stmt)
