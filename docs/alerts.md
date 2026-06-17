# Paper Validation Alerts (Slice 40–42)

Alerts are **stored and displayed in-app**. External delivery is **disabled by default** (Slice 41).

## Alert sources (Slice 42)

Each alert exposes `alert_source` derived from metadata:

- `paper_validation_runtime` (default)
- `market_watcher`
- `market_watcher_bridge`
- `manual_action`

## In-app alerts

All paper validation events create tenant-scoped in-app alerts. No real trades are executed from alerts.

## External delivery (Slice 41/46)

| Env flag | Default | Purpose |
|----------|---------|---------|
| `ALERT_DELIVERY_ENABLED` | `false` | Master switch for external delivery |
| `ALERT_WEBHOOK_ENABLED` | `false` | Webhook provider |
| `ALERT_WEBHOOK_URL` | empty | Webhook target (never commit secrets) |
| `ALERT_WEBHOOK_SECRET` | empty | Optional HMAC signing secret (Slice 42) |
| `TELEGRAM_ALERTS_ENABLED` | `false` | Telegram provider (Slice 46) |
| `TELEGRAM_BOT_TOKEN` | empty | Bot token — env only, never in DB |
| `TELEGRAM_CHAT_ID` | empty | Optional staging chat id |
| `EMAIL_ALERTS_ENABLED` | `false` | Placeholder stub |

User notification preferences (`/notifications/preferences`) gate webhook and Telegram per user. See [notifications.md](notifications.md).

When disabled, `delivery_status=disabled` and alerts remain in-app only.

### Webhook provider

When enabled, POSTs a JSON payload with idempotency key, event id, timestamp, and optional HMAC signature (`X-AlphaTrade-Signature` when `ALERT_WEBHOOK_SECRET` is set). Headers include `X-AlphaTrade-Alert-Id`, `X-AlphaTrade-Event-Id`, `X-AlphaTrade-Idempotency-Key`, `X-AlphaTrade-Timestamp`. Webhook URL and errors are redacted in logs. Retries stop after `ALERT_WEBHOOK_MAX_RETRIES`; failed delivery keeps the alert in-app.

### Delivery status fields

- `delivery_status`: `pending`, `delivered`, `failed`, `skipped`, `disabled`
- `delivery_channel`: `in_app`, `webhook`, `telegram`, `email`, `push`
- `delivery_attempts`, `last_delivery_error` (redacted), `delivered_at`, `next_retry_at`
- `delivery_skipped_reason`, `retry_exhausted` (Slice 46)

Delivery respects alert dedup keys — duplicate alerts are suppressed at creation, not re-sent externally.

## Alert types

- `setup_signal_detected`
- `paper_trade_opened` / `paper_trade_closed`
- `stop_hit`, `tp_hit`, `runner_exit`
- `strategy_blocked`, `data_stale`
- `promotion_status_changed`, `paper_validation_restricted`
- `overtrading_warning`, `daily_loss_lock_warning`

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/alerts` | List alerts |
| GET | `/alerts/summary` | Unread count and breakdown |
| GET | `/alerts/{id}` | Single alert |
| PATCH | `/alerts/{id}/read` | Mark one read (does not change delivery status) |
| PATCH | `/alerts/read-all` | Mark all read |
| GET | `/alerts/delivery-status` | External delivery configuration |
| GET | `/alerts/delivery-summary` | Delivery status counts |
| POST | `/alerts/{id}/deliver` | Manual deliver (owner) |
| POST | `/alerts/deliver-pending` | Deliver pending batch (owner) |

Notification preferences: see [notifications.md](notifications.md).

## UI

- **Alerts** (`/alerts`) — unread count, severity, type label, delivery status, mark read, optional deliver when enabled
- Strategy Lab paper panel — recent alerts inline

Real trading remains disabled. Paper validation only.
