"""Secret hashing and exact action-payload binding.

Plaintext enrollment tokens and action nonces are returned once to the caller
and never persisted. Comparisons use ``hmac.compare_digest``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable

from pydantic import BaseModel

from app.services.canonical_serialization import canonical_sha256
from app.telegram_security.contracts import InboundReplayFingerprint

TokenFactory = Callable[[], str]


def generate_opaque_token() -> str:
    """Return a callback-data-safe opaque token (Telegram callback_data ≤ 64 bytes)."""
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def secrets_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def payload_binding_hash(payload: BaseModel) -> str:
    """Canonical SHA-256 of the exact action payload bound to a nonce."""
    return canonical_sha256(payload)


def inbound_fingerprint_digest(fingerprint: InboundReplayFingerprint) -> str:
    """Canonical SHA-256 of the exact inbound replay fingerprint."""
    return canonical_sha256(fingerprint)
