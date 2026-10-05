"""Immutable research policy registry; entirely separate from strategy parameters."""

from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.confluence.contracts import ComponentName
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.services.canonical_serialization import canonical_sha256


class ComponentWeight(CanonicalModel):
    component: ComponentName
    weight: CanonicalDecimal = Field(ge=0)


class ConfluencePolicy(CanonicalModel):
    version: str
    provisional: Literal[True] = True
    weights: tuple[ComponentWeight, ...]
    volume_lookback: int = Field(ge=1)
    volume_reference_ratio: CanonicalDecimal = Field(gt=0)
    quality_reference_points: CanonicalDecimal = Field(ge=0, le=100)
    minimum_scored_coverage: CanonicalDecimal = Field(ge=0, le=1)
    account_context_max_age_seconds: int = Field(ge=1)
    history_max_age_seconds: int = Field(ge=1)
    history_min_sample_size: int = Field(ge=1)
    normalization_version: str
    arithmetic_version: str = "decimal-28-half-even/v1"
    score_method: Literal["available_weight_mean_times_100"] = "available_weight_mean_times_100"

    @property
    def content_hash(self) -> str:
        return canonical_sha256(self)


POLICY_V2_001 = ConfluencePolicy(
    version="confluence-research/v2.001",
    weights=tuple(
        ComponentWeight(
            component=name,
            weight=Decimal(20)
            if name
            in {
                ComponentName.PATTERN,
                ComponentName.HTF,
                ComponentName.VOLUME,
                ComponentName.ORDER_FLOW,
                ComponentName.CVD,
            }
            else Decimal(0),
        )
        for name in ComponentName
    ),
    volume_lookback=20,
    volume_reference_ratio=Decimal("1.5"),
    quality_reference_points=Decimal(80),
    minimum_scored_coverage=Decimal("0.5"),
    account_context_max_age_seconds=60,
    history_max_age_seconds=86400,
    history_min_sample_size=20,
    normalization_version="confirmed-state;two-close-alignment;relative-volume;directional-flow/v1",
)


def get_policy(version: str = POLICY_V2_001.version) -> ConfluencePolicy:
    """Unknown versions fail; changing defaults requires a new explicit registry entry."""
    if version != POLICY_V2_001.version:
        raise ValueError(f"Unknown confluence policy version: {version}")
    return POLICY_V2_001
