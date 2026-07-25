"""TradingView webhook signature verification (AT-037).

HMAC-SHA256 over ``{timestamp}.{raw_body}`` with replay protection via
timestamp skew. Fail-closed when the secret is missing or the signature
header is absent/invalid. Secrets are never logged.
"""

from __future__ import annotations

import hashlib
import hmac
import time


def verify_tradingview_signature(
    payload: bytes,
    *,
    signature_header: str | None,
    timestamp_header: str | None,
    secret: str,
    max_skew_seconds: int,
    now: float | None = None,
) -> bool:
    """Return True when signature + timestamp are valid; otherwise False."""
    if not secret.strip():
        return False
    if not signature_header or not timestamp_header:
        return False
    try:
        timestamp = int(timestamp_header.strip())
    except ValueError:
        return False
    current = time.time() if now is None else now
    if abs(current - timestamp) > max_skew_seconds:
        return False
    signature = signature_header.strip().lower()
    if signature.startswith("sha256="):
        signature = signature.removeprefix("sha256=")
    if len(signature) != 64:
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def compute_tradingview_signature(
    payload: bytes,
    *,
    timestamp: int,
    secret: str,
) -> str:
    """Compute a hex HMAC for tests and local tooling (never log secret)."""
    signed = f"{timestamp}.".encode() + payload
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
