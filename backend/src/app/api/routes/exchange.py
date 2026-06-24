"""Read-only exchange connectivity status (owner-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.dependencies import ProviderRegistryDep, SettingsDep
from app.core.exchange_readiness import exchange_provider_status
from app.schemas.exchange import ExchangeStatusResponse
from app.security.rbac import OwnerDep

router = APIRouter(prefix="/exchange", tags=["exchange"])


@router.get("/status", response_model=ExchangeStatusResponse, summary="Exchange status")
async def exchange_status(
    _tenant: OwnerDep,
    settings: SettingsDep,
    registry: ProviderRegistryDep,
) -> ExchangeStatusResponse:
    """Return redacted exchange posture and provider health (no secrets)."""
    return ExchangeStatusResponse(
        exchange_mode=settings.exchange_mode.value,
        execution_mode=settings.execution_mode.value,
        real_trading_enabled=settings.real_trading_enabled,
        blofin_demo_enabled=settings.blofin_demo_enabled,
        demo_active=settings.exchange_demo_active,
        api_key_configured=bool(settings.blofin_api_key.strip()),
        api_secret_configured=bool(settings.blofin_api_secret.strip()),
        api_passphrase_configured=bool(settings.blofin_api_passphrase.strip()),
        credentials_configured=settings.blofin_demo_configured,
        provider=exchange_provider_status(registry),
        generated_at=datetime.now(UTC),
    )
