# Paper Validation (Slice 35, 38, 39)

Paper validation tracks **simulated paper trades** via the paper bot runtime. No exchange orders. Real trading remains disabled.

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

Automated scheduling is deferred. Use:

- **UI:** Run scan / Run tick buttons in Strategy Lab
- **API:** `POST /paper-validation/{run_id}/tick` for tests and smoke scripts

Optional in-process background loop is **disabled by default** for stability.

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

Apply through head **`q7r8s9t0u1v2`** (Slice 39):

```bash
cd backend && uv run alembic upgrade head
```

## Smoke

```bash
./scripts/paper-validation-smoke.sh
./scripts/strategy-smoke.sh
```
