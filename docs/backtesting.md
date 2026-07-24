# Backtesting v2 (AT-034)

Deterministic **backtest engine v2** (`ENGINE_VERSION=at034-2.0.0`) replays stored historical OHLCV candles as a pure function of frozen configuration, immutable dataset snapshots, and structured strategy rules. Historical simulation only — **not** a profit guarantee. **Real trading remains disabled** (`enable_real_trading=false`, `execution_mode=paper`). Backtest output is **record-only** and **never feeds execution, risk, or position-sizing decisions**.

See also: [journal_intelligence_foundation.md](journal_intelligence_foundation.md) (journal bulk import from backtests) · [strategy_library.md](strategy_library.md) · [paper_validation.md](paper_validation.md)

## Architecture overview

| Layer | Responsibility |
|-------|----------------|
| **Config snapshot** | At create time, `BacktestService` freezes `config_snapshot` (strategy card, structured rules, setup type, assumptions, `engine_version`, `dataset_hash`) and `config_hash` (canonical JSON SHA-256). These never change for the run. |
| **Immutable datasets** | `BacktestDatasetService` ensures candles exist, then snapshots or reuses a `backtest_datasets` row keyed by `dataset_hash`. Rows are never updated. |
| **Engine** | `BacktestEngineService.run()` is deterministic: same inputs → same `result_hash`. No wall-clock reads inside the bar loop. |
| **Result hash** | `result_hash` is SHA-256 over canonical JSON of the full `BacktestResult` payload (metrics, trades, splits, excursions, etc.). |
| **Verify** | `POST /backtests/{id}/verify` re-runs the frozen config against the stored dataset (`persist=False`), compares `result_hash`, and checks dataset integrity. |

Migration: **`m9b0c1d2e3f4`** (`backtest_datasets`, dataset linkage on `backtest_runs`, excursion columns on `backtest_trades`).

```bash
cd backend && uv run alembic upgrade head
```

## Lifecycle and statuses

| Status | Meaning |
|--------|---------|
| `queued` | Run created; waiting for sync execution or worker/BackgroundTasks drain. |
| `running` | Worker claimed the run and is simulating. |
| `cancel_requested` | User requested cancel while running; engine checks every 2000 bars. |
| `cancelled` | Terminal — queued cancel or in-loop cancellation converged. |
| `completed` | Terminal — metrics and trades persisted. |
| `failed` | Terminal — unhandled engine error; `error_message` set. |

**Create flow:** `POST /strategies/{id}/backtests` → freeze config + dataset → `QUEUED` → if `total_bars <= backtest_sync_max_bars`, execute synchronously; else stay `QUEUED` and drain via worker loop (1 run/cycle) or `BackgroundTasks` when `worker_enabled=false`.

**Cancel:** `POST /backtests/{id}/cancel` — queued runs become `cancelled` immediately; running runs become `cancel_requested` and converge to `cancelled` when the engine observes the flag.

**Idempotency:** Optional `idempotency_key` per org converges to the same run id on retry.

**Active-run cap:** `backtest_max_active_runs_per_org` (default 2) limits concurrent `queued`/`running`/`cancel_requested` runs per organization.

## Settings (defaults from `Settings`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `backtest_max_bars` | 20_000 | Refuse runs exceeding this bar count (no truncation). |
| `backtest_sync_max_bars` | 6_000 | Sync path threshold; larger datasets stay queued. |
| `backtest_max_active_runs_per_org` | 2 | Concurrent active run cap. |
| `backtest_journal_bulk_max` | 1_000 | Max trades per bulk journal request. |
| `backtest_tier1_oos_min_trades` | 30 | Setup evidence tier 1 — OOS trade count. |
| `backtest_tier1_oos_min_profit_factor` | 1.3 | Tier 1 — OOS profit factor. |
| `backtest_tier1_min_confirm_trades` | 20 | Tier 1 — non-backtest confirm trades. |
| `backtest_tier2_min_trades` | 30 | Tier 2 — total backtest trades. |
| `backtest_tier2_oos_min_trades` | 15 | Tier 2 — OOS trade count. |
| `backtest_tier2_oos_min_profit_factor` | 1.1 | Tier 2 — OOS profit factor. |

## Walk-forward semantics

Configured via `assumptions.split_config`:

- **`holdout`** — single in-sample / out-of-sample split at `floor(n_bars × (1 − oos_fraction))`. Segments are **independent** (separate equity, separate trade buckets).
- **`rolling`** — sliding windows with `window_bars` and `step_bars`; each window has its own IS/OOS sub-split.
- **`none`** — full range as one in-sample segment.

Each segment requires at least **35 bars** (`WARMUP_BARS` 25 + 10). Shorter segments are skipped with limitations noted in the result.

Per-trade `split_label` (`in_sample` / `out_of_sample`) and aggregated `oos_metrics` are included when OOS trades exist. Warmup bars precede the first tradable index within each segment.

## Simulation semantics

### Entries (structured rules required for reliable replay)

Long and short entries are supported per mode:

| Mode | Long | Short |
|------|------|-------|
| `pullback_ema` | Dip below EMA20 then reclaim above | Poke above EMA then reject below |
| `breakout` | Close above 20-bar high | Close below 20-bar low |
| `liquidity_sweep` | Sweep below swing low and reclaim | Sweep above swing high and reject |

Rule resolution order: **structured** → adapter keywords → default setup → unsupported (`needs_structured_rules`).

### Fees, slippage, funding

- **Fees:** `fees_bps / 10_000 × notional` on entry and exit.
- **Slippage:** adverse adjustment `slippage_bps / 10_000 × price` on entry and exit fills.
- **Funding:** `funding_rate_bps_per_8h` accrues pro-rata per bar duration. **Longs pay** positive funding; **shorts receive** (negative cost) when the rate is positive.

### Runner trail

When a runner exit rule is present and TP1 is hit, `runner_trail_pct` (default 1.5%) trails from bar close — longs trail below close, shorts trail above.

### Intra-bar invariant

When stop and take-profit are both touched in the same bar, **stop wins** (conservative).

### Excursions (in-loop)

Per open trade the engine tracks:

- **MFE / MAE** — max favorable / adverse price and amount.
- **Available profit** — MFE amount (best theoretical exit).
- **Capture %** — realized net PnL vs available profit when available &gt; 0.

## Dataset provenance and degraded data

`backtest_datasets` records `candle_count`, `gap_count`, `stale_count`, `source_counts`, `first_open_time`, `last_open_time`, and `dataset_hash`.

- **Gaps** — counted when consecutive `open_time` deltas exceed one timeframe step.
- **Stale** — candles with `is_stale=true` increment `stale_count`.
- **Degraded** — ingestion limitations mark `data_quality=degraded` in the result.
- **Unreliable** — insufficient bars (&lt; 35) or `total_bars > backtest_max_bars` returns empty trades with `recommendation=unreliable_data` (no silent truncation).

## Bulk journal from backtest

`POST /backtests/{id}/journal-trades` (completed runs only):

- **Dry-run default** — preview row outcomes without persistence.
- **Commit** — creates `journal_trades` with `source=backtest`, `entry_method=auto`, `external_ref=backtest:{run_id}:{trade_id}`, `linked_backtest_trade_id`, and excursion fields copied from the simulated trade.
- **Dedup** — re-commit marks all rows duplicate; no new rows.
- **Cap** — `backtest_journal_bulk_max`; all-or-nothing per request.
- **Audit** — `BACKTEST_JOURNALED`.

## Comparison and setup evidence

### `GET /journal/comparison`

Returns three cohorts with shared filters (`strategy_id`, `strategy_version_id`, date range):

| Cohort | Sources |
|--------|---------|
| `human` | `manual`, `imported` |
| `paper_system` | `paper_execution`, `paper_validation` |
| `backtest` | `backtest` |

### `GET /journal/setup-evidence`

**Advisory only** — never enables trading or overrides the risk engine.

| Tier | Criteria (defaults) |
|------|---------------------|
| **tier1** | OOS n ≥ 30, OOS PF ≥ 1.3, OOS expectancy &gt; 0, ≥ 20 non-backtest confirm trades with positive expectancy |
| **tier2** | Total backtest n ≥ 30, OOS n ≥ 15, OOS PF ≥ 1.1, OOS expectancy &gt; 0 |
| **tier3** | Everything else |

Thresholds are configurable via the `backtest_tier*` settings.

## API summary

| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | `/strategies/{id}/backtests` | Trader | Create run (sync or queued) |
| GET | `/strategies/{id}/backtests` | Trader | List runs |
| GET | `/backtests/{id}` | Trader | Run detail |
| GET | `/backtests/{id}/trades` | Trader | Simulated trades |
| POST | `/backtests/{id}/cancel` | Trader | Cancel queued/running |
| POST | `/backtests/{id}/verify` | Trader | Deterministic re-run check |
| POST | `/backtests/{id}/journal-trades` | Trader | Bulk journal import |
| GET | `/journal/comparison` | Reader | Three-cohort comparison |
| GET | `/journal/setup-evidence` | Reader | Advisory evidence tiers |
| POST | `/market/history/ingest` | Trader | Store candles (ingest before snapshot) |

**RBAC:** Mutations require `OWNER` or `TRADER`. `GET /journal/comparison` and `GET /journal/setup-evidence` allow `VIEWER`. Backtest `GET` routes currently require `TraderDep` (owner/trader only).

## Audit events

| Event | When |
|-------|------|
| `BACKTEST_RUN_CREATED` | Run persisted |
| `BACKTEST_RUN_CANCELLED` | Cancel requested or converged |
| `BACKTEST_RUN_COMPLETED` | Successful finish |
| `BACKTEST_RUN_FAILED` | Engine error |
| `BACKTEST_RUN_VERIFIED` | Verify endpoint |
| `BACKTEST_JOURNALED` | Bulk journal commit |

## Limitations (honest)

- **Single-symbol** per run — no multi-asset portfolio simulation.
- **Provider ingest** — backtests depend on stored `historical_candles`; mock/deterministic in tests, exchange public API when configured. Gaps and stale flags surface explicitly.
- **No parameter optimization** — walk-forward is windowed evaluation only, not optimizing parameters across splits.
- **Simulation vs reality** — fills, funding, and slippage are models; paper and live execution differ. Small samples produce weak or unreliable promotion signals.
- **Vague text rules** — without structured rules, replay may return `needs_structured_rules`.

## Disclaimer

Backtest results are historical simulations for research and journaling. They do not guarantee future performance. AlphaTrade-AI does not execute live orders from backtest output. Passing a backtest or evidence tier does not authorize real trading.
