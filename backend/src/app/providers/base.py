"""Base contracts shared by all external-service providers.

A provider wraps a single external capability (LLM, market data, exchange, ...).
Each provider reports a :class:`ProviderStatus` so the system can surface
degraded/fallback states to operators and the frontend, and can make safe
runtime decisions (e.g. block real execution when the exchange is unavailable).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ProviderKind(StrEnum):
    """Category of external capability a provider wraps."""

    LLM = "llm"
    EMBEDDINGS = "embeddings"
    VECTOR = "vector"
    EXCHANGE = "exchange"
    MARKET_DATA = "market_data"
    NEWS = "news"
    NOTIFICATIONS = "notifications"
    TRACING = "tracing"
    EMAIL = "email"
    BILLING = "billing"


class ProviderHealth(StrEnum):
    """Health of a provider at a point in time."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class ProviderStatus(BaseModel):
    """Point-in-time status report for a single provider."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: ProviderKind
    health: ProviderHealth
    using_fallback: bool = False
    is_mock: bool = False
    detail: str | None = Field(
        default=None, description="Human-readable status detail; must not contain secrets."
    )
    last_success_at: datetime | None = Field(
        default=None, description="Last successful provider request, when tracked."
    )
    error_message: str | None = Field(
        default=None, description="Redacted last error message, when available."
    )


@runtime_checkable
class Provider(Protocol):
    """Common interface every provider implementation must satisfy."""

    name: str
    kind: ProviderKind

    def status(self) -> ProviderStatus:
        """Return the current status without raising.

        Implementations must be resilient: a failing health probe should be
        reported as ``UNAVAILABLE``/``DEGRADED`` rather than propagating an
        exception, so status aggregation never crashes.
        """
        ...


class BaseMockProvider:
    """Reusable healthy mock provider used when no real credentials exist.

    Mock providers keep the system fully runnable and testable offline. They are
    explicitly flagged (``is_mock=True``) so their status is never mistaken for a
    live integration.
    """

    def __init__(self, name: str, kind: ProviderKind, detail: str | None = None) -> None:
        self.name = name
        self.kind = kind
        self._detail = detail or "Mock implementation (no live integration)."

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            using_fallback=False,
            is_mock=True,
            detail=self._detail,
        )
