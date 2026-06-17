# Paper Validation (Slice 35, 38, 39, 40)

Paper validation tracks **simulated paper trades** via the paper bot runtime. No exchange orders. Real trading remains disabled.

## Scheduler foundation (Slice 40)

Optional paper validation scheduler — **disabled by default**.

| Setting | Default | Purpose |
|---------|---------|---------|
| `ENABLE_PAPER_SCHEDULER` | `false` | Env gate — must be true for any automated tick |
| Tenant `enabled` | `false` | Per-org opt-in via `PATCH /paper-validation/scheduler/config` |
| `interval_seconds` | 300 | Safe interval between cycles |
| `max_runs_per_cycle` | 5 | Cap active runs processed per tick |
| `max_scans_per_minute` | 10 | Rate limit |

**v1:** manual `POST /paper-validation/scheduler/tick` (owner role). No fragile always-on background job by default.

Scheduler skips runs when: strategy blocked, run stopped/restricted, stale data, rate limit exceeded.

## Runtime history (Slice 40)

`paper_validation_runtime_history` records each scan/tick/scheduler cycle: status (`skipped`, `success`, `failed`, `partial`), blockers, warnings, data freshness, latency, redacted errors.

`GET /paper-validation/scheduler/history`

## Alerts (Slice 40–41)

`paper_validation_alerts` stores tenant-scoped in-app alerts. Slice 41 adds optional external delivery (disabled by default) and delivery status fields. See [alerts.md](./alerts.md).

Types: `setup_signal_detected`, `paper_trade_opened`, `paper_trade_closed`, `stop_hit`, `tp_hit`, `runner_exit`, `strategy_blocked`, `data_stale`, `promotion_status_changed`, `paper_validation_restricted`, `overtrading_warning`, `daily_loss_lock_warning`.

API: `GET /alerts`, delivery endpoints, `PATCH /alerts/{id}/read`. Marking read does not mutate delivery status.

## Market watcher bridge (Slice 42)

Connects read-only observations to eligible paper validation **scans** — disabled by default (`MARKET_WATCHER_BRIDGE_ENABLED=false`). Manual bridge tick via API or agent (owner + confirmation). Records decisions and creates alerts with source `market_watcher_bridge`. Never places real orders.

## Market watcher prep (Slice 41)

Read-only market scanning foundation — disabled by default. See [market_watcher.md](./market_watcher.md). Feeds paper validation scan decisions; never places orders.

## 7-day sample windows (Slice 40)

`paper_validation_sample_windows` — simple 7-day buckets from closed paper trades (not full walk-forward optimization): trades_count, win_rate, net_pnl, max_drawdown, expectancy, recommendation, data_quality.

Promotion now also requires minimum runtime windows and checks stale data / provider failures.

## Runtime model (Slice 39)

| Entity | Purpose |
|--------|---------|
| `paper_validation_runs` | Active validation session with mode, config, metrics |
| `paper_signals` | Detected setups from structured rule scan |
| `paper_trades` | Simulated trades (open = position, closed = history) |
| `paper_trade_events` | Lifecycle audit (opened, closed) |
| `paper_validation_metric_snapshots` | Point-in-time metrics after each close |

Each paper trade stores: strategy/version/run ids, symbol, exchange, timeframe, direction, entry/exit, stop, TP/runner plans, fees, slippage, PnL, `rule_engine_source`, `created_from_signal_id`.

## Runtime modes

| Mode | Behavior |
|------|----------|
| `scan_only` (default) | Detect setup → create `paper_signal` — **no** simulated trade |
| `auto_paper` | After deterministic checks → open simulated `paper_trade` |

There is **no real mode**. No exchange order APIs are called.

## Manual tick (v1)

Use:

- **UI:** Run scan / Run tick / Manual scheduler tick in Strategy Lab
- **API:** `POST /paper-validation/{run_id}/tick`, `POST /paper-validation/scheduler/tick`

Optional in-process background loop is **not implemented** — only manual `POST /paper-validation/scheduler/tick` when `ENABLE_PAPER_SCHEDULER=true`.

## Paper bot engine v1

`PaperBotEngine` / `PaperValidationRuntimeService`:

1. Load paper-eligible strategy + structured rules
2. Fetch recent OHLCV candles (mock or stored)
3. Evaluate entry via structured rules (same resolver as backtest)
4. Apply no-trade filters
5. Create paper signal
6. In `auto_paper`, open simulated trade with fees/slippage
7. On tick, monitor open trades — stop, TP, runner, timeout
8. Update metrics and promotion recommendation

Non-machine-testable rules → `not_testable` signal + blocker (no fake trades).

## Metrics

Updated after each closed paper trade:

- trade count, win rate, net/gross PnL, profit factor, expectancy
- **max_drawdown_pct** (equity curve based — no longer placeholder)
- total fees, slippage, average win/loss, consecutive losses
- average holding time, stop respected, early exit, runner helped counts

## Promotion (paper only)

Recommendation may be: `continue`, `improve`, `restrict`, `retire`, `insufficient_data`, `paper_validated`.

`paper_validated` requires (conservative): min trades, positive expectancy, PF ≥ 1.1, max DD ≤ 25%, stop respect, no critical lesson blockers, enough samples/time.

**Does not promote to live trading.**

## Paper eligibility gates (Slice 38)

See `GET /strategies/{id}/paper-eligibility` for: `needs_structure`, `needs_backtest`, `needs_more_sample`, `needs_lesson_review`, `paper_eligible`, `paper_validation_running`, `paper_validated`, `restricted`.

Accepted lessons vs pending observations: only **accepted** lessons affect promotion; pending candidates are blockers when critical.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/strategies/{id}/paper-validation/start` | Start run (`runtime_mode`, optional `config`) |
| POST | `/paper-validation/{run_id}/scan` | Scan for signals |
| POST | `/paper-validation/{run_id}/tick` | Monitor/close open trades |
| GET | `/paper-validation/{run_id}` | Run detail |
| GET | `/paper-validation/{run_id}/signals` | Paper signals |
| GET | `/paper-validation/{run_id}/trades` | Paper trades |
| GET | `/paper-validation/{run_id}/positions` | Open positions |
| GET | `/paper-validation/{run_id}/metrics` | Current metrics |
| POST | `/paper-validation/{run_id}/stop` | Stop run |
| GET | `/strategies/{id}/paper-validation` | List runs |
| GET | `/strategies/{id}/paper-eligibility` | Gates and blockers |

## Limitations (v1)

- Partial TP closes full position at first TP (schema supports multi-TP; v1 simplified)
- No autonomous scheduler — manual scan/tick
- Mock/deterministic candles in tests; production uses stored historical data
- Not connected to exchange fills
- Does not enable live trading or change `ENABLE_REAL_TRADING`

## Migration

Apply through head **`u1v2w3x4y5z6`** (Slice 42; prior Slice 41: `t0u1v2w3x4y5`):

```bash
cd backend && uv run alembic upgrade head
```

## Smoke

```bash
./scripts/paper-validation-smoke.sh
./scripts/strategy-smoke.sh
./scripts/market-watcher-smoke.sh   # Slice 42 — watcher + bridge (read-only, paper scan only)
```
