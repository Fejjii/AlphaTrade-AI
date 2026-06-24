"""Exchange provider package (BloFin demo only).

This package adds read-only and (later) demo-execution access to the BloFin
*demo* venue. It is wired only when ``exchange_mode=paper_exchange_demo`` and a
demo host is allowlisted. Real/live exchange execution is never implemented.
"""

from __future__ import annotations

from app.providers.exchange.base import (
    AccountPermissions,
    ExchangeAccountProvider,
    ExchangeBalance,
    ExchangeExecutionProvider,
    ExchangeFill,
    ExchangeInstrument,
    ExchangeOrderRequest,
    ExchangeOrderResult,
    ExchangePositionData,
)
from app.providers.exchange.blofin_execution import (
    BloFinDemoExecutionProvider,
    DemoExecutionDisabledError,
)
from app.providers.exchange.errors import (
    ExchangeAuthError,
    ExchangeError,
    ExchangeRateLimitError,
    ExchangeRequestError,
    ExchangeUnavailableError,
)
from app.providers.exchange.factory import (
    ResolvedExchange,
    resolve_exchange_provider,
)

__all__ = [
    "AccountPermissions",
    "BloFinDemoExecutionProvider",
    "DemoExecutionDisabledError",
    "ExchangeAccountProvider",
    "ExchangeAuthError",
    "ExchangeBalance",
    "ExchangeError",
    "ExchangeExecutionProvider",
    "ExchangeFill",
    "ExchangeInstrument",
    "ExchangeOrderRequest",
    "ExchangeOrderResult",
    "ExchangePositionData",
    "ExchangeRateLimitError",
    "ExchangeRequestError",
    "ExchangeUnavailableError",
    "ResolvedExchange",
    "resolve_exchange_provider",
]
