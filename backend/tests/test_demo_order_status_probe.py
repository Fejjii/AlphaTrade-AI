"""Tests for bounded read-only demo order status probes."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.demo_order_status import (
    cancelled_status_from_cancel_audit,
    probe_demo_order_status_with_retry,
)
from app.providers.exchange.base import ExchangeOrderResult
from app.providers.exchange.errors import ExchangeError


def _result(order_id: str = "ord-1") -> ExchangeOrderResult:
    return ExchangeOrderResult(
        exchange_order_id=order_id,
        client_order_id="client-1",
        status="live",
        filled_size=Decimal("0"),
        average_price=None,
    )


def test_probe_retries_transient_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fn() -> ExchangeOrderResult:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ExchangeError("transient venue timeout")
        return _result()

    monkeypatch.setattr("app.core.demo_order_status.time.sleep", lambda _s: None)
    result = probe_demo_order_status_with_retry(
        fn,
        max_attempts=3,
        retry_delay_seconds=0.0,
    )
    assert result.status == "live"
    assert calls["n"] == 3


def test_probe_raises_after_bounded_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.demo_order_status.time.sleep", lambda _s: None)

    def always_fail() -> ExchangeOrderResult:
        raise ExchangeError("still failing")

    with pytest.raises(ExchangeError, match="still failing"):
        probe_demo_order_status_with_retry(
            always_fail,
            max_attempts=2,
            retry_delay_seconds=0.0,
        )


def test_cancelled_status_from_cancel_audit() -> None:
    result = cancelled_status_from_cancel_audit(exchange_order_id="1000131288930")
    assert result.exchange_order_id == "1000131288930"
    assert result.status == "cancelled"
    assert result.filled_size == Decimal("0")
