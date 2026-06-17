"""Explicit confirmation policy for chat-initiated state mutations (Slice 40C)."""

from __future__ import annotations

import re


def is_question_message(message: str) -> bool:
    """True when the user is asking rather than commanding."""
    lowered = message.strip().lower()
    if lowered.endswith("?"):
        return True
    question_starts = (
        "should i ",
        "can i ",
        "could i ",
        "would you ",
        "do you think ",
        "what if ",
        "is it ok ",
        "is it okay ",
        "am i ",
    )
    return any(lowered.startswith(prefix) for prefix in question_starts)


def has_explicit_confirmation(message: str, *, confirm_arg: bool | None = None) -> bool:
    """True when the user supplied an explicit confirmation token."""
    if confirm_arg is True:
        return True
    lowered = message.lower()
    return (
        "confirm=true" in lowered
        or re.search(r"\b(i confirm|confirmed|confirm action|yes confirm)\b", lowered) is not None
    )


def mutation_allowed(message: str, *, confirm_arg: bool | None = None) -> bool:
    """State-changing chat actions require a non-question message with explicit confirmation."""
    if is_question_message(message):
        return False
    return has_explicit_confirmation(message, confirm_arg=confirm_arg)
