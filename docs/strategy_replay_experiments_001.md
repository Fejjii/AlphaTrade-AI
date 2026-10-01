# Strategy replay and experiments 001

Branch: `codex/strategy_replay_experiments_001`
Exact parent: PR160 `78635e60e4f745fd50d6dc181b555a6948562077`.
Draft review should target `codex/release_consolidation_wave_001`, because PR160
is still open. No PR168 content is imported.

## Scope and authorities

This is a Nested Continuation research adapter over the existing backtest
lifecycle, not a separate backtesting platform. It reuses `HistoricalCandle`,
`BacktestDataset`, `BacktestRun`, `BacktestTrade`, `RiskEngine`, backtest fill,
funding, excursion and metric calculators, audit records, and the canonical
backtest-to-journal path. No database migration or dependency change is needed.

A replay uses an explicit immutable strategy-version ID and an existing frozen
dataset ID. It never selects the latest strategy version, acquires market data,
creates execution Candidates, writes operational Brain setups, calls an exchange,
changes Watcher or Telegram state, or promotes/approves a strategy. Draft versions
can be researched without becoming executable. Historical rows are shared market
data; strategy versions and job reads remain tenant-scoped.

Jobs carry normal backtest run UUIDs and queue/running/completed/failed/cancelled
states. The existing worker and worker-disabled background fallback execute them.
Results, all candidate lifecycle observations, blocked reasons, missing evidence,
and simulated risk verdicts live in the existing run result JSON. Simulated
trades live in `backtest_trades`; extra targets, R, holding periods and setup IDs
are bound by the result hash and enriched into the existing trade-list endpoint.
Optional explicit journaling preserves exact strategy-version and backtest-trade
lineage and projects measured targets. Existing journal/statistics/analytics can
consume those `source=backtest` records; replay does not manufacture paper trades.

## API

`POST /backtests/replays` (Trader, HTTP 201) accepts:

```json
{
  "strategy_version_id": "<immutable Nested version UUID>",
  "dataset_id": "<existing backtest dataset UUID>",
  "idempotency_key": "nested-baseline-001",
  "minimum_sample": 30,
  "windows": {
    "training_start": "2026-09-01T00:00:00Z",
    "training_end": "2026-09-15T00:00:00Z",
    "evaluation_start": "2026-09-15T00:00:00Z",
    "evaluation_end": "2026-09-30T00:00:00Z",
    "as_of": "2026-10-01T00:00:00Z"
  },
  "assumptions": {
    "symbol": "BTCUSDT",
    "exchange": "binance",
    "timeframe": "15m",
    "initial_capital": "10000",
    "risk_per_trade_pct": "0.1",
    "fees_bps": "4",
    "slippage_bps": "5",
    "funding_rate_bps_per_8h": "0"
  }
}
```

The example describes the request shape, not a measured dataset or recommended
risk parameter. Exact Nested parameters come exclusively from the immutable
version's `pattern_spec`; there are no per-run parameter overrides. Research a
proposal by explicitly forking a version through existing strategy versioning.
The returned `replay_config` exposes the exact saved configuration even while
the job is queued. The normalized request, spec, version content hash, canonical risk limits,
assumptions, engine version and input hashes are frozen in `config_snapshot`.
An idempotency key cannot be reused for different content or another user.

Use existing `GET /backtests/{id}`, `GET /backtests/{id}/trades`,
`POST /backtests/{id}/cancel`, `POST /backtests/{id}/verify`, and
`POST /backtests/{id}/journal-trades` to observe, verify or explicitly journal a
job. A failed or cancelled job cannot be journaled. Verification reuses the
frozen configuration and rejects changed dataset content, close times, stale
flags or job/version identity. It does not duplicate trades or rerun promotion.

`POST /backtests/replays/compare` accepts `baseline_run_id` and `proposed_run_id`.
Both must be completed replays in the caller's tenant, with identical dataset,
input hash, assumptions, windows, direction, family, symbol, timeframe, risk
limits, engine version and sample threshold. It returns exact version/run IDs,
a deterministic comparison hash, both windows' counts/states and the evaluation
net-PnL difference. Missing evaluation data makes the difference null. Its
comparison/result identities are recorded through the existing audit authority
(`BACKTEST_RUN_VERIFIED`, operation `strategy_replay_comparison`). Comparing a
run to itself is a useful zero-difference control.

## Causality and deterministic assumptions

Windows are UTC-aware and half-open: `training_start < training_end <=
evaluation_start < evaluation_end <= as_of`. They must align to complete candle
coverage. No candle crosses the training/evaluation boundary; no position,
account equity, risk history or detector episode crosses it. Each segment starts
with the declared capital. Aggregate metrics pool trades descriptively; the
per-window reports carry independent sample counts and net PnL. There is no
optimizer, fitting, rolling overlap, random search or promotion path.

The existing Nested detector walks candles chronologically. Pivots become usable
only after their right-hand confirmation bars close. The adapter emits
prefix-stable, time-checked events; execution consumes only the event at the
current candle. Confirmation at a candle close can enter only at the next
candle open. Confirmation on the final candle is recorded as blocked, without
an invented fill. Structural stop and measured target are rechecked at that
open; a gap through either invalidates entry. Concurrent confirmations,
occupied positions and trade caps are observable blocks.

Stops win when both stop and target are touched in one bar. A stop gap exits at
the adverse open, with no use of that bar's later extrema or funding. Otherwise
intrabar exit timestamps are represented by candle end; exact intrabar timing
cannot be inferred. The first measured target closes full size; no synthetic
3R/4R target or runner is introduced. MAE/MFE are bounds over held candle ranges,
including the exit bar: extremes may have occurred after an intrabar exit, so
these are explicitly not tick-level excursions. Holding bars/seconds use that
same deterministic convention. R is net PnL divided by initial filled-entry-to-
structural-stop risk times size.

Fees apply to both filled notionals. Adverse slippage changes entry/exit fills
and is also reported as a cost; replay does not subtract it a second time from
PnL. The shared fill helper's legacy AT034 default is retained for old runs.
Funding uses the declared constant rate, prorated over held candles; actual
historical funding is unavailable. Decimal precision and rounding are fixed.

Risk evaluates the canonical `RiskEngine` against an isolated simulated account,
with the complete default `RiskLimits` frozen at creation, prior realized daily
and weekly losses and trade counts, and UTC weekend state from the candle clock.
No live account/user risk state is read or updated. Risk BLOCK prevents entry;
WARN is retained as a research observation, not live approval. Funding, 24-hour
liquidity, mental-capital and live-account evidence are not inferred.

## Missing data and interpretation

Missing window coverage, candle gaps/duplicates, stale rows, wrong identities,
invalid OHLCV or invalid/unclosed intervals produce `missing_data` for that
segment and no fabricated trades. Legacy historical candles store inclusive
`close_time = open + interval - 1 second`; replay accepts that or the exclusive
interval end and normalizes to the full closed interval. Synthetic mock candles
are explicitly disclosed. Snapshot creation refreshes rows from the database
before hashing, preventing in-memory Decimal scale from changing a hash after a
restart. No historical row is rewritten. Non-default legacy runner/sample-size overrides,
legacy split configs, separate start/end dates and non-neutral funding labels
are rejected; replay uses explicit windows and the explicit numeric funding rate.

Unavailable moving-average/higher-timeframe evidence and unsupported CVD,
order flow, open interest and historical funding remain explicit in the result
and candidate evidence map. They are not filled with invented observations.
Each window exposes candle, confirmed candidate, blocked and completed trade
counts. Below the declared threshold the state is `insufficient_sample`; above
it the state is only `descriptive_only`. Cancellation marks unfinished research
as cancelled, including an unvalued open position if interrupted.

`improvement_claim` is always false, even if the proposed version has a better
replay result or the sample threshold is met. A single holdout result does not
establish significance, robustness or future performance. Repeated verification
of one dataset is not independent evidence.

## SFP seam

`ReplayAdapter.events` separates family detection from fill/risk/account logic.
A future SFP adapter must emit chronological, prefix-stable closed-candle events
with exact structural entry/stop/targets and evidence availability. After PR168
consolidation, register its validated immutable family spec and adapter here;
retain the same job, trade, journal and audit authorities and the prefix/leakage
tests. This PR registers only Nested and rejects other family versions.

## Validation and handoff

Validation commands and final results are recorded in `HANDOFF.md`. The focused
suite covers repeated hashes across reloads and different Decimal contexts,
prefix/pivot causality, evaluation isolation, missing-data states, next-open
entries, mirrored stop/gap accounting, simulated risk blocks, immutable version
fork comparisons, journal targets, idempotency, cancellation/failure status,
worker-disabled background execution, verify, tenant fences and Trader RBAC.

No live provider acquisition, live trading, deployment, runtime activation,
shared database migration, merge, or CI wait is part of this task. Stop after
commit, push, draft PR creation and handoff.
