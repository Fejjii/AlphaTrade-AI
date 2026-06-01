"""Schemas for health and provider-status endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.providers.base import ProviderStatus


class HealthResponse(BaseModel):
    """Basic liveness payload plus trading-safety posture."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    app: str
    version: str
    environment: str
    execution_mode: str
    real_trading_enabled: bool
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness payload: ``ready`` only when no provider is unavailable."""

    model_config = ConfigDict(extra="forbid")

    status: str
    ready: bool
    providers_total: int
    providers_unavailable: int
    timestamp: datetime


class ProviderStatusResponse(BaseModel):
    """Aggregated provider statuses for operators and the frontend."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    providers: list[ProviderStatus] = Field(default_factory=list)
