"""Authenticated BloFin *demo* REST client.

Safety-critical guarantees:

* Every request asserts the configured base URL is an allowlisted BloFin demo
  host (defense in depth on top of settings validation).
* Credentials are HMAC-signed and never logged; all error text is redacted.
* Transient failures (network, 5xx, rate limit) are retried with bounded,
  jittered backoff. Auth and other 4xx errors are not retried.

This module performs no order placement; it is the transport used by the
read-only account/market-data providers and (later) the demo execution provider.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.core.exchange_safety import assert_demo_host
from app.guardrails.redaction import redact_text
from app.providers.exchange.errors import (
    ExchangeAuthError,
    ExchangeError,
    ExchangeRateLimitError,
    ExchangeRequestError,
    ExchangeUnavailableError,
    VenueErrorDetails,
)
from app.providers.exchange.venue_diagnostics import endpoint_label

logger = structlog.get_logger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _now_ms() -> str:
    return str(int(datetime.now(UTC).timestamp() * 1000))


class BloFinClient:
    """Minimal signed REST client for the BloFin demo venue."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        rate_limit_requests_per_second: int = 5,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], str] = _now_ms,
        nonce_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
        jitter: float = 0.1,
    ) -> None:
        # Last-line guard: never construct a client against a non-demo host.
        assert_demo_host(base_url)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._api_passphrase = api_passphrase
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._min_interval = 1.0 / max(rate_limit_requests_per_second, 1)
        self._transport = transport
        self._sleeper = sleeper
        self._clock = clock
        self._nonce_factory = nonce_factory
        self._jitter = jitter
        self._last_request_at: float = 0.0
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None

    @property
    def last_success_at(self) -> datetime | None:
        return self._last_success_at

    @property
    def last_error(self) -> str | None:
        return redact_text(self._last_error) if self._last_error else None

    def _sign(self, *, method: str, path: str, timestamp: str, nonce: str, body: str) -> str:
        """BloFin signature: base64(hex(HMAC_SHA256(secret, path+method+ts+nonce+body)))."""
        prehash = f"{path}{method.upper()}{timestamp}{nonce}{body}"
        digest = hmac.new(self._api_secret, prehash.encode("utf-8"), hashlib.sha256).hexdigest()
        return base64.b64encode(digest.encode("utf-8")).decode("utf-8")

    def _auth_headers(self, *, method: str, path: str, body: str) -> dict[str, str]:
        timestamp = self._clock()
        nonce = self._nonce_factory()
        return {
            "ACCESS-KEY": self._api_key,
            "ACCESS-SIGN": self._sign(
                method=method, path=path, timestamp=timestamp, nonce=nonce, body=body
            ),
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-NONCE": nonce,
            "ACCESS-PASSPHRASE": self._api_passphrase,
            "Content-Type": "application/json",
        }

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            self._sleeper(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _client(self) -> httpx.Client:
        if self._transport is not None:
            return httpx.Client(
                base_url=self._base_url, timeout=self._timeout, transport=self._transport
            )
        return httpx.Client(base_url=self._base_url, timeout=self._timeout)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        """Execute a request and return the venue's ``data`` payload.

        Raises a typed :class:`ExchangeError` subclass on failure. The error
        message is redacted before being stored.
        """
        # Re-assert demo host on every call; configuration cannot drift to prod.
        assert_demo_host(self._base_url)

        body_str = json.dumps(body, separators=(",", ":")) if body is not None else ""
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= self._max_retries:
            self._throttle()
            try:
                headers = (
                    self._auth_headers(method=method, path=path, body=body_str) if signed else {}
                )
                with self._client() as client:
                    response = client.request(
                        method.upper(),
                        path,
                        params=params,
                        content=body_str if body_str else None,
                        headers=headers,
                    )
                return self._handle_response(response, method=method, path=path)
            except (ExchangeRateLimitError, ExchangeUnavailableError) as exc:
                last_exc = exc
                self._last_error = redact_text(str(exc))
                attempt += 1
                if attempt > self._max_retries:
                    break
                self._backoff(attempt)
            except httpx.HTTPError as exc:
                last_exc = ExchangeUnavailableError(redact_text(str(exc)))
                self._last_error = redact_text(str(exc))
                attempt += 1
                if attempt > self._max_retries:
                    break
                self._backoff(attempt)

        logger.warning(
            "blofin_request_failed",
            method=method,
            path=path,
            endpoint=endpoint_label(method, path),
            error=self._last_error,
        )
        endpoint = endpoint_label(method, path)
        details = VenueErrorDetails(endpoint_name=endpoint)
        if isinstance(last_exc, ExchangeError) and last_exc.details is not None:
            details = VenueErrorDetails(
                venue_error_code=last_exc.details.venue_error_code,
                venue_error_message=last_exc.details.venue_error_message,
                http_status=last_exc.details.http_status,
                endpoint_name=endpoint,
            )
        if last_exc is not None and isinstance(last_exc, ExchangeError):
            raise type(last_exc)(str(last_exc), details=details) from last_exc
        raise ExchangeUnavailableError(
            "BloFin request failed after retries.",
            details=details,
        )

    def _backoff(self, attempt: int) -> None:
        delay = (2 ** (attempt - 1)) * self._min_interval
        # Deterministic jitter (no RNG) keeps tests reproducible.
        self._sleeper(delay * (1 + self._jitter))

    def _handle_response(self, response: httpx.Response, *, method: str, path: str) -> Any:
        endpoint = endpoint_label(method, path)
        status = response.status_code
        if status == 429:
            raise ExchangeRateLimitError(
                "BloFin rate limit exceeded.",
                details=VenueErrorDetails(http_status=status, endpoint_name=endpoint),
            )
        if status in _RETRYABLE_STATUS:
            raise ExchangeUnavailableError(
                f"BloFin server error: HTTP {status}.",
                details=VenueErrorDetails(http_status=status, endpoint_name=endpoint),
            )
        if status in (401, 403):
            self._last_error = "BloFin authentication/permission failure."
            raise ExchangeAuthError(
                self._last_error,
                details=VenueErrorDetails(
                    venue_error_code=str(status),
                    venue_error_message=self._last_error,
                    http_status=status,
                    endpoint_name=endpoint,
                ),
            )
        if status >= 400:
            self._last_error = f"BloFin rejected request: HTTP {status}."
            raise ExchangeRequestError(
                self._last_error,
                details=VenueErrorDetails(
                    venue_error_code=str(status),
                    venue_error_message=self._last_error,
                    http_status=status,
                    endpoint_name=endpoint,
                ),
            )

        try:
            payload = response.json()
        except Exception as exc:  # malformed body
            raise ExchangeUnavailableError(
                f"BloFin returned non-JSON body: {redact_text(str(exc))}",
                details=VenueErrorDetails(http_status=status, endpoint_name=endpoint),
            ) from exc

        # BloFin envelope: {"code": "0", "msg": "...", "data": ...}; code 0 == ok.
        code = str(payload.get("code", "0"))
        if code != "0":
            msg = redact_text(str(payload.get("msg", "")))
            details = VenueErrorDetails(
                venue_error_code=code,
                venue_error_message=msg or None,
                http_status=status,
                endpoint_name=endpoint,
            )
            if code in ("401", "403"):
                self._last_error = f"BloFin auth error {code}: {msg}"
                raise ExchangeAuthError(self._last_error, details=details)
            self._last_error = f"BloFin error {code}: {msg}"
            raise ExchangeRequestError(self._last_error, details=details)

        self._last_success_at = datetime.now(UTC)
        self._last_error = None
        return payload.get("data")
