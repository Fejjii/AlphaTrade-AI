"""Small deterministic extractors. Missing fields stay missing."""

from __future__ import annotations

import re

from app.schemas.common import Timeframe

_SYMBOL = re.compile(r"(?<![A-Z0-9])([A-Z][A-Z0-9]{1,20}(?:USDT|USD))(?![A-Z0-9])")
_DIRECTION = re.compile(r"\b(long|short)\b", re.IGNORECASE)
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "this",
        "that",
        "with",
        "from",
        "what",
        "show",
        "list",
        "my",
        "your",
        "are",
        "was",
        "were",
        "have",
        "has",
        "did",
        "does",
        "not",
        "but",
        "you",
        "into",
        "about",
        "please",
        "trade",
        "trades",
    }
)


def query_tokens(text: str) -> set[str]:
    """Return lowercase tokens used for lexical overlap."""
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.lower()) if token not in _STOP}


def extract_symbol(text: str) -> str | None:
    """Return the first explicit symbol. No default symbol is substituted."""
    match = _SYMBOL.search(text.upper())
    if match is None:
        return None
    return match.group(1)


def extract_direction(text: str) -> str | None:
    """Return long or short only when exactly one direction is named."""
    found = {item.lower() for item in _DIRECTION.findall(text)}
    if len(found) != 1:
        return None
    return str(next(iter(found)))


def extract_timeframe(text: str) -> str | None:
    """Return a supported timeframe token. Longer tokens win over prefixes."""
    lowered = text.lower()
    ordered = sorted((item.value for item in Timeframe), key=len, reverse=True)
    for value in ordered:
        if re.search(rf"(?<![a-z0-9]){re.escape(value)}(?![a-z0-9])", lowered):
            return value
    return None
