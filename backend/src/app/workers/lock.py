"""Single-runner lock for the background worker.

Guarantees at most one worker performs a scan cycle at a time, even across
multiple processes/instances. Uses Redis ``SET NX EX`` when available, with a
process-local in-memory fallback so the worker stays runnable in development and
tests. The lock is fenced by a per-acquisition token so only the holder can
release it.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Protocol

import structlog

from app.core.config import Settings

logger = structlog.get_logger(__name__)


class WorkerLock(Protocol):
    """A best-effort distributed mutex with TTL-based expiry."""

    def try_acquire(self) -> str | None:
        """Return a fencing token if acquired, else ``None``."""
        ...

    def release(self, token: str) -> None:
        """Release the lock if (and only if) ``token`` still owns it."""
        ...


class InMemoryWorkerLock:
    """Process-local lock with TTL. Suitable for single-instance/dev/tests."""

    def __init__(self, key: str, ttl_seconds: int, *, clock=time.monotonic) -> None:
        self._key = key
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def try_acquire(self) -> str | None:
        with self._lock:
            now = self._clock()
            if self._token is not None and now < self._expires_at:
                return None
            token = uuid.uuid4().hex
            self._token = token
            self._expires_at = now + self._ttl
            return token

    def release(self, token: str) -> None:
        with self._lock:
            if self._token == token:
                self._token = None
                self._expires_at = 0.0


class RedisWorkerLock:
    """Cross-process lock backed by Redis ``SET NX EX``."""

    def __init__(self, client, key: str, ttl_seconds: int) -> None:
        self._client = client
        self._key = key
        self._ttl = ttl_seconds

    def try_acquire(self) -> str | None:
        token = uuid.uuid4().hex
        acquired = self._client.set(self._key, token, nx=True, ex=self._ttl)
        return token if acquired else None

    def release(self, token: str) -> None:
        # Compare-and-delete so we never release a lock we no longer hold.
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            self._client.eval(script, 1, self._key, token)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("worker_lock_release_failed", error_type=type(exc).__name__)


def build_worker_lock(settings: Settings) -> WorkerLock:
    """Build a Redis-backed lock when configured, else an in-memory lock."""
    key = f"worker:lock:{settings.worker_name}"
    ttl = settings.worker_lock_ttl_seconds
    if not settings.rate_limit_use_redis:
        return InMemoryWorkerLock(key, ttl)
    try:
        import redis

        client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_connect_timeout_seconds,
            decode_responses=True,
        )
        client.ping()
        logger.info("worker_lock_redis_enabled")
        return RedisWorkerLock(client, key, ttl)
    except Exception as exc:
        logger.warning("worker_lock_redis_unavailable", error_type=type(exc).__name__)
        return InMemoryWorkerLock(key, ttl)
