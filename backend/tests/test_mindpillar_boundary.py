"""Supplemental intelligence never substitutes for canonical exchange observations."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.mindpillar import (
    IntelligenceKind,
    IntelligenceRequest,
    IntelligenceSource,
    IntelligenceValue,
    MindPillarLiveAdapter,
    SupplementalIntelligenceObservation,
    SupplementalIntelligenceReport,
    require_supplemental_intelligence,
)
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.enums import MarketType, VenueId
from app.market_contracts.errors import StaleEvidenceError
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.schemas.nested_continuation import EvidenceAvailability as State
from app.signal_fusion.first_slice_types import FirstSliceEvidenceBundle
from app.signal_fusion.observation import PublicMarketObservation
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import ORG_ID


def observation(kind=IntelligenceKind.FUNDING):
    return SupplementalIntelligenceObservation(
        kind=kind,
        symbol="BTCUSDT",
        provider_timestamp=EVALUATED_AT,
        observed_at=EVALUATED_AT,
        availability=State.AVAILABLE,
        source_provenance=(
            IntelligenceSource(
                venue=VenueId.BINANCE,
                market_type=MarketType.PERPETUAL,
                instrument_id="binance:usdm_futures:perpetual:BTCUSDT",
                provider_symbol="BTCUSDT",
                source_reference="controlled-test-fixture",
            ),
        ),
        freshness=evaluate_freshness(
            source_time=EVALUATED_AT,
            evaluated_at=EVALUATED_AT,
            policy=first_slice_freshness_policy(),
        ),
        values=(
            IntelligenceValue(
                name="settled_rate",
                value="0.0001",
                units="ratio_per_settlement",
                calculation_method="controlled-test-fixture",
            ),
        ),
    )


def test_live_mindpillar_is_unavailable_without_network_and_cannot_supply_values(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("MindPillar pending adapter must not contact a network")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    request = IntelligenceRequest(symbol="BTCUSDT", observed_at=EVALUATED_AT)
    result = MindPillarLiveAdapter().observe(request)
    assert result.availability is State.UNSUPPORTED
    assert result.reason_code == "api_contract_unverified"
    assert result.observations == ()
    assert result.authority == "supplemental"
    with pytest.raises(ValueError, match="supplemental_intelligence_unavailable"):
        require_supplemental_intelligence(
            result,
            request=request,
            evaluated_at=EVALUATED_AT,
            freshness_policy=first_slice_freshness_policy(),
        )


def test_supplemental_types_cannot_be_canonical_evidence_or_claim_authority():
    item = observation()
    with pytest.raises(ValidationError):
        PublicMarketObservation.model_validate(item.model_dump())
    with pytest.raises(ValidationError):
        FirstSliceEvidenceBundle.model_validate({"mindpillar": item.model_dump()})
    with pytest.raises(ValidationError):
        SupplementalIntelligenceObservation.model_validate(
            {**item.model_dump(), "authority": "canonical"}
        )
    assembler = FirstSliceEvidenceAssembler(ReplayPerpetualSource(), replay=True)
    before = assembler.assemble(organization_id=ORG_ID)
    MindPillarLiveAdapter().observe(IntelligenceRequest(symbol="BTCUSDT", observed_at=EVALUATED_AT))
    assert (
        assembler.assemble(organization_id=ORG_ID).evidence_window_hash
        == before.evidence_window_hash
    )


@pytest.mark.parametrize(
    "field", ["provider_timestamp", "freshness", "source_provenance", "values"]
)
def test_available_requires_provenance_time_freshness_and_values(field):
    data = observation().model_dump()
    data[field] = () if field in {"source_provenance", "values"} else None
    with pytest.raises(ValidationError):
        SupplementalIntelligenceObservation.model_validate(data)


def test_intelligence_freshness_is_rechecked_at_consumption():
    item = observation()
    report = SupplementalIntelligenceReport(
        symbol="BTCUSDT",
        observed_at=EVALUATED_AT,
        availability=State.AVAILABLE,
        reason_code="available",
        observations=(item,),
    )
    request = IntelligenceRequest(
        symbol="BTCUSDT", observed_at=EVALUATED_AT, kinds=(IntelligenceKind.FUNDING,)
    )
    require_supplemental_intelligence(
        report,
        request=request,
        evaluated_at=EVALUATED_AT,
        freshness_policy=first_slice_freshness_policy(),
    )
    with pytest.raises(StaleEvidenceError):
        require_supplemental_intelligence(
            report,
            request=request,
            evaluated_at=EVALUATED_AT + timedelta(seconds=11),
            freshness_policy=first_slice_freshness_policy(),
        )
    with pytest.raises(ValueError, match="components_missing"):
        require_supplemental_intelligence(
            report,
            request=IntelligenceRequest(symbol="BTCUSDT", observed_at=EVALUATED_AT),
            evaluated_at=EVALUATED_AT,
            freshness_policy=first_slice_freshness_policy(),
        )


def test_cross_venue_cvd_requires_explicit_reset_window_and_multiple_venues():
    data = observation().model_dump()
    data["kind"] = IntelligenceKind.CROSS_VENUE_CVD
    with pytest.raises(ValidationError, match="windows and reset"):
        SupplementalIntelligenceObservation.model_validate(data)
    data.update(
        window_start=EVALUATED_AT - timedelta(minutes=10),
        window_end=EVALUATED_AT,
        reset_semantics="zero_at_window_start",
    )
    with pytest.raises(ValidationError, match="two source venues"):
        SupplementalIntelligenceObservation.model_validate(data)
    bybit = {
        **data["source_provenance"][0],
        "venue": VenueId.BYBIT,
        "instrument_id": "bybit:usdm_futures:perpetual:BTCUSDT",
    }
    data["source_provenance"] = (*data["source_provenance"], bybit)
    assert SupplementalIntelligenceObservation.model_validate(data).authority == "supplemental"


def test_unavailable_intelligence_cannot_contain_a_usable_value():
    data = observation().model_dump()
    data["availability"] = State.MISSING
    with pytest.raises(ValidationError, match="Unavailable intelligence"):
        SupplementalIntelligenceObservation.model_validate(data)
