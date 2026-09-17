"""Enrollment-aware rate-limit contract for the Telegram protocol."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.telegram_security.clock import Clock
from app.telegram_security.errors import TelegramRateLimitedError


@dataclass(frozen=True)
class RateLimitPolicy:
    enrollment_per_user: int = 10
    enrollment_window: timedelta = timedelta(seconds=60)
    callback_per_user: int = 30
    callback_window: timedelta = timedelta(seconds=60)
    callback_per_chat: int = 60
    callback_chat_window: timedelta = timedelta(seconds=60)


@dataclass
class ProtocolRateLimiter:
    """Sliding window keyed by enrollment/callback identity. Uses the protocol clock."""

    clock: Clock
    policy: RateLimitPolicy = field(default_factory=RateLimitPolicy)
    _events: dict[str, list[datetime]] = field(default_factory=lambda: defaultdict(list))

    def check_enrollment(self, *, organization_id: str, user_id: str) -> None:
        self._check(
            key=f"enroll:{organization_id}:{user_id}",
            limit=self.policy.enrollment_per_user,
            window=self.policy.enrollment_window,
            scope="enrollment",
        )

    def check_callback(self, *, bot_id: str, telegram_user_id: str, chat_id: str) -> None:
        self._check(
            key=f"callback-user:{bot_id}:{telegram_user_id}",
            limit=self.policy.callback_per_user,
            window=self.policy.callback_window,
            scope="callback_user",
        )
        self._check(
            key=f"callback-chat:{bot_id}:{chat_id}",
            limit=self.policy.callback_per_chat,
            window=self.policy.callback_chat_window,
            scope="callback_chat",
        )

    def _check(self, *, key: str, limit: int, window: timedelta, scope: str) -> None:
        now = self.clock.now()
        cutoff = now - window
        retained = [stamp for stamp in self._events[key] if stamp > cutoff]
        if len(retained) >= limit:
            raise TelegramRateLimitedError(scope=scope)
        retained.append(now)
        self._events[key] = retained
