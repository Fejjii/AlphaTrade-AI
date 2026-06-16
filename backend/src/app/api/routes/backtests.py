"""Backtest API (Slice 35)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import BacktestServiceDep
from app.schemas.backtest import BacktestRun, PaginatedBacktestTrades
from app.security.rbac import TraderDep

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("/{backtest_id}", response_model=BacktestRun, summary="Get backtest run with metrics")
async def get_backtest(
    backtest_id: uuid.UUID,
    tenant: TraderDep,
    service: BacktestServiceDep,
) -> BacktestRun:
    return service.get(backtest_id, organization_id=tenant.organization_id)


@router.get(
    "/{backtest_id}/trades",
    response_model=PaginatedBacktestTrades,
    summary="List simulated trades for backtest run",
)
async def list_backtest_trades(
    backtest_id: uuid.UUID,
    tenant: TraderDep,
    service: BacktestServiceDep,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedBacktestTrades:
    return service.list_trades(
        backtest_id,
        organization_id=tenant.organization_id,
        limit=limit,
        offset=offset,
    )
