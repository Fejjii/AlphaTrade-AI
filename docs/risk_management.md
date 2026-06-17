# Risk management (paper discipline)

Slice 45 adds tenant-scoped **user risk settings** that drive the daily discipline snapshot and dashboard guidance. Real exchange execution remains disabled.

## User risk settings

Persisted per organization + user in `user_risk_settings`:

| Field | Purpose |
| --- | --- |
| `daily_loss_limit` | Max realized+unrealized paper loss before loss lock |
| `daily_target` | Green-day protection threshold |
| `max_trades_per_day` | Overtrading guard |
| `max_risk_per_trade_percent` | Position sizing guidance (≤ 10%) |
| `default_account_balance` | Paper equity reference |
| `timezone` | Local day boundaries (invalid values fall back to UTC) |
| `green_day_protection_enabled` | Toggle green-day signal |
| `one_loss_stop_enabled` | Lock after first losing closed paper trade today |
| `overtrading_guard_enabled` | Toggle frequency guard |
| `notes` | Optional trader notes |

### API

- `GET /risk/settings` — returns persisted settings or safe system defaults (`using_defaults: true`)
- `PATCH /risk/settings` — partial update; audit logged (`risk_settings_updated`)
- `POST /risk/settings/reset-defaults` — restore system defaults

All routes are auth-protected, tenant-scoped, and rate limited. No broker or live trading paths.

## Daily discipline snapshot resolution

The dashboard daily discipline block resolves limits in order:

1. **`configured_daily_state`** — today's `daily_risk_states` row when present
2. **`user_risk_settings`** — persisted user settings (may initialize today's daily state when loss limit is set)
3. **`system_default`** — engine defaults with explicit limitations

The snapshot includes `risk_settings_source` so the UI never silently invents limits.

## Daily PnL sources (paper only)

Today's paper PnL aggregates:

- Closed **paper-validation** `PaperTrade.net_pnl` (local day)
- Closed **proposal-flow** `Position.realized_pnl`
- Unrealized PnL from open proposal-flow positions only (when available)

Returned in `pnl_sources` with limitations when data is incomplete. No broker data.

## Agent tools

`risk_settings_tool` (deterministic, DB-backed):

- `get` — current settings
- `update` — **requires explicit confirmation** (`confirm=true` or "I confirm")
- `discipline`, `discipline_score`, `open_trades`, `paper_pnl`, `loss_lock_reason`

The LLM explains tool output; it must not invent settings or PnL.

## Limitations

- Paper-validation open trades do not include live unrealized PnL in this slice
- Unrealized PnL uses proposal-flow position marks only
- Settings affect paper discipline guidance, not exchange orders
