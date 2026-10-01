"""Incremental SHA-256 for canonical trade-set documents.

The bytes match :func:`app.services.canonical_serialization.canonical_sha256`.
Callers can hash a long trade tape without building the document in memory.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata


def _json_string(value: str) -> bytes:
    normalized = unicodedata.normalize("NFC", value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


class TradeSetHasher:
    """Hash ``{"events":[{"content_hash","sequence","venue_trade_id"}, ...]}``."""

    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self._digest.update(b'{"events":[')
        self._count = 0
        self._closed = False

    def add(self, *, venue_trade_id: str, sequence: int, content_hash: str) -> None:
        if self._closed:
            raise RuntimeError("Trade-set hasher is already closed.")
        if self._count:
            self._digest.update(b",")
        self._count += 1
        self._digest.update(b'{"content_hash":')
        self._digest.update(_json_string(content_hash))
        self._digest.update(b',"sequence":')
        self._digest.update(str(int(sequence)).encode("ascii"))
        self._digest.update(b',"venue_trade_id":')
        self._digest.update(_json_string(venue_trade_id))
        self._digest.update(b"}")

    def hexdigest(self) -> str:
        if not self._closed:
            self._digest.update(b"]}")
            self._closed = True
        return self._digest.hexdigest()


class VenueIdSetHasher:
    """Hash ``{"venue_trade_ids":["id", ...]}`` in the given order."""

    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self._digest.update(b'{"venue_trade_ids":[')
        self._count = 0
        self._closed = False

    def add(self, venue_trade_id: str) -> None:
        if self._closed:
            raise RuntimeError("Venue-id hasher is already closed.")
        if self._count:
            self._digest.update(b",")
        self._count += 1
        self._digest.update(_json_string(venue_trade_id))

    def hexdigest(self) -> str:
        if not self._closed:
            self._digest.update(b"]}")
            self._closed = True
        return self._digest.hexdigest()
