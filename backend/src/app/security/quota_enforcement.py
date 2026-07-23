"""FastAPI dependencies for organization quota enforcement."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.params import Depends as DependsMarker

from app.core.dependencies import QuotaServiceDep
from app.core.errors import QuotaExceededError
from app.security.rbac import TraderDep
from app.services.quota_service import QuotaCheckResult


def require_quota(feature: str) -> DependsMarker:
    """Return a dependency that enforces organization quotas for ``feature``."""

    def _dependency(
        request: Request,
        tenant: TraderDep,
        quota_service: QuotaServiceDep,
    ) -> QuotaCheckResult:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        result = quota_service.check_feature(
            tenant.organization_id,
            feature,
            request_id=request_id,
            user_id=tenant.user_id,
        )
        if result.hard_blocked:
            raise QuotaExceededError(
                result.message,
                details={"feature": feature, "quota": "hard_limit"},
            )
        if result.soft_warning:
            request.state.quota_warning = result.message
        return result

    return DependsMarker(_dependency)


QuotaCheckDep = Annotated[QuotaCheckResult, Depends]
