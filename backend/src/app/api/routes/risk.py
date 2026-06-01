"""Risk engine API."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import RiskServiceDep
from app.schemas.risk import RiskCheckRequest, RiskCheckResult

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/check", response_model=RiskCheckResult, summary="Run deterministic risk check")
async def check_risk(request: RiskCheckRequest, risk_service: RiskServiceDep) -> RiskCheckResult:
    return risk_service.check(request)
