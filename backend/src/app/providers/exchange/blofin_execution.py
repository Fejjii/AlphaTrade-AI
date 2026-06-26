"""BloFin DEMO-only order execution provider (Slice 61).

This provider places orders on the BloFin *demo* venue exclusively. It enforces,
on every call and before any network I/O:

* real trading must be disabled (``real_trading_enabled`` is False),
* the exchange must be in ``paper_exchange_demo`` mode, and
* the client base URL must be an allowlisted demo host (via the client guard).

There is no code path here that can place a real-money order.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from app.guardrails.redaction import redact_text
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.exchange.base import (
    ExchangeFill,
    ExchangeOrderRequest,
    ExchangeOrderResult,
)
from app.providers.exchange.blofin_account import BloFinAccountProvider
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.errors import ExchangeRequestError, VenueErrorDetails
from app.providers.exchange.position_side import resolve_position_side

logger = structlog.get_logger(__name__)


class DemoExecutionDisabledError(RuntimeError):
    """Raised when demo execution is invoked in an unsafe configuration."""


class BloFinDemoExecutionProvider:
    """Places orders on the BloFin demo venue only."""

    name = "blofin-demo-execution"
    kind = ProviderKind.EXCHANGE

    def __init__(
        self,
        client: BloFinClient,
        account: BloFinAccountProvider,
        *,
        real_trading_enabled: bool,
        exchange_demo_active: bool,
    ) -> None:
        self._client = client
        self._account = account
        self._real_trading_enabled = real_trading_enabled
        self._exchange_demo_active = exchange_demo_active

    def _assert_safe(self) -> None:
        # Hard gates, re-checked on every call. Order matters: real-trading first.
        if self._real_trading_enabled:
            raise DemoExecutionDisabledError(
                "Refusing demo execution: real_trading_enabled is True."
            )
        if not self._exchange_demo_active:
            raise DemoExecutionDisabledError(
                "Refusing demo execution: exchange_mode is not paper_exchange_demo."
            )

    def place_order(self, request: ExchangeOrderRequest) -> ExchangeOrderResult:
        """Place a demo order; raises on unsafe config or venue rejection."""
        self._assert_safe()
        position_mode = self._account.get_position_mode().position_mode
        position_side = resolve_position_side(
            position_mode,
            request.side,
            reduce_only=request.reduce_only,
        )
        body: dict[str, Any] = {
            "instId": request.inst_id,
            "marginMode": "cross",
            "positionSide": position_side,
            "side": request.side.value,
            "orderType": request.order_type.value,
            "size": str(request.size),
        }
        if request.price is not None:
            body["price"] = str(request.price)
        if request.reduce_only:
            body["reduceOnly"] = "true"
        if request.client_order_id:
            body["clientOrderId"] = request.client_order_id

        try:
            data = self._client.request("POST", "/api/v1/trade/order", body=body, signed=True)
            result = self._parse_order_result(data, request)
        except ExchangeRequestError as exc:
            if exc.position_mode is None:
                raise ExchangeRequestError(
                    str(exc),
                    details=exc.details,
                    position_mode=position_mode,
                    position_side=position_side,
                ) from exc
            raise
        return ExchangeOrderResult(
            exchange_order_id=result.exchange_order_id,
            client_order_id=result.client_order_id,
            status=result.status,
            filled_size=result.filled_size,
            average_price=result.average_price,
            fills=result.fills,
            position_mode=position_mode,
            position_side=position_side,
        )

    def get_order(self, *, inst_id: str, exchange_order_id: str) -> ExchangeOrderResult:
        self._assert_safe()
        data = self._client.request(
            "GET",
            "/api/v1/trade/order",
            params={"instId": inst_id, "orderId": exchange_order_id},
            signed=True,
        )
        return self._parse_order_result(data, None)

    def cancel_order(self, *, inst_id: str, exchange_order_id: str) -> None:
        self._assert_safe()
        self._client.request(
            "POST",
            "/api/v1/trade/cancel-order",
            body={"instId": inst_id, "orderId": exchange_order_id},
            signed=True,
        )

    @staticmethod
    def _parse_order_result(data: Any, request: ExchangeOrderRequest | None) -> ExchangeOrderResult:
        row = data[0] if isinstance(data, list) and data else data
        if not isinstance(row, dict):
            row = {}
        nested_code = row.get("code")
        if nested_code is not None and str(nested_code) != "0":
            nested_msg = redact_text(str(row.get("msg", "")))
            code_str = str(nested_code)
            raise ExchangeRequestError(
                f"BloFin error {code_str}: {nested_msg}",
                details=VenueErrorDetails(
                    venue_error_code=code_str,
                    venue_error_message=nested_msg or None,
                ),
            )
        order_id = str(row.get("orderId", row.get("ordId", "")))
        filled = Decimal(str(row.get("filledSize", row.get("accFillSz", "0")) or "0"))
        avg_raw = row.get("averagePrice", row.get("avgPx"))
        average = Decimal(str(avg_raw)) if avg_raw not in (None, "") else None
        fills = tuple(
            ExchangeFill(
                fill_id=str(f.get("tradeId", "")),
                order_id=order_id,
                price=Decimal(str(f.get("fillPrice", f.get("fillPx", "0")) or "0")),
                size=Decimal(str(f.get("fillSize", f.get("fillSz", "0")) or "0")),
                fee=Decimal(str(f.get("fee", "0") or "0")),
                fee_currency=f.get("feeCurrency"),
            )
            for f in (row.get("fills", []) if isinstance(row.get("fills"), list) else [])
            if isinstance(f, dict)
        )
        return ExchangeOrderResult(
            exchange_order_id=order_id,
            client_order_id=row.get("clientOrderId")
            or (request.client_order_id if request else None),
            status=str(row.get("state", row.get("status", "live"))),
            filled_size=filled,
            average_price=average,
            fills=fills,
        )

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY,
            using_fallback=False,
            is_mock=False,
            detail="BloFin demo execution (paper only — never real money).",
            last_success_at=self._client.last_success_at,
            error_message=self._client.last_error,
        )
