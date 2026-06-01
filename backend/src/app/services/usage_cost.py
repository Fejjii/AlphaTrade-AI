"""Resolve usage cost from provider metadata and token counts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.common import CostSource
from app.services.cost_estimator import estimate_placeholder_cost


@dataclass(frozen=True)
class ResolvedUsageCost:
    provider_reported_cost: Decimal | None
    estimated_cost: Decimal
    cost_source: CostSource

    @property
    def is_billing_grade(self) -> bool:
        return self.cost_source is CostSource.PROVIDER_REPORTED

    @property
    def display_cost(self) -> Decimal:
        if self.provider_reported_cost is not None:
            return self.provider_reported_cost
        return self.estimated_cost


def resolve_usage_cost(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    provider_metadata: dict[str, int | float | str | bool],
) -> ResolvedUsageCost:
    """Determine cost fields from provider metadata and fallbacks."""
    raw_source = provider_metadata.get("cost_source")
    explicit_source: CostSource | None = None
    if isinstance(raw_source, str):
        try:
            explicit_source = CostSource(raw_source.strip().lower())
        except ValueError:
            explicit_source = None

    raw_reported = provider_metadata.get("provider_reported_cost")
    if raw_reported is not None:
        reported = Decimal(str(raw_reported))
        return ResolvedUsageCost(
            provider_reported_cost=reported,
            estimated_cost=reported,
            cost_source=CostSource.PROVIDER_REPORTED,
        )

    if explicit_source is CostSource.STATIC_ESTIMATED:
        estimated = estimate_placeholder_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ResolvedUsageCost(
            provider_reported_cost=None,
            estimated_cost=estimated,
            cost_source=CostSource.STATIC_ESTIMATED,
        )

    if explicit_source is CostSource.TOKENIZER_ESTIMATED or _has_provider_token_usage(
        provider_metadata
    ):
        estimated = estimate_placeholder_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ResolvedUsageCost(
            provider_reported_cost=None,
            estimated_cost=estimated,
            cost_source=CostSource.TOKENIZER_ESTIMATED,
        )

    if input_tokens > 0 or output_tokens > 0:
        estimated = estimate_placeholder_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ResolvedUsageCost(
            provider_reported_cost=None,
            estimated_cost=estimated,
            cost_source=CostSource.STATIC_ESTIMATED,
        )

    return ResolvedUsageCost(
        provider_reported_cost=None,
        estimated_cost=Decimal("0"),
        cost_source=CostSource.UNAVAILABLE,
    )


def build_provider_metadata(
    *,
    input_tokens: int,
    output_tokens: int,
    provider_reported_cost: Decimal | None = None,
    cost_source: CostSource | None = None,
    fallback_used: bool = False,
    **extra: int | float | str | bool,
) -> dict[str, int | float | str | bool]:
    """Build normalized provider metadata for :class:`UsageEventCreate`."""
    meta: dict[str, int | float | str | bool] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "fallback_used": fallback_used,
    }
    if provider_reported_cost is not None:
        meta["provider_reported_cost"] = float(provider_reported_cost)
        meta["cost_source"] = CostSource.PROVIDER_REPORTED.value
    elif cost_source is not None:
        meta["cost_source"] = cost_source.value
    meta.update(extra)
    return meta


def _has_provider_token_usage(metadata: dict[str, int | float | str | bool]) -> bool:
    has_input = isinstance(metadata.get("input_tokens"), int)
    has_output = isinstance(metadata.get("output_tokens"), int)
    return has_input or has_output
