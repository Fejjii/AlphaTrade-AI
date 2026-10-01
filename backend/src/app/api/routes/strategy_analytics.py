"""Canonical authenticated reads of the existing Strategy Analytics foundation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import AwareDatetime, ValidationError

from app.core.dependencies import StrategyAnalyticsServiceDep
from app.core.errors import ValidationAppError
from app.schemas.common import JournalTradeSource, MarketRegime
from app.schemas.strategy_analytics import (
    NestedMaturityStage,
    StrategyAnalyticsDimension,
    StrategyAnalyticsFilters,
    StrategyAnalyticsReport,
)
from app.security.rbac import ReaderDep

router = APIRouter(prefix="/strategy-analytics", tags=["strategy-analytics"])


@router.get(
    "/report",
    response_model=StrategyAnalyticsReport,
    summary="Strategy analytics over the authenticated user's closed journal trades",
    description=(
        "Read-only recorded history. Repeat group_by to combine segmentation dimensions. "
        "Dates are inclusive timezone-aware timestamps using journal exit/entry/creation time. "
        "Strategy, version and Nested stage filters apply after the configured journal row cap. "
        "Unavailable metrics stay null; metric samples, confidence, missing fields, warnings "
        "and limitations are returned unchanged from the canonical analytics service."
    ),
)
def get_strategy_analytics_report(
    tenant: ReaderDep,
    service: StrategyAnalyticsServiceDep,
    group_by: list[StrategyAnalyticsDimension] = Query(
        default=[StrategyAnalyticsDimension.STRATEGY], min_length=1, max_length=6
    ),
    strategy_id: UUID | None = Query(default=None),
    strategy_version_id: UUID | None = Query(default=None),
    symbol: str | None = Query(default=None, max_length=30),
    timeframe: str | None = Query(default=None, max_length=8),
    market_regime: MarketRegime | None = Query(default=None),
    nested_maturity_stage: NestedMaturityStage | None = Query(default=None),
    date_from: AwareDatetime | None = Query(default=None),
    date_to: AwareDatetime | None = Query(default=None),
    source: JournalTradeSource | None = Query(default=None),
    min_sample_size: int = Query(default=20, ge=1, le=1000),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> StrategyAnalyticsReport:
    try:
        filters = StrategyAnalyticsFilters(
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            symbol=symbol,
            timeframe=timeframe,
            market_regime=market_regime,
            nested_maturity_stage=nested_maturity_stage,
            date_from=date_from,
            date_to=date_to,
            source=source,
        )
    except ValidationError as exc:
        raise ValidationAppError(
            "Invalid analytics filters.",
            details={"errors": exc.errors(include_context=False, include_input=False)},
        ) from exc
    return service.compute(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        filters=filters,
        group_by=tuple(group_by),
        min_sample_size=min_sample_size,
        limit=limit,
        offset=offset,
    )
