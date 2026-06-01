"""Optional access-token denylist (Redis with in-memory fallback)."""

from __future__ import annotations

import threading
import time
from typing import Protocol

import structlog

from app.core.config import Settings

logger = structlog.get_logger(__name__)


class AccessTokenDenylist(Protocol):
    def add(self, jti: str, *, ttl_seconds: int) -> None: ...

    def is_denied(self, jti: str) -> bool: ...


class _InMemoryDenylist:
    def __init__(self) -> None:
        self._entries: dict[str, float] = {}
        self._lock = threading.Lock()

    def add(self, jti: str, *, ttl_seconds: int) -> None:
        expires = time.monotonic() + max(ttl_seconds, 1)
        with self._lock:
            self._entries[jti] = expires
            self._purge_locked()

    def is_denied(self, jti: str) -> bool:
        with self._lock:
            self._purge_locked()
            return jti in self._entries

    def _purge_locked(self) -> None:
        now = time.monotonic()
        expired = [key for key, exp in self._entries.items() if exp <= now]
        for key in expired:
            del self._entries[key]


class _RedisDenylist:
    def __init__(self, settings: Settings) -> None:
        import redis

        self._client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_connect_timeout_seconds,
            decode_responses=True,
        )
        self._prefix = "auth:deny:"

    def add(self, jti: str, *, ttl_seconds: int) -> None:
        try:
            self._client.setex(f"{self._prefix}{jti}", max(ttl_seconds, 1), "1")
        except Exception as exc:
            logger.warning("access_token_denylist_add_failed", error_type=type(exc).__name__)

    def is_denied(self, jti: str) -> bool:
        try:
            return bool(self._client.exists(f"{self._prefix}{jti}"))
        except Exception:
            return False


class NoOpDenylist:
    def add(self, jti: str, *, ttl_seconds: int) -> None:
        return

    def is_denied(self, jti: str) -> bool:
        return False


_denylist: AccessTokenDenylist | None = None
_denylist_lock = threading.Lock()


def get_access_token_denylist(settings: Settings) -> AccessTokenDenylist:
    """Return a process-wide denylist backend."""
    global _denylist
    if not settings.access_token_denylist_enabled:
        return NoOpDenylist()
    with _denylist_lock:
        if _denylist is not None:
            return _denylist
        if settings.access_token_denylist_use_redis:
            try:
                _denylist = _RedisDenylist(settings)
                logger.info("access_token_denylist_backend", backend="redis")
                return _denylist
            except Exception as exc:
                if not settings.rate_limit_allow_in_memory_fallback:
                    raise
                logger.warning(
                    "access_token_denylist_redis_unavailable",
                    error_type=type(exc).__name__,
                )
        _denylist = _InMemoryDenylist()
        logger.info("access_token_denylist_backend", backend="memory")
        return _denylist


def reset_access_token_denylist() -> None:
    """Clear cached denylist (tests)."""
    global _denylist
    with _denylist_lock:
        _denylist = None
