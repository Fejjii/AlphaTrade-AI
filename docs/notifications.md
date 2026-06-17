# Notifications (Slice 46)

User-scoped notification preferences control **how** paper validation alerts are delivered. Provider secrets stay in environment variables — never in the database.

## In-app alerts

Always stored for tenant-scoped paper validation events. Default: enabled.

## External delivery (disabled by default)

External channels require:

1. `ALERT_DELIVERY_ENABLED=true` (global master switch)
2. Per-channel env flags and configuration
3. User preference toggles (`webhook_enabled`, `telegram_enabled`)

Alerts **never execute trades**. Paper validation only.

## Provider environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALERT_DELIVERY_ENABLED` | `false` | Master switch |
| `ALERT_WEBHOOK_ENABLED` | `false` | Webhook provider |
| `ALERT_WEBHOOK_URL` | empty | Webhook target URL |
| `ALERT_WEBHOOK_SECRET` | empty | Optional HMAC signing secret |
| `ALERT_WEBHOOK_TIMEOUT_SECONDS` | `5` | HTTP timeout |
| `ALERT_WEBHOOK_MAX_RETRIES` | `2` | Retry cap per alert |
| `TELEGRAM_ALERTS_ENABLED` | `false` | Telegram provider |
| `TELEGRAM_BOT_TOKEN` | empty | Bot token (secret — env only) |
| `TELEGRAM_CHAT_ID` | empty | Default chat id for staging |
| `TELEGRAM_TIMEOUT_SECONDS` | `5` | HTTP timeout |
| `TELEGRAM_MAX_RETRIES` | `2` | Retry cap per alert |

Per-user `telegram_chat_id` may be stored in preferences (chat id only, not the bot token).

## Notification preferences API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/notifications/preferences` | Current preferences |
| PATCH | `/notifications/preferences` | Partial update |
| POST | `/notifications/preferences/reset-defaults` | Reset to defaults |
| POST | `/notifications/test` | Safe test notification |

Fields: `in_app_enabled`, `webhook_enabled`, `telegram_enabled`, `min_severity`, `enabled_alert_types`, `quiet_hours_*`, `timezone`, `digest_mode`.

## Webhook delivery

Signed payloads when `ALERT_WEBHOOK_SECRET` is set (`X-AlphaTrade-Signature`). Unsigned mode when secret is missing. Stable `idempotency_key` per alert (`alert-deliver:{alert_id}`). Errors and URLs redacted in logs.

## Telegram delivery

Uses Telegram Bot API `sendMessage`. Disabled unless env flag, bot token, chat id, and user preference are all enabled. Bot token never logged.

## Delivery routing

`DeliveryRoutingService` evaluates severity threshold, alert type filters, quiet hours, digest mode, and provider availability before external send.

## Retry behavior

Failed deliveries retry with backoff until `ALERT_WEBHOOK_MAX_RETRIES` or `TELEGRAM_MAX_RETRIES`. Exhausted retries set `retry_exhausted` and keep the alert in-app.

## Agent tools

`notification_preferences_tool` — get/update preferences, test send, webhook/Telegram status. Mutations require explicit confirmation.

`paper_validation_tool` actions: `alert_delivery_status`, `alert_delivery_reason`, `deliver_pending`.

## Limitations

- No email/push production providers yet (stubs)
- Daily digest mode defers immediate external delivery
- No per-organization webhook URLs (env-global staging pattern)
