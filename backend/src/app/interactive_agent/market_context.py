"""Deterministic Agent presentation, rechecking every optional evidence boundary."""

from __future__ import annotations

from app.market_contracts.context import MarketEvidenceContext
from app.market_contracts.derivatives import DerivativeMetric, require_derivative_observations
from app.market_contracts.errors import MarketContractError, StaleEvidenceError
from app.market_contracts.order_book import require_order_book
from app.market_contracts.order_flow import require_order_flow
from app.schemas.nested_continuation import EvidenceAvailability


def _unusable_state(reported: EvidenceAvailability, exc: Exception) -> str:
    if isinstance(exc, StaleEvidenceError):
        return EvidenceAvailability.STALE.value
    return (
        EvidenceAvailability.INCOMPLETE.value
        if reported is EvidenceAvailability.AVAILABLE
        else reported.value
    )


def market_context_text(context: MarketEvidenceContext) -> str:
    parts: list[str] = []
    if not any(item.metric is DerivativeMetric.OPEN_INTEREST for item in context.derivatives):
        parts.append("Open interest: MISSING.")
    for item in context.derivatives:
        label = f"{item.metric.value} venue={item.identity.venue.value}"
        if item.metric is not DerivativeMetric.OPEN_INTEREST:
            continue
        try:
            require_derivative_observations(
                (item,),
                required_metrics=(item.metric,),
                identity=item.identity,
                evaluated_at=context.evaluated_at,
            )
            parts.append(
                f"{label}: {item.value} {item.units}; single provider record, "
                "OI change and OI notional unavailable."
            )
        except (MarketContractError, ValueError) as exc:
            parts.append(f"{label}: {_unusable_state(item.availability, exc)}; no usable OI value.")
    flow = context.order_flow
    if flow is None:
        parts.append("Executed flow and CVD: MISSING.")
    else:
        label = f"Executed flow/CVD venue={flow.identity.venue.value}"
        try:
            require_order_flow(flow, identity=flow.identity, evaluated_at=context.evaluated_at)
            last = flow.windows[-1]
            parts.append(
                f"{label}: closed 5m buy={last.aggressive_buy_base_volume} "
                f"sell={last.aggressive_sell_base_volume} {flow.base_units}; "
                f"10m CVD={flow.rolling_cvd} {flow.cvd_units}, reset to zero at "
                f"{flow.window_start.isoformat()}; divergence={flow.cvd_divergence or 'none'}."
            )
        except (MarketContractError, ValueError) as exc:
            parts.append(
                f"{label}: {_unusable_state(flow.availability, exc)}; "
                "coverage or freshness unavailable."
            )
    book = context.order_book
    if book is None:
        parts.append("Resting order book: MISSING.")
    else:
        label = f"Resting order book venue={book.identity.venue.value}"
        try:
            require_order_book(book, identity=book.identity, evaluated_at=context.evaluated_at)
            parts.append(
                f"{label}: spread={book.spread} {book.price_units}; "
                f"snapshot of up to {book.requested_depth} levels per side; "
                "historical coverage unavailable; RPI excluded."
            )
        except (MarketContractError, ValueError) as exc:
            parts.append(
                f"{label}: {_unusable_state(book.availability, exc)}; no usable liquidity value."
            )
    if context.cross_venue_components:
        parts.append("Cross-venue context: " + ", ".join(context.cross_venue_components) + ".")
    return " ".join(parts)
