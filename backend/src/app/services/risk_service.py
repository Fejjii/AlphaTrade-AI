"""Risk service: orchestrates deterministic checks and optional event persistence."""

from __future__ import annotations

from app.schemas.risk import RiskCheckRequest, RiskCheckResult
from app.services.risk.engine import RiskEngine
from app.services.risk.limits import RiskLimits
from app.services.risk.rules import RiskEvaluationContext


class RiskService:
    """Business-facing API for the deterministic risk engine."""

    def __init__(self, engine: RiskEngine | None = None) -> None:
        self._engine = engine or RiskEngine()

    def check(
        self,
        request: RiskCheckRequest,
        *,
        context: RiskEvaluationContext | None = None,
    ) -> RiskCheckResult:
        """Run all risk rules and return the aggregated verdict."""
        return self._engine.evaluate(request, context=context)

    @property
    def limits(self) -> RiskLimits:
        return self._engine.limits
