"""GET-only HTTP client for public perpetual market data.

POST/PUT/PATCH/DELETE and any order, position, or account path are rejected.
Spot and Coin-M hosts cannot be used as a silent substitute for USD-M.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from app.market_contracts.errors import (
    NetworkMutationForbiddenError,
    RegionalProviderFailureError,
    SpotFallbackRejectedError,
    WrongMarketError,
)

ALLOWED_PATHS = frozenset(
    {
        "/fapi/v1/ping",
        "/fapi/v1/time",
        "/fapi/v1/exchangeInfo",
        "/fapi/v1/klines",
        "/fapi/v1/aggTrades",
    }
)
SPOT_HOST_MARKERS = (
    "api.binance.com",
    "api1.binance.com",
    "api2.binance.com",
    "api3.binance.com",
    "api4.binance.com",
    "data-api.binance.vision",
)
COINM_HOST_MARKERS = ("dapi.binance.com",)
SPOT_PATH_PREFIXES = ("/api/v3/", "/api/v1/")
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"})
REGIONAL_STATUS_CODES = frozenset({401, 403, 418, 451})


class ReadOnlyHttpGetClient:
    """Allowlisted HTTPS GET client. Never sends credentials or mutations."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": "AlphaTradeAI-perpetual-evidence/read-only"},
        )
        self._assert_base_url()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_json(self, path: str, params: Mapping[str, str | int] | None = None) -> Any:
        return self.request_json("GET", path, params=params)

    def request_json(
        self,
        method: str,
        path: str,
        params: Mapping[str, str | int] | None = None,
    ) -> Any:
        normalized_method = method.upper()
        if normalized_method in MUTATING_METHODS or normalized_method != "GET":
            raise NetworkMutationForbiddenError(
                f"Perpetual evidence adapter forbids HTTP {normalized_method}."
            )
        normalized_path = self._normalize_path(path)
        if normalized_path not in ALLOWED_PATHS:
            raise NetworkMutationForbiddenError(
                f"Path {normalized_path} is not on the read-only perpetual allowlist."
            )
        url = urljoin(self._base_url + "/", normalized_path.lstrip("/"))
        self._assert_url(url)
        try:
            response = self._client.get(url, params=dict(params or {}))
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
            raise RegionalProviderFailureError(
                "Preferred Binance USD-M perpetual source is unreachable."
            ) from exc
        if response.status_code in REGIONAL_STATUS_CODES:
            raise RegionalProviderFailureError(
                f"Preferred Binance USD-M source rejected the runtime region "
                f"(HTTP {response.status_code})."
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RegionalProviderFailureError(
                f"Preferred Binance USD-M source returned HTTP {response.status_code}."
            ) from exc
        return response.json()

    def _normalize_path(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            parsed = urlsplit(path)
            self._assert_url(path)
            path = parsed.path
        if not path.startswith("/"):
            path = "/" + path
        for prefix in SPOT_PATH_PREFIXES:
            if path.startswith(prefix):
                raise SpotFallbackRejectedError(
                    "Spot REST paths cannot satisfy perpetual evidence."
                )
        return path

    def _assert_base_url(self) -> None:
        parsed = urlsplit(self._base_url)
        host = (parsed.hostname or "").lower()
        if not host:
            raise WrongMarketError("Perpetual evidence base URL is missing a host.")
        self._assert_host(host)
        if parsed.scheme not in {"https", "http"}:
            raise WrongMarketError("Perpetual evidence URL scheme is not supported.")

    def _assert_url(self, url: str) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        self._assert_host(host)
        path = parsed.path or "/"
        for prefix in SPOT_PATH_PREFIXES:
            if path.startswith(prefix):
                raise SpotFallbackRejectedError(
                    "Spot REST paths cannot satisfy perpetual evidence."
                )

    def _assert_host(self, host: str) -> None:
        if any(host == marker or host.endswith("." + marker) for marker in SPOT_HOST_MARKERS):
            raise SpotFallbackRejectedError(
                "Spot host cannot be used as a Binance USD-M perpetual evidence source."
            )
        if any(host == marker or host.endswith("." + marker) for marker in COINM_HOST_MARKERS):
            raise WrongMarketError("Coin-M host cannot substitute for USD-M perpetual evidence.")
