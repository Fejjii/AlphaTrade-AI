"""Canonical JSON / dataset hashing for deterministic backtests (AT-034).

Hashes are process-stable: sorted keys, fixed separators, Decimal via
``format(d, "f")``, datetimes as UTC ISO-8601, StrEnums as their values.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol


class _CandleLike(Protocol):
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str


def _to_utc_iso(value: datetime) -> str:
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return format(obj, "f")
    if isinstance(obj, datetime):
        return _to_utc_iso(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="python")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical JSON bytes (UTF-8)."""
    return json.dumps(
        obj,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_hash(obj: Any) -> str:
    """SHA-256 hex digest of canonical JSON for ``obj``."""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def dataset_content_hash(rows: Sequence[_CandleLike]) -> str:
    """Hash ordered candle content lines for an immutable dataset snapshot.

    Each line: ``open_time_utc_iso|open|high|low|close|volume|source`` with
    Decimals via ``format(d, "f")``.
    """
    lines: list[str] = []
    for row in rows:
        lines.append(
            "|".join(
                (
                    _to_utc_iso(row.open_time),
                    format(row.open, "f"),
                    format(row.high, "f"),
                    format(row.low, "f"),
                    format(row.close, "f"),
                    format(row.volume, "f"),
                    row.source,
                )
            )
        )
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
