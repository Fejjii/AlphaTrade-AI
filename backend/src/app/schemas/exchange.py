"""Schemas for the read-only exchange status endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.providers.base import ProviderStatus


class ExchangeStatusResponse(BaseModel):
    """Redaction-safe exchange connectivity posture for operators."""

    model_config = ConfigDict(extra="forbid")

    exchange_mode: str
    execution_mode: str
    real_trading_enabled: bool
    blofin_demo_enabled: bool
    demo_active: bool
    api_key_configured: bool
    api_secret_configured: bool
    api_passphrase_configured: bool
    credentials_configured: bool
    provider: ProviderStatus | None = Field(
        default=None,
        description="Exchange provider health; never contains secrets.",
    )
    generated_at: datetime
