"""Strict native reads with bounded diagnostics; no mutations or synthetic fills."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.demo_preflight import failure_diagnostics
from app.providers.exchange.governed_blofin import DemoFill, DemoOrderEvidence, _time
from app.schemas.manual_demo import DemoReconciliationDiagnostic
from app.schemas.trade_plan import EntrySide, TradePlanRevision

ORDER = "GET /api/v1/trade/order-detail"
FILLS = "GET /api/v1/trade/fills-history"
PROTECTION = "GET /api/v1/trade/orders-tpsl-pending"


class NativeEvidenceError(ValueError):
    def __init__(self, reason: str, field: str | None = None) -> None:
        self.reason = reason
        self.field = field
        super().__init__("Native demo evidence refused.")


class DemoReconciliationError(ValueError):
    def __init__(self, diagnostic: DemoReconciliationDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__("Native demo reconciliation requires operator review.")


def diagnostic_for(exc: Exception, *, stage: str, endpoint: str) -> DemoReconciliationDiagnostic:
    if isinstance(exc, DemoReconciliationError):
        return exc.diagnostic
    safe = failure_diagnostics(exc, stage=stage, endpoint=endpoint)
    if isinstance(exc, NativeEvidenceError):
        safe["reason_code"] = exc.reason
        if exc.field:
            safe["field_name"] = exc.field
    return DemoReconciliationDiagnostic.model_validate(safe)


@contextmanager
def stage(name: str, endpoint: str) -> Iterator[None]:
    try:
        yield
    except DemoReconciliationError:
        raise
    except Exception as exc:
        raise DemoReconciliationError(diagnostic_for(exc, stage=name, endpoint=endpoint)) from exc


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise NativeEvidenceError(reason)


def rows(data: Any, *, single: bool = False) -> list[dict[str, Any]]:
    if single and isinstance(data, dict):
        return [data]
    require(isinstance(data, list), "response_shape_invalid")
    require(all(isinstance(row, dict) for row in data), "response_shape_invalid")
    require(len(data) < 100, "response_page_incomplete")
    return cast(list[dict[str, Any]], data)


def number(value: Any, *, field: str, positive: bool = False) -> Decimal:
    try:
        require(isinstance(value, str) and 0 < len(value) <= 64, "numeric_value_invalid")
        parsed = Decimal(value)
        require(
            parsed.is_finite()
            and len(parsed.as_tuple().digits) <= 24
            and abs(int(parsed.as_tuple().exponent)) <= 18,
            "numeric_value_invalid",
        )
        if positive:
            require(parsed > 0, "numeric_value_invalid")
        return parsed
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise NativeEvidenceError("numeric_value_invalid", field=field) from exc


def identity(value: Any) -> str:
    require(
        isinstance(value, str)
        and 0 < len(value) <= 64
        and value.isascii()
        and all(c.isalnum() or c in "_-" for c in value),
        "native_identity_invalid",
    )
    return cast(str, value)


def occurrence(value: Any, *, earliest: datetime, now: datetime) -> datetime:
    require(
        isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 16,
        "native_timestamp_invalid",
    )
    parsed = _time(value)
    require(earliest <= parsed <= now, "native_timestamp_outside_order_history")
    return parsed


def reconcile_native(
    client: BloFinClient,
    *,
    plan: TradePlanRevision,
    client_order_id: str,
    clock: Callable[[], datetime],
) -> DemoOrderEvidence | None:
    with stage("order_lookup", ORDER):
        order_rows = rows(
            client.request(
                "GET",
                ORDER.removeprefix("GET "),
                params={"instId": plan.execution_instrument, "clientOrderId": client_order_id},
                signed=True,
            ),
            single=True,
        )
    if not order_rows:
        return None  # Never permission to submit again.
    with stage("order_parse", ORDER):
        require(len(order_rows) == 1, "order_lookup_ambiguous")
        order = order_rows[0]
        require(
            order.get("clientOrderId") == client_order_id
            and order.get("instId") == plan.execution_instrument,
            "order_identity_mismatch",
        )
        order_id = identity(order.get("orderId"))
        require(
            order.get("side") == ("buy" if plan.side is EntrySide.BUY else "sell")
            and number(order.get("size"), field="size", positive=True) == plan.quantity.value
            and order.get("positionSide") == "net"
            and order.get("marginMode") == "cross"
            and order.get("orderType") == "market",
            "order_plan_mismatch",
        )
        created = occurrence(order.get("createTime"), earliest=plan.valid_from, now=clock())
        filled = number(order.get("filledSize"), field="filledSize")
        require(0 <= filled <= plan.quantity.value, "order_filled_quantity_invalid")
        state = order.get("state")
        require(
            state
            in {
                "live",
                "partially_filled",
                "filled",
                "canceled",
                "cancelled",
                "expired",
                "rejected",
            },
            "order_state_unknown",
        )
        require(
            (state != "filled" or filled == plan.quantity.value)
            and (state != "rejected" or filled == 0)
            and (state != "live" or filled == 0)
            and (state != "partially_filled" or 0 < filled < plan.quantity.value),
            "order_state_quantity_conflict",
        )
    with stage("fill_lookup", FILLS):
        fill_rows = rows(
            client.request(
                "GET",
                FILLS.removeprefix("GET "),
                params={"instId": plan.execution_instrument, "orderId": order_id, "limit": "100"},
                signed=True,
            )
        )
    with stage("fill_parse", FILLS):
        fills: list[DemoFill] = []
        for fill in fill_rows:
            require(
                fill.get("orderId") == order_id
                and fill.get("instId") == plan.execution_instrument
                and fill.get("side") == order.get("side")
                and fill.get("positionSide") == "net",
                "fill_identity_mismatch",
            )
            trade_id = identity(fill.get("tradeId"))
            require(fill.get("feeCurrency", "USDT") == "USDT", "fill_fee_currency_unsupported")
            # Preserve native signed fees/rebates. Never abs(), zero or infer a charge.
            fee = number(fill.get("fee"), field="fee")
            quantity = number(fill.get("fillSize"), field="fillSize", positive=True)
            price = number(fill.get("fillPrice"), field="fillPrice", positive=True)
            # Submission increments constrain orders, not individual matching-engine
            # executions. Real partial fills may be smaller; complete totals and
            # identity-bound positive quantities still constrain the authorization.
            # REST uses ts. Some native variants expose fillTime; contradictory clocks refuse.
            timestamp = fill.get("ts", fill.get("fillTime"))
            if fill.get("ts") is not None and fill.get("fillTime") is not None:
                require(fill["ts"] == fill["fillTime"], "fill_timestamp_conflict")
            fills.append(
                DemoFill(
                    f"{order_id}:{trade_id}",
                    quantity,
                    price,
                    occurrence(timestamp, earliest=created, now=clock()),
                    fee,
                )
            )
        fills.sort(key=lambda fill: (fill.occurred_at, fill.identity))
        require(len({fill.identity for fill in fills}) == len(fills), "fill_identity_duplicate")
        require(
            sum((fill.quantity for fill in fills), Decimal("0")) == filled, "fill_totals_incomplete"
        )
    diagnostics: list[DemoReconciliationDiagnostic] = []
    protection_status = "missing"
    verified: list[str] = []
    try:
        with stage("protection_lookup", PROTECTION):
            protection = rows(
                client.request(
                    "GET",
                    PROTECTION.removeprefix("GET "),
                    params={"instId": plan.execution_instrument, "limit": "100"},
                    signed=True,
                )
            )
        linked = 0
        for p in protection:
            # A returned native parent/TPSL id may establish lineage even when the
            # protective client id is blank. Similar terms alone never establish it.
            client_link = p.get("clientOrderId") == client_order_id
            parent_link = p.get("orderId") == order_id
            tpsl_link = bool(order.get("tpslId")) and p.get("tpslId") == order["tpslId"]
            if not (client_link or parent_link or tpsl_link):
                continue
            linked += 1
            try:
                with stage("protection_parse", PROTECTION):
                    pid = identity(p.get("tpslId"))
                    require(
                        p.get("orderId") in {None, "", order_id}, "protection_identity_conflict"
                    )
                    require(
                        not order.get("tpslId") or pid == order["tpslId"],
                        "protection_identity_conflict",
                    )
                    require(
                        p.get("instId") == plan.execution_instrument
                        and p.get("state") == "live"
                        and p.get("side") == ("sell" if plan.side is EntrySide.BUY else "buy")
                        and p.get("positionSide") == "net"
                        and p.get("marginMode") == "cross",
                        "protection_terms_mismatch",
                    )
                    require(
                        number(p.get("slOrderPrice"), field="slOrderPrice") == -1
                        and number(p.get("tpOrderPrice"), field="tpOrderPrice") == -1
                        and number(p.get("slTriggerPrice"), field="slTriggerPrice")
                        == plan.risk_and_exits.stop.value
                        and number(p.get("tpTriggerPrice"), field="tpTriggerPrice")
                        == plan.risk_and_exits.targets[0].price.value
                        and number(p.get("size"), field="size", positive=True) >= filled,
                        "protection_terms_mismatch",
                    )
                    occurrence(p.get("createTime"), earliest=created, now=clock())
                    verified.append(pid)
            except DemoReconciliationError as exc:
                diagnostics.append(exc.diagnostic)
        if protection and linked == 0:
            diagnostics.append(
                diagnostic_for(
                    NativeEvidenceError("protection_link_missing"),
                    stage="protection_parse",
                    endpoint=PROTECTION,
                )
            )
        if linked > 1 or len(set(verified)) != len(verified):
            verified = []
            protection_status = "ambiguous"
            diagnostics.append(
                diagnostic_for(
                    NativeEvidenceError("protection_identity_ambiguous"),
                    stage="protection_parse",
                    endpoint=PROTECTION,
                )
            )
        elif any(d.reason_code != "protection_link_missing" for d in diagnostics):
            protection_status = "unavailable"
    except DemoReconciliationError as exc:
        diagnostics.append(exc.diagnostic)
        protection_status = "unavailable"
    return DemoOrderEvidence(
        order_id,
        client_order_id,
        str(state),
        tuple(fills),
        bool(verified),
        "verified" if verified else protection_status,
        tuple(verified),
        tuple(diagnostics[:4]),
    )
