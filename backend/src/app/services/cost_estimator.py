"""Placeholder cost estimation — not billing-grade.

Official tokenizer or provider-reported costs should replace this module for
production billing. Values are deterministic for tests and observability only.
"""

from __future__ import annotations

from decimal import Decimal

# Per-1M token placeholder rates (USD) — informational only
_PLACEHOLDER_RATES: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "default": (Decimal("0.20"), Decimal("0.80")),
}


def estimate_placeholder_cost(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Return a non-billing-grade estimated cost from token counts."""
    input_rate, output_rate = _PLACEHOLDER_RATES.get(model or "", _PLACEHOLDER_RATES["default"])
    input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * input_rate
    output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * output_rate
    return (input_cost + output_cost).quantize(Decimal("0.00000001"))
