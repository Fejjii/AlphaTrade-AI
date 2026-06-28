"""Bounded read-only retry for BloFin demo order status probes."""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal

from app.providers.exchange.base import ExchangeOrderResult
from app.providers.exchange.errors import ExchangeError

DEFAULT_STATUS_PROBE_ATTEMPTS = 3
DEFAULT_STATUS_PROBE_DELAY_SECONDS = 0.5


def probe_demo_order_status_with_retry(
    fn: Callable[[], ExchangeOrderResult],
    *,
    max_attempts: int = DEFAULT_STATUS_PROBE_ATTEMPTS,
    retry_delay_seconds: float = DEFAULT_STATUS_PROBE_DELAY_SECONDS,
) -> ExchangeOrderResult:
    """Call venue ``get_order`` with bounded retry on transient ``ExchangeError``.

    Read-only: never places or cancels orders. Raises the last error when all
    attempts fail.
    """
    last_exc: ExchangeError | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except ExchangeError as exc:
            last_exc = exc
            if attempt + 1 < max_attempts:
                time.sleep(retry_delay_seconds)
    assert last_exc is not None
    raise last_exc


def cancelled_status_from_cancel_audit(
    *,
    exchange_order_id: str,
) -> ExchangeOrderResult:
    """Synthetic cancelled status when venue probe fails but cancel was audited."""
    return ExchangeOrderResult(
        exchange_order_id=exchange_order_id,
        client_order_id=None,
        status="cancelled",
        filled_size=Decimal("0"),
        average_price=None,
    )
