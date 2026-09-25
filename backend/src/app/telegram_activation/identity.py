"""Bot identity checks. The token is never logged."""

from __future__ import annotations

import re

_TOKEN_BOT_ID = re.compile(r"^(\d{1,32}):")


def token_bot_user_id(token: str) -> str | None:
    """Return the numeric bot user id encoded in a Telegram bot token."""

    match = _TOKEN_BOT_ID.match(token.strip())
    if match is None:
        return None
    return match.group(1)


def bot_identity_mismatch(*, bot_id: str, token: str) -> bool:
    """True when a numeric configured bot id disagrees with the token prefix.

    Opaque test identities are not numeric, so they are not compared. A numeric
    ``TELEGRAM_BOT_ID`` must be the bot user id in the token.
    """

    configured = bot_id.strip()
    prefix = token_bot_user_id(token)
    if prefix is None or not configured.isdigit():
        return False
    return configured != prefix
