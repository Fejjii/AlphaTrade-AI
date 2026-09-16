"""Content hashes for market evidence.

Hashes exclude database IDs, receive/recorded time, request/trace metadata, and
mutable processing status. They include semantic source time, natural event
identity, values/units, venue/market/instrument, finality evidence, and
normalization policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.services.canonical_serialization import canonical_sha256

RECEIVE_AND_TRANSPORT_FIELDS = frozenset(
    {
        "observation_id",
        "trade_event_id",
        "cursor_id",
        "cvd_window_id",
        "receive_time",
        "receive_timestamp",
        "receive_time_max",
        "recorded_at",
        "created_at",
        "updated_at",
        "retrieved_at",
        "request_id",
        "trace_id",
        "correlation_id",
        "connected_at",
    }
)
CONTENT_HASH_EXCLUDE = frozenset({"content_hash"})


def semantic_content_hash(
    value: BaseModel | Mapping[str, Any],
    *,
    extra_exclude: frozenset[str] = frozenset(),
) -> str:
    """SHA-256 of the canonical semantic preimage."""
    source = value.model_dump(mode="python") if isinstance(value, BaseModel) else dict(value)
    exclude = RECEIVE_AND_TRANSPORT_FIELDS | extra_exclude
    preimage = {key: item for key, item in source.items() if key not in exclude}
    return canonical_sha256(preimage)


def with_content_hash[T: BaseModel](value: T, *, extra_exclude: frozenset[str] = frozenset()) -> T:
    digest = semantic_content_hash(value, extra_exclude=CONTENT_HASH_EXCLUDE | extra_exclude)
    return value.model_copy(update={"content_hash": digest})
