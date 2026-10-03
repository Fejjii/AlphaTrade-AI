"""Explicit demo account sync capability, independent of execution credentials."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import ExchangeMode, ExecutionMode, Settings
from app.core.errors import ExchangeDemoInactiveError
from app.core.exchange_safety import assert_demo_host
from app.providers.exchange.blofin_account import BloFinAccountProvider
from app.providers.exchange.blofin_client import BloFinClient

_ACCOUNT_PATHS = frozenset(
    {"/api/v1/account/balance", "/api/v1/account/positions", "/api/v1/user/query-apikey"}
)


class BloFinReadOnlyClient(BloFinClient):
    """Transport with no order, withdrawal or transfer capability."""

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        if method.upper() != "GET" or path not in _ACCOUNT_PATHS or body is not None:
            raise ExchangeDemoInactiveError("BloFin sync permits account GET requests only.")
        data = super().request(method, path, params=params, signed=signed)
        if not isinstance(data, list | dict) or (
            path == "/api/v1/account/positions" and not isinstance(data, list)
        ):
            raise ExchangeDemoInactiveError("BloFin account response has an invalid shape.")
        return data


def get_readonly_account_provider(
    settings: Settings, *, transport: httpx.BaseTransport | None = None
) -> BloFinAccountProvider:
    """Release only the separate sync secrets after an explicit safe opt-in."""
    if (
        not settings.blofin_readonly_sync_enabled
        or settings.execution_mode is not ExecutionMode.PAPER
        or settings.enable_real_trading
        or settings.exchange_mode is not ExchangeMode.PAPER_INTERNAL
    ):
        raise ExchangeDemoInactiveError("BloFin read-only sync is not active in paper_internal.")
    credentials = (
        settings.blofin_readonly_api_key.strip(),
        settings.blofin_readonly_api_secret.strip(),
        settings.blofin_readonly_api_passphrase.strip(),
    )
    if not all(credentials):
        raise ExchangeDemoInactiveError("Dedicated BloFin read-only sync credentials are missing.")
    assert_demo_host(settings.blofin_demo_rest_base_url)
    url = httpx.URL(settings.blofin_demo_rest_base_url)
    if (
        url.scheme != "https"
        or url.userinfo
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ExchangeDemoInactiveError("BloFin sync requires a plain HTTPS demo origin.")
    return BloFinAccountProvider(
        BloFinReadOnlyClient(
            base_url=settings.blofin_demo_rest_base_url,
            api_key=credentials[0],
            api_secret=credentials[1],
            api_passphrase=credentials[2],
            timeout_seconds=settings.blofin_request_timeout_seconds,
            max_retries=settings.blofin_max_retries,
            rate_limit_requests_per_second=settings.blofin_rate_limit_requests_per_second,
            transport=transport,
        )
    )
