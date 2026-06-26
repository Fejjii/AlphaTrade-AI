"""Tests for redaction-safe venue mirror failure diagnostics."""

from __future__ import annotations

from decimal import Decimal

from app.providers.exchange.client_order_id import derive_blofin_venue_client_order_id
from app.providers.exchange.errors import ExchangeRequestError, VenueErrorDetails
from app.providers.exchange.venue_diagnostics import (
    build_demo_mirror_failure_metadata,
    client_order_id_fingerprint,
)
from app.schemas.common import OrderSide, OrderType
from app.schemas.execution import PaperOrderRequest


def test_client_order_id_fingerprint_is_hash_not_raw() -> None:
    raw = "slice66b-demo-limit-001"
    fingerprint = client_order_id_fingerprint(raw)
    assert fingerprint is not None
    assert fingerprint != raw
    assert len(fingerprint) == 8


def test_mirror_failure_metadata_includes_safe_fields() -> None:
    request = PaperOrderRequest(
        proposal_id="00000000-0000-0000-0000-000000000001",
        approval_id="00000000-0000-0000-0000-000000000002",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        size=Decimal("0.1"),
        price=Decimal("44716.5"),
        idempotency_key="slice66b-demo-limit-001",
    )
    exc = ExchangeRequestError(
        "BloFin error 51008: Order price is out of the allowable range",
        details=VenueErrorDetails(
            venue_error_code="51008",
            venue_error_message="Order price is out of the allowable range",
            http_status=200,
            endpoint_name="POST /api/v1/trade/order",
        ),
    )
    metadata = build_demo_mirror_failure_metadata(
        exc=exc,
        request=request,
        paper_order_id="849eaac8-0273-4efd-bd60-39dc2a5afd41",
        inst_id="BTC-USDT",
        exchange_mode="paper_exchange_demo",
    )
    assert metadata["venue_error_code"] == "51008"
    assert metadata["http_status"] == 200
    assert metadata["endpoint_name"] == "POST /api/v1/trade/order"
    assert metadata["inst_id"] == "BTC-USDT"
    assert metadata["order_side"] == "buy"
    assert metadata["order_type"] == "limit"
    assert metadata["size"] == "0.1"
    assert metadata["price"] == "44716.5"
    assert metadata["paper_order_id"] == "849eaac8-0273-4efd-bd60-39dc2a5afd41"
    assert "client_order_id_hash" in metadata
    assert "slice66b-demo-limit-001" not in str(metadata)


def test_mirror_failure_metadata_includes_venue_client_order_id_prefix() -> None:
    request = PaperOrderRequest(
        proposal_id="00000000-0000-0000-0000-000000000001",
        approval_id="00000000-0000-0000-0000-000000000002",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        size=Decimal("0.1"),
        price=Decimal("44716.5"),
        idempotency_key="slice66b-demo-limit-001",
    )
    venue_id = derive_blofin_venue_client_order_id("slice66b-demo-limit-001")
    exc = ExchangeRequestError(
        "BloFin error 51000: rejected",
        details=VenueErrorDetails(
            venue_error_code="51000",
            venue_error_message="rejected",
            http_status=200,
            endpoint_name="POST /api/v1/trade/order",
        ),
    )
    metadata = build_demo_mirror_failure_metadata(
        exc=exc,
        request=request,
        paper_order_id="849eaac8-0273-4efd-bd60-39dc2a5afd41",
        inst_id="BTC-USDT",
        exchange_mode="paper_exchange_demo",
        venue_client_order_id=venue_id,
    )
    assert metadata["venue_client_order_id_prefix"] == venue_id[:8]
    assert metadata["client_order_id_hash"] == client_order_id_fingerprint(
        "slice66b-demo-limit-001"
    )
    assert "slice66b-demo-limit-001" not in str(metadata)


def test_mirror_failure_metadata_redacts_secret_like_messages() -> None:
    request = PaperOrderRequest(
        proposal_id="00000000-0000-0000-0000-000000000001",
        approval_id="00000000-0000-0000-0000-000000000002",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        size=Decimal("0.1"),
        idempotency_key="idem001234",
    )
    exc = ExchangeRequestError(
        "BloFin error 1001: api_key=leakedsecret",
        details=VenueErrorDetails(
            venue_error_code="1001",
            venue_error_message="api_key=***REDACTED***",
            http_status=200,
            endpoint_name="POST /api/v1/trade/order",
        ),
    )
    metadata = build_demo_mirror_failure_metadata(
        exc=exc,
        request=request,
        paper_order_id="paper-order-id",
        inst_id="BTC-USDT",
        exchange_mode="paper_exchange_demo",
    )
    assert "leakedsecret" not in str(metadata)


def test_mirror_failure_metadata_includes_position_mode_and_side() -> None:
    request = PaperOrderRequest(
        proposal_id="00000000-0000-0000-0000-000000000001",
        approval_id="00000000-0000-0000-0000-000000000002",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        size=Decimal("0.1"),
        price=Decimal("44716.5"),
        idempotency_key="idem001234",
    )
    exc = ExchangeRequestError(
        "Refusing order: reduce-only is not supported in BloFin hedge mode.",
        position_mode="long_short_mode",
    )
    metadata = build_demo_mirror_failure_metadata(
        exc=exc,
        request=request,
        paper_order_id="paper-order-id",
        inst_id="BTC-USDT",
        exchange_mode="paper_exchange_demo",
    )
    assert metadata["position_mode"] == "long_short_mode"
    assert "demo-key" not in str(metadata)
    assert "demo-secret" not in str(metadata)
