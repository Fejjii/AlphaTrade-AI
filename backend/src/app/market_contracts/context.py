"""Typed optional market context for the existing Agent market read consumer."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, model_validator

from app.market_contracts.derivatives import DerivativeObservation
from app.market_contracts.models import CanonicalModel
from app.market_contracts.order_book import OrderBookObservation
from app.market_contracts.order_flow import OrderFlowObservation

MarketContextObservation = DerivativeObservation | OrderFlowObservation | OrderBookObservation


class MarketEvidenceContext(CanonicalModel):
    contract_version: Literal["public-market-context/v1"] = "public-market-context/v1"
    evaluated_at: AwareDatetime
    anchor_venue: str
    anchor_symbol: str
    derivatives: tuple[DerivativeObservation, ...] = ()
    order_flow: OrderFlowObservation | None = None
    order_book: OrderBookObservation | None = None
    cross_venue_components: tuple[str, ...] = ()
    qualification_authority: Literal[False] = False

    @model_validator(mode="after")
    def _labels(self) -> MarketEvidenceContext:
        components: list[tuple[str, MarketContextObservation]] = [
            (x.metric.value, x) for x in self.derivatives
        ]
        components += [
            (name, x)
            for name, x in (("order_flow", self.order_flow), ("order_book", self.order_book))
            if x is not None
        ]
        expected = tuple(
            name for name, x in components if x.identity.venue.value != self.anchor_venue
        )
        if self.cross_venue_components != expected:
            raise ValueError("Cross-venue context must be explicitly labeled per component.")
        if any(x.identity.instrument.provider_symbol != self.anchor_symbol for _, x in components):
            raise ValueError("Different-symbol evidence cannot be presented as this market.")
        return self
