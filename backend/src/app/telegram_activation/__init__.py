"""Controlled paper Telegram activation. Disabled unless a caller arms it.

Importing this package does not mount a webhook, start polling, enable Watcher,
or permit Telegram network I/O.
"""

from app.telegram_activation.contracts import ActivationVerdict, PreflightReport
from app.telegram_activation.controller import TelegramPaperActivation
from app.telegram_activation.preflight import defaults_are_safe, run_preflight
from app.telegram_activation.rollback import plan_rollback

__all__ = [
    "ActivationVerdict",
    "PreflightReport",
    "TelegramPaperActivation",
    "defaults_are_safe",
    "plan_rollback",
    "run_preflight",
]
