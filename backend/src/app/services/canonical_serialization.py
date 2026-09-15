"""Versioned canonical JSON primitives for trading-semantic hashes."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CanonicalSerializationError(ValueError):
    """Raised when a value has no unambiguous canonical representation."""


def canonical_json_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes without insignificant whitespace."""
    source = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
    canonical = _canonicalize(source)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: BaseModel | dict[str, Any]) -> str:
    """Hash the exact bytes returned by :func:`canonical_json_bytes`."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonicalize(value: Any) -> Any:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        raise CanonicalSerializationError("Binary floating-point values are not canonical.")
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CanonicalSerializationError("Canonical datetimes must be timezone-aware.")
        utc_value = value.astimezone(UTC)
        return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalSerializationError("Canonical JSON object keys must be strings.")
        return {
            unicodedata.normalize("NFC", key): _canonicalize(item)
            for key, item in value.items()
        }
    raise CanonicalSerializationError(
        f"Unsupported canonical value type: {type(value).__qualname__}."
    )


def _canonical_decimal(value: Decimal) -> dict[str, str | int]:
    if not value.is_finite():
        raise CanonicalSerializationError("Canonical decimals must be finite.")
    if value.is_zero():
        return {"scale": 0, "value": "0"}

    normalized = value.normalize()
    sign, digits, exponent = normalized.as_tuple()
    coefficient = int("".join(str(digit) for digit in digits))
    if exponent >= 0:
        coefficient *= 10**exponent
        scale = 0
    else:
        scale = -exponent
    if sign:
        coefficient = -coefficient
    return {"scale": scale, "value": str(coefficient)}
