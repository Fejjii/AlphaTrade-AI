"""Infrastructure providers (Redis) for status reporting only."""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus

logger = structlog.get_logger(__name__)


class RedisInfrastructureProvider:
    """Reports Redis connectivity for rate limiting — not a data provider."""

    name = "redis"
    kind = ProviderKind.TRACING

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._using_redis = False
        self._detail = "Redis not configured for rate limiting."

        if not settings.rate_limit_use_redis:
            self._detail = "Redis rate limiting disabled — in-memory limiter only."
            return

        try:
            import redis

            client = redis.from_url(
                settings.redis_url,
                socket_connect_timeout=settings.redis_connect_timeout_seconds,
                socket_timeout=settings.redis_connect_timeout_seconds,
                decode_responses=True,
            )
            client.ping()
            self._using_redis = True
            self._detail = f"Redis connected at {settings.redis_url} for rate limiting."
        except Exception as exc:
            if settings.rate_limit_allow_in_memory_fallback:
                self._detail = f"Redis unavailable ({exc}) — in-memory rate limit fallback active."
            else:
                self._detail = f"Redis unavailable and fallback disabled: {exc}"

    def status(self) -> ProviderStatus:
        if not self._settings.rate_limit_use_redis:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.HEALTHY,
                using_fallback=True,
                is_mock=True,
                detail=self._detail,
            )
        if self._using_redis:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.HEALTHY,
                using_fallback=False,
                is_mock=False,
                detail=self._detail,
            )
        health = (
            ProviderHealth.DEGRADED
            if self._settings.rate_limit_allow_in_memory_fallback
            else ProviderHealth.UNAVAILABLE
        )
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=health,
            using_fallback=not self._using_redis,
            is_mock=not self._using_redis,
            detail=self._detail,
        )
