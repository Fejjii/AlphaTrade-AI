# Paper Validation (Slice 35)

Paper validation tracks **simulated paper trades** linked to a strategy. No exchange orders. Real trading remains disabled.

## Metrics tracked

Each `paper_validation_runs` record stores:

- `paper_trades_count`
- `win_rate`
- `net_pnl`
- `profit_factor`
- `expectancy`
- `max_drawdown_pct`
- `plan_adherence_avg` (when available)
- `early_exit_count` / `stop_respected_count` (groundwork)
- `recommendation`: `continue`, `improve`, `restrict`, `retire`, `insufficient_data`

Metrics aggregate from closed **paper positions** linked to proposals with `user_strategy_id`.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/strategies/{id}/paper-validation/start` | Start / snapshot validation |
| GET | `/strategies/{id}/paper-validation` | List runs |
| GET | `/strategies/{id}/paper-validation/{run_id}` | Single run with metrics |

## Limitations

- No autonomous paper bot — metrics update from existing paper workflow
- Not connected to exchange fills
- Does not enable live trading or change `ENABLE_REAL_TRADING`
- `paper_eligible` requires conservative backtest promotion first

## Migration

Requires **`m3n4o5p6q7r8`** (`metrics`, `recommendation`, `ended_at` on paper validation runs).
