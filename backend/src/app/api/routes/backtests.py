"""Backtest API (Slice 34)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.dependencies import BacktestServiceDep
from app.schemas.backtest import BacktestRun
from app.security.rbac import TraderDep

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("/{backtest_id}", response_model=BacktestRun, summary="Get backtest run")
async def get_backtest(
    backtest_id: uuid.UUID,
    tenant: TraderDep,
    service: BacktestServiceDep,
) -> BacktestRun:
    return service.get(backtest_id, organization_id=tenant.organization_id)
