"""Risk engine API."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import LossAcceptanceServiceDep, PositionSizingServiceDep, RiskServiceDep
from app.schemas.position_sizing import (
    LossAcceptanceRequest,
    LossAcceptanceResult,
    PositionSizingRequest,
    PositionSizingResult,
)
from app.schemas.risk import RiskCheckRequest, RiskCheckResult

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/check", response_model=RiskCheckResult, summary="Run deterministic risk check")
async def check_risk(request: RiskCheckRequest, risk_service: RiskServiceDep) -> RiskCheckResult:
    return risk_service.check(request)


@router.post("/size", response_model=PositionSizingResult, summary="Calculate position size v2")
async def calculate_position_size(
    request: PositionSizingRequest,
    sizing_service: PositionSizingServiceDep,
) -> PositionSizingResult:
    return sizing_service.calculate(request)


@router.post(
    "/loss-acceptance",
    response_model=LossAcceptanceResult,
    summary="Evaluate loss acceptance gate",
)
async def evaluate_loss_acceptance(
    request: LossAcceptanceRequest,
    loss_service: LossAcceptanceServiceDep,
) -> LossAcceptanceResult:
    return loss_service.evaluate(
        planned_loss_amount=request.planned_loss_amount,
        request=request,
    )
