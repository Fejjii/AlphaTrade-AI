# Paper Validation Alerts (Slice 40)

Alerts are **stored and displayed in-app only**. Telegram, email, and push delivery are deferred.

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
| GET | `/alerts` | List alerts (filter by type, severity, unread) |
| GET | `/alerts/summary` | Unread count and breakdown |
| GET | `/alerts/{id}` | Single alert |
| PATCH | `/alerts/{id}/read` | Mark one read |
| PATCH | `/alerts/read-all` | Mark all read |

## UI

- **Alerts** nav page (`/alerts`) — unread count, filters, mark read
- Strategy Lab paper panel — recent alerts inline

All alerts are paper-validation scoped. Real trading remains disabled.
