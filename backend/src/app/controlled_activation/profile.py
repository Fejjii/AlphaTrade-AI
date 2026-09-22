"""One paper package. Defaults stay disarmed. Production cannot arm it."""

from __future__ import annotations

from app.core.config import Environment, Settings, TelegramInboundMode
from app.telegram_activation.policy import WEBHOOK_SECRET_MIN_LENGTH


def controlled_telegram_projection(settings: Settings) -> bool:
    """Staging paper projection onto a verified binding.

    Requires the Watcher paper arm and public USD-M evidence. Legacy Telegram
    alerts and automatic delivery stay off. This does not mint a Candidate.
    """

    from app.market_activation.profile import controlled_watcher_arm

    if not controlled_watcher_arm(settings):
        return False
    if settings.perpetual_evidence_source != "binance_usdm":
        return False
    if not settings.telegram_bot_id.strip() or not settings.telegram_chat_id.strip():
        return False
    inbound = settings.telegram_inbound_mode
    if inbound is TelegramInboundMode.POLLING:
        if settings.telegram_webhook_secret.strip():
            return False
    elif inbound is TelegramInboundMode.WEBHOOK:
        if len(settings.telegram_webhook_secret) < WEBHOOK_SECRET_MIN_LENGTH:
            return False
    else:
        return False
    return (
        settings.telegram_paper_activation_armed
        and settings.telegram_interaction_enabled
        and not settings.telegram_alerts_enabled
        and not settings.automatic_telegram_delivery_enabled
        and settings.environment is Environment.STAGING
    )


def package_disarmed(settings: Settings) -> bool:
    """True when the process is back on replay with Watcher and Telegram off."""

    return (
        settings.execution_mode.value == "paper"
        and not settings.enable_real_trading
        and not settings.real_trading_enabled
        and settings.perpetual_evidence_source == "replay"
        and not settings.watcher_orchestration_enabled
        and not settings.watcher_paper_staging_activation
        and not settings.market_watcher_enabled
        and not settings.telegram_alerts_enabled
        and not settings.telegram_interaction_enabled
        and not settings.automatic_telegram_delivery_enabled
        and not settings.telegram_paper_activation_armed
        and settings.telegram_inbound_mode is TelegramInboundMode.OFF
        and not settings.telegram_network_permitted
        and not settings.telegram_webhook_secret.strip()
    )
