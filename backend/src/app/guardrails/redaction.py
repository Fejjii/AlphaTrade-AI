"""Reusable secret and PII redaction for logs, traces, audit metadata, and errors."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_REDACTED = "***REDACTED***"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), _REDACTED),
    (re.compile(r"sk_(test|live)_[a-zA-Z0-9]{16,}", re.IGNORECASE), _REDACTED),
    (re.compile(r"whsec_[a-zA-Z0-9]{16,}", re.IGNORECASE), _REDACTED),
    (re.compile(r"pk_(test|live)_[a-zA-Z0-9]{16,}", re.IGNORECASE), _REDACTED),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), f"Bearer {_REDACTED}"),
    (
        re.compile(r"Authorization:\s*[^\s,;]+", re.IGNORECASE),
        f"Authorization: {_REDACTED}",
    ),
    (
        re.compile(
            r"(api[_-]?key|access[_-]?token|refresh[_-]?token|exchange[_-]?secret"
            r"|client[_-]?secret)\s*[:=]\s*['\"]?[^\s'\",;]+",
            re.IGNORECASE,
        ),
        r"\1=" + _REDACTED,
    ),
    (
        re.compile(
            r"(mongodb|postgres|postgresql|mysql|redis)://[^\s'\"]+",
            re.IGNORECASE,
        ),
        r"\1://" + _REDACTED,
    ),
    (
        re.compile(r"password\s*[:=]\s*['\"]?[^\s'\",;]+", re.IGNORECASE),
        "password=" + _REDACTED,
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        _REDACTED,
    ),
    (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        _REDACTED,
    ),
]

_SENSITIVE_KEYS = frozenset(
    {
        "openai_api_key",
        "api_key",
        "authorization",
        "password",
        "token",
        "secret",
        "access_token",
        "refresh_token",
        "verification_token",
        "reset_token",
        "invite_token",
        "exchange_secret",
        "bearer",
        "stripe_secret_key",
        "stripe_webhook_secret",
        "stripe_signature",
        "webhook_signature",
    }
)


def redact_text(value: str) -> str:
    """Redact secrets and sensitive patterns from a string."""
    if not value:
        return value
    redacted = value
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside mappings and sequences."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return redact_mapping(dict(value))
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Redact mapping values and mask known sensitive keys."""
    result: dict[str, Any] = {}
    for key, raw in data.items():
        if key.lower() in _SENSITIVE_KEYS and raw:
            result[key] = _REDACTED
        else:
            result[key] = redact_value(raw)
    return result


def redact_for_log(event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog-compatible processor for centralized log redaction."""
    return redact_mapping(event_dict)
