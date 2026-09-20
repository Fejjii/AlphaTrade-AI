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
        or re.search(r"\b(i confirm|confirm action|yes,?\s*confirm)\b", lowered) is not None
    )


def mutation_allowed(message: str, *, confirm_arg: bool | None = None) -> bool:
    """State-changing chat actions require a non-question message with explicit confirmation."""
    if is_question_message(message):
        return False
    return has_explicit_confirmation(message, confirm_arg=confirm_arg)


_CONFIRMATION_ONLY = re.compile(
    r"^(i confirm|yes,?\s*confirm|confirm action)(\s+(this |the )?(proposal|draft))?\.?$",
    re.IGNORECASE,
)

_CONFIRM_PROPOSAL_ID = re.compile(
    r"^(i confirm|yes,?\s*confirm|confirm action)\s+(this |the )?proposal\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.?$",
    re.IGNORECASE,
)

_REJECTION_ONLY = re.compile(
    r"^(i reject|reject proposal|reject this draft)(\s+(this |the )?(proposal|draft))?\.?$",
    re.IGNORECASE,
)

_REJECT_PROPOSAL_ID = re.compile(
    r"^(i reject|reject proposal|reject this draft)\s+(this |the )?proposal\s+"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.?$",
    re.IGNORECASE,
)


def is_confirmation_only_message(message: str) -> bool:
    """True when the entire message is an explicit confirmation, not a buried injection."""
    return _CONFIRMATION_ONLY.match(message.strip()) is not None


def confirmed_proposal_id(message: str) -> str | None:
    """Return a proposal UUID only when the message is an explicit confirm of that id."""
    match = _CONFIRM_PROPOSAL_ID.match(message.strip())
    if match is None:
        return None
    return match.group(3)


def is_rejection_only_message(message: str) -> bool:
    """True when the entire message is an explicit rejection, not a buried injection."""
    return _REJECTION_ONLY.match(message.strip()) is not None


def rejected_proposal_id(message: str) -> str | None:
    """Return a proposal UUID only when the message is an explicit reject of that id."""
    match = _REJECT_PROPOSAL_ID.match(message.strip())
    if match is None:
        return None
    return match.group(3)


def rejection_allowed(message: str, *, confirm_arg: bool | None = None) -> bool:
    """Rejecting a draft requires an explicit reject/confirm token and is never a question."""
    if is_question_message(message):
        return False
    if confirm_arg is True:
        return True
    lowered = message.lower()
    return has_explicit_confirmation(message, confirm_arg=confirm_arg) or bool(
        re.search(r"\b(i reject|reject proposal|reject this draft)\b", lowered)
    )
