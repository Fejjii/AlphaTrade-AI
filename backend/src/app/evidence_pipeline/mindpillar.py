"""Optional derived intelligence boundary; cannot supply canonical exchange evidence.

No verified official stable API contract is configured. The live adapter therefore
makes no network requests and returns unavailable. Exchange observations remain the
only canonical inputs. This schema declares consumer needs, not a MindPillar API.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import FreshnessState, MarketType, VenueId
from app.market_contracts.freshness import (
    FreshnessEvaluation,
    FreshnessPolicy,
    evaluate_freshness,
)
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.schemas.nested_continuation import EvidenceAvailability


class IntelligenceKind(StrEnum):
    CROSS_VENUE_CVD = "cross_venue_cvd"
    CVD_DIVERGENCE = "cvd_divergence"
    OPEN_INTEREST = "open_interest_context"
    FUNDING = "funding_context"
    ORDER_FLOW = "order_flow_context"
    LIQUIDATIONS = "liquidation_context"


class IntelligenceRequest(CanonicalModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{2,32}$")
    observed_at: AwareDatetime
    kinds: tuple[IntelligenceKind, ...] = Field(
        default=tuple(IntelligenceKind), min_length=1, max_length=6
    )


class IntelligenceSource(CanonicalModel):
    """Provider-declared upstream provenance; never a canonical coverage proof."""

    venue: VenueId
    market_type: MarketType
    instrument_id: str = Field(min_length=8, max_length=80)
    provider_symbol: str = Field(pattern=r"^[A-Z0-9]{2,32}$")
    source_reference: str = Field(min_length=1, max_length=200)


class IntelligenceValue(CanonicalModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: CanonicalDecimal
    units: str = Field(min_length=1, max_length=80)
    calculation_method: str = Field(min_length=1, max_length=120)


class SupplementalIntelligenceObservation(CanonicalModel):
    authority: Literal["supplemental"] = "supplemental"
    provider: Literal["mindpillar"] = "mindpillar"
    kind: IntelligenceKind
    symbol: str = Field(pattern=r"^[A-Z0-9]{2,32}$")
    provider_timestamp: AwareDatetime | None = None
    observed_at: AwareDatetime
    source_provenance: tuple[IntelligenceSource, ...] = Field(default=(), max_length=16)
    freshness: FreshnessEvaluation | None = None
    availability: EvidenceAvailability
    values: tuple[IntelligenceValue, ...] = Field(default=(), max_length=32)
    window_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None
    reset_semantics: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _truthful_availability(self) -> SupplementalIntelligenceObservation:
        available = self.availability is EvidenceAvailability.AVAILABLE
        if available:
            if (
                self.provider_timestamp is None
                or not self.source_provenance
                or not self.values
                or self.freshness is None
                or self.freshness.source_time != self.provider_timestamp
                or self.freshness.evaluated_at != self.observed_at
                or self.freshness.state not in {FreshnessState.FRESH, FreshnessState.AGING}
                or self.freshness.valid_until < self.observed_at
            ):
                raise ValueError(
                    "Available intelligence requires provenance, values and freshness."
                )
            if any(source.provider_symbol != self.symbol for source in self.source_provenance):
                raise ValueError("Intelligence source symbols must match the observation.")
            if self.kind in {IntelligenceKind.CROSS_VENUE_CVD, IntelligenceKind.CVD_DIVERGENCE}:
                if self.window_start is None or self.window_end is None or not self.reset_semantics:
                    raise ValueError(
                        "CVD intelligence requires explicit windows and reset semantics."
                    )
                if (
                    self.kind is IntelligenceKind.CROSS_VENUE_CVD
                    and len({source.venue for source in self.source_provenance}) < 2
                ):
                    raise ValueError("Cross venue CVD requires at least two source venues.")
        elif self.values:
            raise ValueError("Unavailable intelligence cannot carry usable values.")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("Intelligence windows require both bounds.")
        if (
            self.window_start is not None
            and self.window_end is not None
            and (self.window_start >= self.window_end or self.window_end > self.observed_at)
        ):
            raise ValueError("Intelligence windows must be closed and ordered.")
        return self


class SupplementalIntelligenceReport(CanonicalModel):
    schema_version: Literal["SupplementalIntelligenceV1"] = "SupplementalIntelligenceV1"
    authority: Literal["supplemental"] = "supplemental"
    provider: Literal["mindpillar"] = "mindpillar"
    symbol: str = Field(pattern=r"^[A-Z0-9]{2,32}$")
    observed_at: AwareDatetime
    availability: EvidenceAvailability
    reason_code: Literal["available", "api_contract_unverified", "provider_unavailable"]
    observations: tuple[SupplementalIntelligenceObservation, ...] = Field(default=(), max_length=6)

    @model_validator(mode="after")
    def _consistent_report(self) -> SupplementalIntelligenceReport:
        if self.availability is EvidenceAvailability.AVAILABLE:
            if not self.observations or self.reason_code != "available":
                raise ValueError("Available intelligence requires observations.")
            if len({o.kind for o in self.observations}) != len(self.observations):
                raise ValueError("Intelligence kinds must be unique.")
            if any(
                o.symbol != self.symbol
                or o.observed_at != self.observed_at
                or o.availability is not EvidenceAvailability.AVAILABLE
                for o in self.observations
            ):
                raise ValueError("Intelligence observations must match report scope.")
        elif self.observations or self.reason_code == "available":
            raise ValueError("Unavailable report cannot carry executable observations.")
        return self


class SupplementalIntelligenceProvider(Protocol):
    def observe(self, request: IntelligenceRequest) -> SupplementalIntelligenceReport: ...


class MindPillarLiveAdapter:
    """Unavailable pending an official versioned API, licensing and data semantics."""

    def observe(self, request: IntelligenceRequest) -> SupplementalIntelligenceReport:
        return SupplementalIntelligenceReport(
            symbol=request.symbol,
            observed_at=request.observed_at,
            availability=EvidenceAvailability.UNSUPPORTED,
            reason_code="api_contract_unverified",
        )


def require_supplemental_intelligence(
    report: SupplementalIntelligenceReport,
    *,
    request: IntelligenceRequest,
    evaluated_at: datetime,
    freshness_policy: FreshnessPolicy,
) -> None:
    """Fail closed for consumers requiring intelligence; does not authorize a Candidate."""

    report = SupplementalIntelligenceReport.model_validate(report.model_dump())
    if report.symbol != request.symbol or report.observed_at > evaluated_at:
        raise ValueError("Supplemental intelligence scope or clock does not match.")
    if report.availability is not EvidenceAvailability.AVAILABLE:
        raise ValueError("supplemental_intelligence_unavailable")
    if not set(request.kinds) <= {o.kind for o in report.observations}:
        raise ValueError("supplemental_intelligence_components_missing")
    for observation in report.observations:
        assert observation.provider_timestamp is not None
        evaluate_freshness(
            source_time=observation.provider_timestamp,
            evaluated_at=evaluated_at,
            policy=freshness_policy,
        )
