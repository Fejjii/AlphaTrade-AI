"""Strict BloFin demo adapter for the canonical durable execution protocol.

All prices and fills come from venue responses. Submission only acknowledges an
order: reconciliation reads fills and attached protection separately. No retry,
account-setting mutation, internal fill fallback, or real venue is supported.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.providers.exchange.blofin_account import BloFinAccountProvider
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.errors import ExchangeRequestError
from app.providers.exchange.mapping import to_blofin_inst_id
from app.schemas.trade_plan import EntrySide, TradePlanRevision

if TYPE_CHECKING:
    from app.providers.exchange.governed_blofin_exit import VerifiedDemoExit


@dataclass(frozen=True)
class DemoVenueSnapshot:
    instrument: str
    price: Decimal
    observed_at: datetime
    tick: Decimal
    lot: Decimal
    minimum: Decimal
    multiplier: Decimal
    equity: Decimal
    available: Decimal
    maximum: Decimal


@dataclass(frozen=True)
class DemoFill:
    identity: str
    quantity: Decimal
    price: Decimal
    occurred_at: datetime
    fee: Decimal


@dataclass(frozen=True)
class DemoOrderEvidence:
    order_id: str
    client_order_id: str
    status: str
    fills: tuple[DemoFill, ...]
    protected: bool
    protection_status: str
    protection_order_ids: tuple[str, ...] = ()


def _rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        return [data]
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _account_rows(data: Any) -> list[dict[str, Any]]:
    """A malformed or possibly truncated account read cannot prove absence."""
    if (
        not isinstance(data, list)
        or len(data) >= 100
        or any(not isinstance(row, dict) for row in data)
    ):
        raise ValueError("Demo account state incomplete or unreadable.")
    return data


def _positive(value: Any) -> Decimal:
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("Positive finite venue value required.")
    return parsed


def _time(value: Any) -> datetime:
    # Venue occurrence timestamps are mandatory. Observation time cannot replace them.
    return datetime.fromtimestamp(int(str(value)) / 1000, tz=UTC)


class GovernedBloFinDemoProvider:
    """Uses an allowlisted demo client and verifies current permissions before send."""

    def __init__(
        self, client: BloFinClient, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._client = client
        self._account = BloFinAccountProvider(client)
        self._clock = clock

    def snapshot(self, *, symbol: str, now: datetime) -> DemoVenueSnapshot:
        self.verify_permissions()
        if self._account.get_position_mode().position_mode != "net_mode":
            raise ValueError("Governed demo requires the existing NET account mode.")
        instrument = to_blofin_inst_id(symbol)
        rows = _rows(
            self._client.request("GET", "/api/v1/market/instruments", params={"instId": instrument})
        )
        row = next((r for r in rows if r.get("instId") == instrument), None)
        if row is None or row.get("state") != "live":
            raise ValueError("Demo instrument unavailable.")
        if (
            row.get("quoteCurrency") != "USDT"
            or row.get("baseCurrency") != symbol.removesuffix("USDT")
            or row.get("contractType") != "linear"
        ):
            raise ValueError("Only base-valued linear USDT contracts are supported.")
        if row.get("instType") not in {"SWAP", "PERPETUAL"}:
            raise ValueError("Demo perpetual instrument required.")
        leverage = self._account.get_leverage_info(inst_id=instrument, margin_mode="cross")
        if leverage.leverage != Decimal("1"):
            raise ValueError("Demo account must already use leverage 1; no leverage mutation.")
        self.verify_flat_account()
        balances = self._account.get_balances()
        balance = next((b for b in balances if b.asset == "USDT"), None)
        if balance is None or balance.available <= 0 or balance.total <= 0:
            raise ValueError("Demo USDT equity unavailable.")
        ticker = _rows(
            self._client.request("GET", "/api/v1/market/tickers", params={"instId": instrument})
        )
        # Preflight IO can outlast the caller's timestamp. Check freshness at receipt.
        now = self._clock()
        quote = next((r for r in ticker if r.get("instId") == instrument), None)
        if quote is None:
            raise ValueError("Demo quote unavailable.")
        observed = _time(quote.get("ts"))
        if not 0 <= (now - observed).total_seconds() < 10:
            raise ValueError("Demo quote stale or future dated.")
        return DemoVenueSnapshot(
            instrument=instrument,
            price=_positive(quote.get("last")),
            observed_at=observed,
            tick=_positive(row.get("tickSize")),
            lot=_positive(row.get("lotSize")),
            minimum=_positive(row.get("minSize")),
            multiplier=_positive(row.get("contractValue")),
            equity=balance.total,
            available=balance.available,
            maximum=_positive(row.get("maxMarketSize")),
        )

    def verify_flat_account(self) -> None:
        """Account-wide proof, including orders on other watchlist markets."""
        positions = _account_rows(
            self._client.request("GET", "/api/v1/account/positions", signed=True)
        )
        for position in positions:
            quantity = Decimal(str(position.get("positions")))
            if not quantity.is_finite() or quantity != 0:
                raise ValueError("Demo position already open or unreadable; new entry refused.")
        for endpoint in ("orders-pending", "orders-tpsl-pending"):
            pending = _account_rows(
                self._client.request(
                    "GET", f"/api/v1/trade/{endpoint}", params={"limit": "100"}, signed=True
                )
            )
            if pending:
                raise ValueError("Demo pending orders or protection; new entry refused.")

    def verify_permissions(self) -> None:
        permissions = self._account.get_account_permissions()
        if (
            not permissions.can_read
            or not permissions.can_trade
            or permissions.can_withdraw
            or permissions.can_transfer
        ):
            raise ValueError("Verified read/trade-only demo permissions required.")

    def reconcile_exit(
        self, *, plan: TradePlanRevision, entry: DemoOrderEvidence
    ) -> VerifiedDemoExit | None:
        from app.providers.exchange.governed_blofin_exit import reconcile_demo_exit

        return reconcile_demo_exit(self._client, plan=plan, entry=entry, clock=self._clock)

    def submit(
        self, *, plan: TradePlanRevision, client_order_id: str, before_post: Callable[[], None]
    ) -> str:
        """One POST, with stop and target attached to the entry order."""
        snapshot = self.snapshot(
            symbol=plan.execution_instrument.replace("-", ""), now=self._clock()
        )
        rules = plan.instrument_rules
        if (snapshot.tick, snapshot.lot, snapshot.minimum, snapshot.multiplier) != (
            rules.tick_size,
            rules.lot_size,
            rules.minimum_quantity,
            rules.contract_multiplier,
        ) or plan.quantity.value > snapshot.maximum:
            raise ValueError("Demo instrument constraints changed before dispatch.")
        if (
            abs(snapshot.price - plan.basis_policy.execution_price.value)
            / plan.basis_policy.execution_price.value
            * Decimal("10000")
            > plan.slippage_policy.maximum_bps
        ):
            raise ValueError("Demo execution quote moved beyond the authorized slippage bound.")
        if (
            abs(snapshot.price - plan.basis_policy.evidence_price.value)
            / plan.basis_policy.evidence_price.value
            * Decimal("10000")
            > plan.basis_policy.tolerance_bps
        ):
            raise ValueError("Demo cross-venue basis moved beyond the authorized bound.")
        if plan.schema_version == "ManualDemoTradePlanV1":
            equity = min(snapshot.equity, snapshot.available)
            notional = plan.quantity.value * snapshot.multiplier * snapshot.price
            if plan.risk_and_exits.maximum_loss.value > equity * Decimal(
                "0.01"
            ) or notional > equity * Decimal("0.05"):
                raise ValueError("Fresh demo balance no longer supports the authorized risk/size.")
        body = {
            "instId": plan.execution_instrument,
            "marginMode": "cross",
            "positionSide": "net",
            "side": "buy" if plan.side is EntrySide.BUY else "sell",
            "orderType": "market",
            "size": str(plan.quantity.value),
            "clientOrderId": client_order_id,
            "slTriggerPrice": str(plan.risk_and_exits.stop.value),
            "slOrderPrice": "-1",
            "tpTriggerPrice": str(plan.risk_and_exits.targets[0].price.value),
            "tpOrderPrice": "-1",
        }
        if self._clock() >= plan.valid_until:
            raise ValueError("Demo plan expired during dispatch preflight.")
        before_post()
        rows = _rows(self._client.request("POST", "/api/v1/trade/order", body=body, signed=True))
        if len(rows) != 1:
            raise ValueError("Ambiguous demo submit response.")
        row = rows[0]
        if str(row.get("code", "0")) != "0":
            raise ExchangeRequestError("Demo entry/protection rejected.")
        order_id = str(row.get("orderId", ""))
        if not order_id or row.get("clientOrderId", client_order_id) != client_order_id:
            raise ValueError("Ambiguous demo submit identity.")
        return order_id

    def cancel_entry(self, *, plan: TradePlanRevision, evidence: DemoOrderEvidence) -> None:
        """Cancel only an identity-verified live entry, never its protective TPSL."""
        self.verify_permissions()
        if (
            plan.schema_version != "ManualDemoTradePlanV1"
            or evidence.status not in {"live", "partially_filled"}
            or not evidence.order_id
            or not evidence.client_order_id
        ):
            raise ValueError("Verified pending manual demo entry required for cancellation.")
        self._client.request(
            "POST",
            "/api/v1/trade/cancel-order",
            signed=True,
            body={"instId": plan.execution_instrument, "orderId": evidence.order_id},
        )
        # An acknowledgment is not proof of cancellation. Caller must read again.

    def reconcile(
        self, *, plan: TradePlanRevision, client_order_id: str
    ) -> DemoOrderEvidence | None:
        """Read by durable client id. Absence never authorizes another POST."""
        rows = _rows(
            self._client.request(
                "GET",
                "/api/v1/trade/order-detail",
                params={"instId": plan.execution_instrument, "clientOrderId": client_order_id},
                signed=True,
            )
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("Ambiguous demo order lookup.")
        row = rows[0]
        if (
            row.get("clientOrderId") != client_order_id
            or row.get("instId") != plan.execution_instrument
        ):
            raise ValueError("Demo order identity mismatch.")
        if (
            row.get("side") != ("buy" if plan.side is EntrySide.BUY else "sell")
            or Decimal(str(row.get("size"))) != plan.quantity.value
            or row.get("positionSide") != "net"
            or row.get("marginMode") != "cross"
            or row.get("orderType") != "market"
        ):
            raise ValueError("Demo order differs from authorized plan.")
        order_id = str(row.get("orderId", ""))
        if not order_id:
            raise ValueError("Demo order id missing.")
        fill_rows = _rows(
            self._client.request(
                "GET",
                "/api/v1/trade/fills-history",
                params={"instId": plan.execution_instrument, "orderId": order_id, "limit": "100"},
                signed=True,
            )
        )
        if len(fill_rows) >= 100:
            raise ValueError("Demo fill page may be incomplete; operator reconciliation required.")
        fills: list[DemoFill] = []
        for fill in fill_rows:
            if (
                fill.get("orderId") != order_id
                or fill.get("instId") != plan.execution_instrument
                or not fill.get("tradeId")
                or fill.get("side") != row.get("side")
                or fill.get("positionSide") != "net"
            ):
                raise ValueError("Demo fill identity mismatch.")
            if fill.get("feeCurrency", "USDT") != "USDT":
                raise ValueError("Unsupported demo fill fee currency.")
            fee = Decimal(str(fill.get("fee")))
            if not fee.is_finite() or fee < 0:
                raise ValueError("Invalid demo fill fee.")
            fills.append(
                DemoFill(
                    identity=f"{order_id}:{fill['tradeId']}",
                    quantity=_positive(fill.get("fillSize")),
                    price=_positive(fill.get("fillPrice")),
                    occurred_at=_time(fill.get("ts")),
                    fee=fee,
                )
            )
        fills.sort(key=lambda fill: (fill.occurred_at, fill.identity))
        if len({fill.identity for fill in fills}) != len(fills):
            raise ValueError("Duplicate venue fill identity in response.")
        if any(
            fill.occurred_at > self._clock() or fill.occurred_at < plan.valid_from for fill in fills
        ):
            raise ValueError("Demo fill occurrence time outside submitted plan history.")
        filled = Decimal(str(row.get("filledSize", "0")))
        if sum((f.quantity for f in fills), Decimal("0")) != filled or filled > plan.quantity.value:
            raise ValueError("Demo fill totals incomplete or exceed authorization.")
        protection_status = "missing"
        try:
            protection = _rows(
                self._client.request(
                    "GET",
                    "/api/v1/trade/orders-tpsl-pending",
                    params={"instId": plan.execution_instrument},
                    signed=True,
                )
            )
        except Exception:
            # Verified fills survive a separate protection-query outage.
            protection = []
            protection_status = "unavailable"
        protected = False
        verified_protection_ids: list[str] = []
        if len(protection) >= 100:
            protection = []
            protection_status = "unavailable"
        for p in protection:
            # Unrelated orders cannot establish protection or obstruct linked evidence.
            if p.get("clientOrderId") != client_order_id:
                continue
            try:
                matches = (
                    bool(p.get("tpslId"))
                    and p.get("instId") == plan.execution_instrument
                    and p.get("state") == "live"
                    and p.get("side") == ("sell" if plan.side is EntrySide.BUY else "buy")
                    and p.get("positionSide") == "net"
                    and p.get("marginMode") == "cross"
                    and p.get("slOrderPrice") == "-1"
                    and p.get("tpOrderPrice") == "-1"
                    and _time(p.get("createTime")) >= _time(row.get("createTime"))
                    and Decimal(str(p.get("slTriggerPrice"))) == plan.risk_and_exits.stop.value
                    and Decimal(str(p.get("tpTriggerPrice")))
                    == plan.risk_and_exits.targets[0].price.value
                    and Decimal(str(p.get("size"))) >= filled
                )
            except Exception:
                # Protection parsing is a separate observation, never a reason to
                # discard already validated actual fill facts.
                protection_status = "unavailable"
                continue
            protected = protected or matches
            if matches:
                verified_protection_ids.append(str(p["tpslId"]))
        if plan.schema_version == "ManualDemoTradePlanV1" and len(verified_protection_ids) > 1:
            protected = False
            protection_status = "ambiguous"
        return DemoOrderEvidence(
            order_id,
            client_order_id,
            str(row.get("state", "")),
            tuple(fills),
            protected,
            "verified" if protected else protection_status,
            tuple(verified_protection_ids),
        )
