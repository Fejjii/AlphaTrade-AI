"""Aggregate organization usage for billing export (no PII or journal content)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import UsageEvent as UsageEventModel
from app.db.models import UsageExportBatch as UsageExportBatchModel
from app.repositories.billing import UsageExportBatchRepository
from app.repositories.usage import UsageRepository
from app.schemas.billing import BillingProviderName, UsageExportLineItem, UsageExportResponse
from app.schemas.common import CostSource
from app.services.usage_service import month_start


class UsageExportService:
    """Build billing-safe usage aggregates for a period."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._usage = UsageRepository(session)
        self._batches = UsageExportBatchRepository(session)

    def export_for_period(
        self,
        organization_id: uuid.UUID,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        provider_name: str,
    ) -> UsageExportResponse:
        start = period_start or month_start()
        end = period_end or datetime.now(UTC)

        summary = self._usage.summarize(
            organization_id=organization_id,
            since=start,
            until=end,
        )
        line_items = self._feature_line_items(organization_id, start, end)

        billing_grade = summary.billing_grade_cost
        estimated = summary.total_estimated_cost
        provider_reported = summary.total_provider_reported_cost
        cost_is_billing_grade = billing_grade > 0 and estimated == billing_grade

        batch = UsageExportBatchModel(
            organization_id=organization_id,
            period_start=start,
            period_end=end,
            provider=provider_name,
            total_events=summary.event_count,
            total_tokens=summary.total_tokens,
            provider_reported_cost=provider_reported,
            estimated_cost=estimated,
            billing_grade_cost=billing_grade,
            cost_is_billing_grade=cost_is_billing_grade,
            fallback_event_count=summary.fallback_count,
            export_summary={
                "line_items": [item.model_dump(mode="json") for item in line_items],
                "cost_note": (
                    "billing_grade"
                    if cost_is_billing_grade
                    else "includes_non_billing_grade_estimates"
                ),
            },
        )
        self._batches.add(batch)
        self._session.flush()

        return UsageExportResponse(
            batch_id=batch.id,
            organization_id=organization_id,
            period_start=start,
            period_end=end,
            total_events=summary.event_count,
            total_tokens=summary.total_tokens,
            provider_reported_cost=provider_reported,
            estimated_cost=estimated,
            billing_grade_cost=billing_grade,
            cost_is_billing_grade=cost_is_billing_grade,
            fallback_event_count=summary.fallback_count,
            line_items=line_items,
            provider=BillingProviderName(provider_name),
            exported_at=datetime.now(UTC),
        )

    def _feature_line_items(
        self,
        organization_id: uuid.UUID,
        since: datetime,
        until: datetime,
    ) -> list[UsageExportLineItem]:
        stmt = (
            select(
                UsageEventModel.feature,
                func.count(UsageEventModel.id),
                func.coalesce(func.sum(UsageEventModel.total_tokens), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                UsageEventModel.cost_source == CostSource.PROVIDER_REPORTED.value,
                                func.coalesce(UsageEventModel.provider_reported_cost, 0),
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(UsageEventModel.estimated_cost), 0),
            )
            .where(
                UsageEventModel.organization_id == organization_id,
                UsageEventModel.event_at >= since,
                UsageEventModel.event_at <= until,
            )
            .group_by(UsageEventModel.feature)
        )
        rows = self._session.execute(stmt).all()
        items: list[UsageExportLineItem] = []
        for feature, count, tokens, reported, estimated in rows:
            reported_dec = Decimal(str(reported))
            estimated_dec = Decimal(str(estimated))
            items.append(
                UsageExportLineItem(
                    feature=feature,
                    event_count=int(count),
                    total_tokens=int(tokens),
                    provider_reported_cost=reported_dec,
                    estimated_cost=estimated_dec,
                    cost_is_billing_grade=reported_dec > 0 and estimated_dec == reported_dec,
                )
            )
        return items
