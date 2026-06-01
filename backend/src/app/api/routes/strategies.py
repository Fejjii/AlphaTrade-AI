"""Strategy module API."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import StrategyServiceDep
from app.schemas.common import StrategyId
from app.schemas.strategy import StrategyEvaluateRequest, StrategyEvaluateResponse
from app.strategies.base import StrategyEvaluationInput

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", summary="List registered strategy modules")
async def list_strategies(service: StrategyServiceDep) -> list[StrategyId]:
    return service.list_strategy_ids()


@router.post("/evaluate", response_model=StrategyEvaluateResponse, summary="Evaluate a strategy")
async def evaluate_strategy(
    body: StrategyEvaluateRequest, service: StrategyServiceDep
) -> StrategyEvaluateResponse:
    data = StrategyEvaluationInput(
        symbol=body.symbol,
        timeframe=body.timeframe,
        close=body.close,
        volume=body.volume,
        funding_rate=body.funding_rate,
        rsi=body.rsi,
        ema_fast=body.ema_fast,
        ema_slow=body.ema_slow,
        htf_trend=body.htf_trend,
        liquidity_sweep_detected=body.liquidity_sweep_detected,
        momentum_exhausted=body.momentum_exhausted,
        at_confluence_level=body.at_confluence_level,
        green_day_active=body.green_day_active,
        stress_score=body.stress_score,
    )
    signal = service.evaluate(body.strategy_id, data)
    return StrategyEvaluateResponse(strategy_id=body.strategy_id, signal=signal)
