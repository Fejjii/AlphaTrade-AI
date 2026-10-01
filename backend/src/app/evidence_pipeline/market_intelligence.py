"""OI/funding acquisition and required-input checks on the existing evidence source."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.market_contracts.adapters.protocol import PerpetualMarketSource
from app.market_contracts.derivatives import (
    DerivativeMetric,
    DerivativeObservation,
    derivative_identity,
    derivative_observation,
    hash_derivative_observation,
    require_derivative_observations,
)
from app.market_contracts.errors import (
    EvidenceSourceSwitchRequiredError,
    MarketContractError,
    RateLimitedError,
    RegionalProviderFailureError,
    WrongSourceError,
)
from app.market_contracts.identity import EvidenceMarketIdentity, InstrumentIdentity
from app.schemas.nested_continuation import EvidenceAvailability
from app.signal_fusion.enums import EvidenceRole

DERIVATIVE_ROLES = {
    EvidenceRole.OPEN_INTEREST: DerivativeMetric.OPEN_INTEREST,
    EvidenceRole.FUNDING: DerivativeMetric.FUNDING,
}


def read_market_intelligence(
    source: PerpetualMarketSource,
    *,
    identity: EvidenceMarketIdentity,
    instrument: InstrumentIdentity,
    observed_at: datetime,
    metrics: Sequence[DerivativeMetric] = tuple(DerivativeMetric),
) -> tuple[DerivativeObservation, ...]:
    observations = []
    for metric in metrics:
        try:
            fetch = getattr(source, "fetch_derivative_observation", None)
            if not callable(fetch):
                observations.append(
                    derivative_observation(
                        identity=identity,
                        metric=metric,
                        observed_at=observed_at,
                        availability=EvidenceAvailability.UNSUPPORTED,
                        reason="provider_has_no_oi_funding_contract",
                    )
                )
                continue
            result = fetch(
                identity=identity,
                instrument=instrument,
                metric=metric,
                observed_at=observed_at,
            )
            if not isinstance(result, DerivativeObservation):
                raise WrongSourceError("OI/funding provider returned an invalid observation.")
            if (
                result.metric is not metric
                or result.identity != derivative_identity(identity, metric)
                or result.observed_at != observed_at
                or hash_derivative_observation(result).content_hash != result.content_hash
            ):
                raise WrongSourceError("OI/funding result does not match the requested source.")
        except EvidenceSourceSwitchRequiredError:
            # Discard all prior facts; reassemble under the new venue identity.
            raise
        except (MarketContractError, ValueError, TypeError) as exc:
            result = derivative_observation(
                identity=identity,
                metric=metric,
                observed_at=observed_at,
                availability=(
                    EvidenceAvailability.MISSING
                    if isinstance(exc, RegionalProviderFailureError | RateLimitedError)
                    else EvidenceAvailability.INCOMPLETE
                ),
                reason=f"provider_failure:{type(exc).__name__}",
            )
        observations.append(result)
    return tuple(observations)


def require_market_intelligence(
    observations: Sequence[DerivativeObservation],
    *,
    required_roles: Sequence[EvidenceRole],
    identity: EvidenceMarketIdentity,
    evaluated_at: datetime,
) -> None:
    require_derivative_observations(
        observations,
        required_metrics=tuple(
            DERIVATIVE_ROLES[r] for r in required_roles if r in DERIVATIVE_ROLES
        ),
        identity=identity,
        evaluated_at=evaluated_at,
    )
