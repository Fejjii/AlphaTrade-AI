"""Tests for BloFin venue-safe client order id derivation."""

from __future__ import annotations

import re

from app.providers.exchange.client_order_id import (
    derive_blofin_venue_client_order_id,
    is_valid_blofin_venue_client_order_id,
)

_ALNUM = re.compile(r"^[A-Za-z0-9]+$")


def test_venue_client_order_id_is_alphanumeric_only() -> None:
    venue_id = derive_blofin_venue_client_order_id("slice66b-demo-limit-001")
    assert _ALNUM.fullmatch(venue_id)
    assert is_valid_blofin_venue_client_order_id(venue_id)


def test_venue_client_order_id_length_at_most_32() -> None:
    venue_id = derive_blofin_venue_client_order_id("slice66b-demo-limit-001")
    assert len(venue_id) <= 32
    assert venue_id.startswith("AT")


def test_same_idempotency_key_gives_same_venue_client_order_id() -> None:
    key = "slice66b-demo-limit-001"
    assert derive_blofin_venue_client_order_id(key) == derive_blofin_venue_client_order_id(key)


def test_different_idempotency_keys_give_different_venue_client_order_ids() -> None:
    a = derive_blofin_venue_client_order_id("slice66b-demo-limit-001")
    b = derive_blofin_venue_client_order_id("slice66b-demo-limit-002")
    assert a != b


def test_raw_idempotency_key_with_hyphens_is_never_sent_verbatim() -> None:
    raw = "slice66b-demo-limit-001"
    venue_id = derive_blofin_venue_client_order_id(raw)
    assert raw not in venue_id
    assert "-" not in venue_id
