"""Versioned freshness policy and immutable evaluations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import FreshnessState
from app.market_contracts.errors import StaleEvidenceError
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.models import CanonicalModel, NonNegativeCanonicalDecimal

FIRST_SLICE_FRESHNESS_POLICY_VERSION = "first-slice-btc-usdt-usdm-freshness/v1"
FIRST_SLICE_TRADE_MAX_AGE_SECONDS = 10
FIRST_SLICE_OHLCV_GRACE_SECONDS = 0


class FreshnessPolicy(CanonicalModel):
    """Immutable consumer-time freshness rules."""

    policy_version: str = Field(min_length=3, max_length=80)
    trade_max_age_seconds: int = Field(ge=0, le=3600)
    aging_age_seconds: int = Field(ge=0, le=3600)
    ohlcv_post_close_grace_seconds: int = Field(ge=0, le=3600)
    max_clock_skew_seconds: int = Field(ge=0, le=60)

    @model_validator(mode="after")
    def _aging_before_stale(self) -> FreshnessPolicy:
        if self.aging_age_seconds > self.trade_max_age_seconds:
            raise ValueError("aging_age_seconds cannot exceed trade_max_age_seconds.")
        return self


class FreshnessEvaluation(CanonicalModel):
    policy_version: str = Field(min_length=3, max_length=80)
    evaluated_at: AwareDatetime
    source_time: AwareDatetime
    age_seconds: NonNegativeCanonicalDecimal
    valid_until: AwareDatetime
    state: FreshnessState
    clock_skew_seconds: NonNegativeCanonicalDecimal
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def first_slice_freshness_policy() -> FreshnessPolicy:
    return FreshnessPolicy(
        policy_version=FIRST_SLICE_FRESHNESS_POLICY_VERSION,
        trade_max_age_seconds=FIRST_SLICE_TRADE_MAX_AGE_SECONDS,
        aging_age_seconds=5,
        ohlcv_post_close_grace_seconds=FIRST_SLICE_OHLCV_GRACE_SECONDS,
        max_clock_skew_seconds=2,
    )


def _require_utc(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware.")
    return value.astimezone(UTC)


def evaluate_freshness(
    *,
    source_time: datetime,
    evaluated_at: datetime,
    policy: FreshnessPolicy,
    require_fresh: bool = True,
) -> FreshnessEvaluation:
    """Evaluate freshness at a consumer boundary. Time passing beyond valid_until fails closed."""
    source = _require_utc(source_time, label="source_time")
    evaluated = _require_utc(evaluated_at, label="evaluated_at")
    age = evaluated - source
    age_seconds = age.total_seconds()
    if age_seconds < 0:
        skew = abs(age_seconds)
        if skew > policy.max_clock_skew_seconds:
            state = FreshnessState.UNKNOWN
        else:
            age_seconds = 0.0
            state = FreshnessState.FRESH
    elif age_seconds <= policy.aging_age_seconds:
        state = FreshnessState.FRESH
    elif age_seconds <= policy.trade_max_age_seconds:
        state = FreshnessState.AGING
    else:
        state = FreshnessState.STALE

    valid_until = source + timedelta(seconds=policy.trade_max_age_seconds)
    if evaluated > valid_until:
        state = FreshnessState.STALE

    evaluation = with_content_hash(
        FreshnessEvaluation(
            policy_version=policy.policy_version,
            evaluated_at=evaluated,
            source_time=source,
            age_seconds=Decimal(str(age_seconds if age_seconds > 0 else 0)),
            valid_until=valid_until,
            state=state,
            clock_skew_seconds=Decimal(
                str(abs(age.total_seconds()) if age.total_seconds() < 0 else 0)
            ),
            content_hash="0" * 64,
        )
    )
    if require_fresh and state is not FreshnessState.FRESH and state is not FreshnessState.AGING:
        raise StaleEvidenceError(
            f"Evidence is {state.value}: age exceeds {policy.trade_max_age_seconds}s "
            f"under {policy.policy_version}."
        )
    if require_fresh and evaluated > valid_until:
        raise StaleEvidenceError(
            f"Evidence valid_until={valid_until.isoformat()} is in the past at evaluation."
        )
    return evaluation
