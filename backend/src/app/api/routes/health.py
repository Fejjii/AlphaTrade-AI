"""Health and readiness endpoints.

These are fully functional: ``/health`` is a cheap liveness probe that also
surfaces the trading-safety posture; ``/health/ready`` reports readiness based
on aggregated provider status.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.core.dependencies import ProviderRegistryDep, SettingsDep
from app.core.deploy_info import resolve_git_sha
from app.providers.base import ProviderHealth
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        app=settings.app_name,
        version=__version__,
        environment=settings.environment.value,
        execution_mode=settings.execution_mode.value,
        real_trading_enabled=settings.real_trading_enabled,
        must_verify_email=settings.must_verify_email,
        demo_seed_enabled=settings.demo_seed_enabled,
        git_sha=resolve_git_sha(),
        timestamp=datetime.now(UTC),
    )


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness(registry: ProviderRegistryDep, settings: SettingsDep) -> ReadinessResponse:
    from app.core.provider_policy import provider_fail_closed

    statuses = registry.statuses()
    unavailable = sum(1 for s in statuses if s.health is ProviderHealth.UNAVAILABLE)
    if provider_fail_closed(settings):
        # Staging/production: authoritative LLM/embeddings/vector must not be
        # silently degraded onto mocks or in-memory substitutes.
        critical = {"llm", "embeddings", "vector"}
        unavailable += sum(
            1
            for s in statuses
            if s.kind.value in critical
            and (s.is_mock or (s.health is ProviderHealth.DEGRADED and s.using_fallback))
        )
    ready = unavailable == 0
    return ReadinessResponse(
        status="ready" if ready else "degraded",
        ready=ready,
        providers_total=len(statuses),
        providers_unavailable=unavailable,
        timestamp=datetime.now(UTC),
    )
