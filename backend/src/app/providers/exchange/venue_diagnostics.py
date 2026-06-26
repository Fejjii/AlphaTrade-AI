"""Redaction-safe venue error diagnostics for demo mirror failures."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.guardrails.redaction import redact_text
from app.providers.exchange.errors import ExchangeError, VenueErrorDetails
from app.schemas.execution import PaperOrderRequest

_VENUE_CODE_RE = re.compile(r"(?:BloFin (?:auth )?error|code)\s+(\d+)", re.IGNORECASE)
_HTTP_STATUS_RE = re.compile(r"HTTP\s+(\d{3})", re.IGNORECASE)


def endpoint_label(method: str, path: str) -> str:
    """Return a stable endpoint name without host or query secrets."""
    return f"{method.upper()} {path.split('?', 1)[0]}"


def client_order_id_fingerprint(client_order_id: str | None) -> str | None:
    """Return a short hash of the client order id (never the raw value)."""
    if not client_order_id:
        return None
    return hashlib.sha256(client_order_id.encode("utf-8")).hexdigest()[:8]


def parse_venue_error_message(message: str) -> tuple[str | None, str | None]:
    """Best-effort parse of ``BloFin error {code}: {msg}`` style text."""
    text = redact_text(message)
    code_match = _VENUE_CODE_RE.search(text)
    venue_code = code_match.group(1) if code_match else None
    venue_message: str | None = text
    if venue_code and ": " in text:
        venue_message = text.split(": ", 1)[1].strip() or None
    elif text.startswith("BloFin "):
        venue_message = text
    return venue_code, venue_message


def venue_error_details_from_exception(exc: BaseException) -> VenueErrorDetails:
    """Extract structured venue details when the exception carries them."""
    if isinstance(exc, ExchangeError) and exc.details is not None:
        return exc.details
    message = redact_text(str(exc))
    venue_code, venue_message = parse_venue_error_message(message)
    http_match = _HTTP_STATUS_RE.search(message)
    http_status = int(http_match.group(1)) if http_match else None
    return VenueErrorDetails(
        venue_error_code=venue_code,
        venue_error_message=venue_message,
        http_status=http_status,
    )


def build_demo_mirror_failure_metadata(
    *,
    exc: BaseException,
    request: PaperOrderRequest,
    paper_order_id: str,
    inst_id: str,
    exchange_mode: str,
    endpoint_name: str | None = None,
) -> dict[str, Any]:
    """Build audit-safe metadata for ``exchange_demo_order_failed`` events."""
    details = venue_error_details_from_exception(exc)
    if endpoint_name is None and isinstance(exc, ExchangeError) and exc.details is not None:
        endpoint_name = exc.details.endpoint_name

    metadata: dict[str, Any] = {
        "inst_id": inst_id,
        "mode": exchange_mode,
        "exchange_mode": exchange_mode,
        "paper_order_id": paper_order_id,
        "order_side": request.side.value,
        "order_type": request.type.value,
        "size": str(request.size),
        "error_type": type(exc).__name__,
    }
    if request.price is not None:
        metadata["price"] = str(request.price)
    fingerprint = client_order_id_fingerprint(request.idempotency_key)
    if fingerprint:
        metadata["client_order_id_hash"] = fingerprint

    if details.venue_error_code:
        metadata["venue_error_code"] = details.venue_error_code
    if details.venue_error_message:
        metadata["venue_error_message"] = details.venue_error_message[:200]
    if details.http_status is not None:
        metadata["http_status"] = details.http_status
    endpoint = endpoint_name or details.endpoint_name
    if endpoint:
        metadata["endpoint_name"] = endpoint

    return metadata


def log_fields_for_mirror_failure(
    *,
    exc: BaseException,
    inst_id: str,
    request: PaperOrderRequest,
    paper_order_id: str,
) -> dict[str, Any]:
    """Fields safe for structlog on demo mirror failure."""
    meta = build_demo_mirror_failure_metadata(
        exc=exc,
        request=request,
        paper_order_id=paper_order_id,
        inst_id=inst_id,
        exchange_mode="paper_exchange_demo",
    )
    # structlog already redacts, but keep messages bounded.
    if "venue_error_message" in meta:
        meta["venue_error_message"] = str(meta["venue_error_message"])[:200]
    return meta
