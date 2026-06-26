"""Venue-safe client order id derivation for BloFin demo orders."""

from __future__ import annotations

import hashlib
import re

_VENUE_PREFIX = "AT"
_HASH_HEX_LEN = 30  # ``AT`` + 30 hex chars = 32 (BloFin max)
_ALNUM = re.compile(r"^[A-Za-z0-9]+$")


def derive_blofin_venue_client_order_id(idempotency_key: str) -> str:
    """Return a stable, venue-safe client order id for a paper idempotency key.

    BloFin requires alphanumeric client order ids up to 32 characters. App
    idempotency keys may contain hyphens or other characters and must never be
    sent to the venue verbatim.
    """
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:_HASH_HEX_LEN]
    return f"{_VENUE_PREFIX}{digest}"


def is_valid_blofin_venue_client_order_id(value: str) -> bool:
    """Return True when ``value`` satisfies BloFin clientOrderId constraints."""
    return bool(value) and len(value) <= 32 and _ALNUM.fullmatch(value) is not None
