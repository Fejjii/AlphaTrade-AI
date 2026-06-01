"""Hashing helpers for one-time account tokens (verification, reset, invite)."""

from __future__ import annotations

import hashlib
import secrets


def generate_account_token() -> str:
    """Return a URL-safe opaque token (never persist in plain text)."""
    return secrets.token_urlsafe(32)


def hash_account_token(token: str) -> str:
    """SHA-256 hex digest for storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
