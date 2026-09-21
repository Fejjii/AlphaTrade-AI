"""Paper-mode Telegram interaction layer. Disabled by default. Never executes."""

from app.telegram_paper_agent.contracts import (
    DiscussionIntent,
    PaperAlertRecipient,
    PaperDiscussionResult,
    PaperNotificationIntent,
    PaperNotificationKind,
    PaperNotificationProjection,
    WatcherScanNotice,
)
from app.telegram_paper_agent.errors import (
    PaperActionRefusedError,
    PaperTelegramDisabledError,
    PaperTelegramError,
    PaperTelegramTenantError,
)
from app.telegram_paper_agent.gateway import TelegramPaperAgent
from app.telegram_paper_agent.memory import InMemoryPaperAgentStore, InMemoryPaperContext

__all__ = [
    "DiscussionIntent",
    "InMemoryPaperAgentStore",
    "InMemoryPaperContext",
    "PaperActionRefusedError",
    "PaperAlertRecipient",
    "PaperDiscussionResult",
    "PaperNotificationIntent",
    "PaperNotificationKind",
    "PaperNotificationProjection",
    "PaperTelegramDisabledError",
    "PaperTelegramError",
    "PaperTelegramTenantError",
    "TelegramPaperAgent",
    "WatcherScanNotice",
]
