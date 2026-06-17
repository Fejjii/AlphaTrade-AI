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
- `paper_eligible` requires multi-gate evaluation (Slice 38) — not a single backtest alone

## Slice 38 — paper eligibility gates

`GET /strategies/{id}/paper-eligibility` returns deterministic status:

| Status | Meaning |
|--------|---------|
| `needs_structure` | Testability below threshold or missing stop/invalidation |
| `needs_backtest` | No completed backtest |
| `needs_more_sample` | Backtest sample or metrics below threshold |
| `needs_lesson_review` | Critical unresolved lesson candidates or repeated mistakes pending |
| `paper_eligible` | All gates pass — may start paper validation |
| `paper_validation_running` | Paper validation in progress |
| `paper_validated` | Paper validation passed (still paper only) |
| `restricted` | Negative expectancy or excessive drawdown |

Gates include: testability ≥70, structured rules, completed backtest, min sample (20), positive expectancy, profit factor ≥1.1, max drawdown ≤25%, no critical unresolved lessons for the strategy, stop/invalidation present.

Paper validation dashboard shows blockers, latest backtest metrics, linked accepted lessons, and unresolved lesson candidates. **No live trading promotion.**

## Migration

Requires **`m3n4o5p6q7r8`** (`metrics`, `recommendation`, `ended_at` on paper validation runs).
