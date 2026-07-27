# AT-040 — Analytics & Charts Implementation Blueprint (Phase D)

Status: blueprint (documentation only — no implementation in this slice).
Depends on: AT-039 blueprint (`docs/product/at039_premium_ui_ux_blueprint.md`, §8 chart
standards and §8.2 canonical metric catalog) and the AT-040 design-system foundation
(`docs/product/at040_design_system_foundation.md`, Phase D roadmap row).
Does not change: production frontend code, backend code, shared navigation
(`frontend/src/components/layout/navigation-config.ts`), chart stack, trading/execution/risk
authority.

Every endpoint, query parameter, and response field named in this document was verified
against the repository at the commit this blueprint was authored on. Where a capability does
not exist, it is marked explicitly; nothing below is aspirational unless labeled
`requires backend work`.

---

## 1. Executive summary

AlphaTrade already computes most professional trading statistics **server-side** — win rate,
expectancy, profit factor, average R, MFE/MAE averages, capture ratio, drawdown, dollar
equity curve, daily P&L series, per-symbol/setup/strategy breakdowns, human-vs-system
cohorts, discipline scores, and validation outcome rates. What is missing is almost entirely
**presentation**: no chart library is installed, only two hand-rolled SVG charts exist
(portfolio equity/daily bars and the backtest equity curve), and the Analyze surfaces
(`/analytics`, `/journal/statistics`, `/journal/comparison`, `/learning-analytics`,
`/coaching`, `/strategy-quality`) render scorecards and tables without visual synthesis.

The plan:

1. **Reuse server aggregates.** `GET /journal/statistics` (AT-031) and
   `GET /performance/portfolio` are the two workhorse sources; both already carry
   sample-size confidence, per-family sample counts, `None`-not-zero semantics, warnings,
   and truncation flags. No client-side re-computation of statistics beyond safe
   deterministic transforms (e.g. weekly rollup of a returned daily series).
2. **Adopt the AT-039 Phase D chart stack once** (Recharts for statistical charts; TradingView
   Lightweight Charts stays deferred until a price/candle chart is actually needed — none of
   the charts in this blueprint require it).
3. **Restructure `/analytics` into a progressively disclosed hub** with six sections —
   Overview, Performance, Setups, Behaviour, Validation, Comparison — implemented as
   query-parameter tabs on the existing route (no navigation-config changes).
4. **Respect the canonical-metric rule** (AT-039 §8.2/§8.3): the full equity and drawdown
   charts stay canonical on Portfolio (owned by the parallel Portfolio workstream); the
   Analytics hub owns the statistical charts (daily P&L, distributions, per-setup bars,
   comparison, validation rates) and references Portfolio metrics only as compact stats.
5. **Enforce source honesty**: a failed source renders `ErrorState` with retry, never a
   zero-value chart; small samples always show the server's `confidence` label; derived
   values are labeled as derived.
6. **Ship in four small PRs** (foundation/overview → setups → behaviour/comparison →
   validation/polish) with no file overlap with the parallel Knowledge and Portfolio agents.

Gaps that require backend work before their charts can exist (deliberately excluded from
the four frontend PRs): R-multiple distribution endpoint (or date filters on
`GET /journal/trades`), performance grouped by direction and by holding duration,
discipline **trend over time**, validation outcome **trend over time**, and a
mistake-recurrence aggregate. Each is listed with the exact smallest backend change in §11.

---

## 2. Existing capability inventory (verified)

### 2.1 Backend sources

All routers mount at the application root in `backend/src/app/main.py` (no global `/api`
prefix). Auth: bearer JWT; analytics reads use `ReaderDep` (OWNER | TRADER | VIEWER) from
`backend/src/app/security/rbac.py`.

| Source | Endpoint | What it provides | Key files |
|---|---|---|---|
| Journal statistics (AT-031) | `GET /journal/statistics` | Server-computed closed-trade aggregates with `group_by` ∈ `overall\|setup\|setup_version\|strategy\|strategy_version\|symbol\|timeframe\|market_regime\|source\|entry_method\|rule_compliance\|execution_actor`; filters `source`, `entry_method`, `symbol`, `timeframe`, `market_regime`, `setup_id`, `user_strategy_id`, `strategy_version_id`, `rule_compliance`, `execution_actor`, `date_from`/`date_to` (datetime, applied to `coalesce(exit_time, entry_time, created_at)`); bucket pagination `limit` (default 50, max 200) / `offset`; scan cap `journal_stats_max_rows` (default 5000) with `truncated` flag | `backend/src/app/api/routes/journal.py`, `backend/src/app/schemas/journal_statistics.py`, `backend/src/app/services/journal_statistics_service.py` |
| Paper portfolio | `GET /performance/portfolio` | `PaperPortfolioResponse`: safety banner, account (`starting_balance`, `current_equity`, `cumulative_realized_pnl`, `unrealized_pnl`, open/closed counts, `as_of`, `limitations`), `metrics` (`PerformanceMetricsSchema`), `open_exposure`, dollar `equity_curve` (`DollarEquityPointSchema`), `daily_series` (`DailyPortfolioPointSchema`), `breakdowns` (`by_symbol/by_setup/by_timeframe/by_strategy/by_source/by_detector`), `trend`, `date_range`, `filters_applied`. Filters: `start_date`/`end_date` (date, local close-date in requested `timezone`), `source` (`all\|proposal_flow\|paper_validation`), `symbol`, `setup`, `timeframe`, `timezone` | `backend/src/app/api/routes/performance.py`, `backend/src/app/schemas/performance.py`, `backend/src/app/services/performance/equity_calculator.py` |
| Performance report | `GET /performance/report` | Proposal-flow closed positions only: account `PerformanceMetricsSchema` + `by_strategy/by_symbol/by_timeframe/by_source` breakdowns; cumulative-PnL `equity_curve` (`EquityPointSchema`). No query params | `backend/src/app/api/routes/performance.py`, `backend/src/app/services/performance/calculator.py` |
| Performance snapshots | `GET /performance/snapshots` (`start_date`, `end_date`, `limit` default 50 max 200); `POST /performance/snapshot` (OwnerDep) | Persisted headline metrics (`trade_count`, `net_pnl`, `win_rate`, `profit_factor`, `max_drawdown`, `max_drawdown_pct`, `as_of`). **On-demand only — no scheduler writes snapshots**, so this is not a reliable time series | same router; model `PerformanceSnapshot` in `backend/src/app/db/models.py` |
| Journal comparison (AT-036) | `GET /journal/comparison` | Human vs paper-system vs backtest cohorts (`JournalTradeStatsMetrics` each), actor scorecards, `decision_quality` (`average_entry_timing_pct`, `early_exit_count`, `early_exit_rate`, `average_missed_profit`, `average_capture_pct`), `by_entry_method`, `by_source`, `rule_compliance`, breakdowns (setup, market_regime), `confidence`, `warnings` | `backend/src/app/api/routes/journal.py`, `backend/src/app/schemas/backtest.py` (`JournalComparison*`), `JournalStatisticsService.compare_cohorts` |
| Journal trades (AT-030) | `GET /journal/trades` (filters `source`, `status`, `symbol`, `user_strategy_id`, `setup_id`; `limit` default 50 max 200 / `offset`; **no date or direction filter**) | Per-trade records incl. `direction`, `planned_risk_amount`, `entry_time`/`exit_time`, `gross_pnl`/`net_pnl`, `fees`/`funding`/`slippage`, MFE/MAE + excursion provenance (`excursion_source`, `excursion_is_stale`, `excursion_candle_count`, …) | `backend/src/app/api/routes/journal.py`, `backend/src/app/schemas/journal_trades.py` |
| Excursion replay (AT-032) | `POST /journal/trades/{id}/replay-excursions`, `POST /journal/trades/replay-excursions` | Deterministic MFE/MAE from stored `HistoricalCandle` rows only; skipped when candles are missing (`missing_candles`). No GET-only excursion endpoint; values surface on `JournalTradeRead` | `backend/src/app/services/journal_excursion_calculator.py`, `journal_excursion_replay_service.py` |
| Behaviour analytics (slice 31) | `GET /analytics/setups`, `/analytics/trade-review`, `/analytics/discipline`, `/analytics/risk-behavior` (all `start_date`/`end_date` as UTC dates) | Proposal/legacy-journal derived: `SetupStatistics` (keyed by `SetupType` = `StrategyId` enum), `TradeReviewAnalytics`, `DisciplineScoreResult` (`score` 0–100, `grade`, behaviours, suggestions), `RiskBehaviorAnalytics` (incl. `revenge_trading_warnings`, `daily_loss_warnings`, `overtrading_warnings`, `journal_completion_rate`, `triggered_rules`) | `backend/src/app/api/routes/analytics.py`, `backend/src/app/services/analytics/*` |
| Learning analytics (slice 84) | `GET /learning-analytics/summary`, `/setup-performance`, `/discipline`, `/confidence-outcome`, `/behavior-insights`, `/lessons`, `/setup-ranking` (shared params `start_date`, `end_date`, `user_id`, `min_sample` default 5 max 100; `dimension` ∈ `condition\|timeframe\|symbol\|direction\|confidence_bucket` where applicable) | Manual paper-validation **session outcome** aggregates: funnel, `outcome_distribution`, `rates.success_rate` etc., discipline score/grade with `insufficient_data`, confidence-vs-outcome buckets, lesson keyword themes, setup ranking (`quality_score`, `sample_size`). Windowed aggregates only — **no time series** | `backend/src/app/api/routes/learning_analytics.py`, `backend/src/app/schemas/learning_analytics.py`, `backend/src/app/services/learning_analytics/*` |
| Strategy quality (slice 89) | `GET /strategy-quality/detectors`, `/summary`, `/detectors/{condition}/explain` | Per-detector (`condition` string) quality from session outcomes: `trust_tier`, `verdict`, `quality_score`, rate family, `outcome_distribution`, `confidence_calibration`, warnings | `backend/src/app/api/routes/strategy_quality.py`, `backend/src/app/schemas/strategy_quality.py` |
| Validation priority (slice 85) | `GET /validation-priority/queue`, `/summary`, `/explain/{item_type}/{item_id}` | Snapshot priority scores per pending candidate/run-plan (`priority_score`, `action_label`, `reliability`, `historical_success_rate`, `historical_invalidation_rate`, factors) — not a time series | `backend/src/app/api/routes/validation_priority.py` |
| Coaching (slice 87) | `GET /coaching/prompts`, `/summary`, `/prompts/{category}/{matched_key}/explain`; `POST /coaching/prompts/save` | Behavioural review prompts with `concern_score`, `reliability`, `severity`, per-prompt `source.sample_size`/`source.rate` | `backend/src/app/api/routes/coaching.py` |
| Lessons | `GET /lessons/candidates` (`status`, `mistake_type`, paging), `GET /lessons/accepted` (`mistake_type`, paging) | Lesson candidates with `mistake_type`, `severity`, `confidence`, `status`, source links. **No recurrence aggregate endpoint** | `backend/src/app/api/routes/lessons.py` |
| Research validation (AT-035) | `GET /research-validation/evidence` (+ `/backtests/{id}/status`); `GET /journal/setup-evidence` | Per-backtest evidence tiers (`tier1/2/3`), `oos_trade_count`, `oos_expectancy`, `oos_profit_factor`, `confirm_trade_count`, promotion eligibility. No success-rate aggregation over time | `backend/src/app/api/routes/research_validation.py`, `backend/src/app/schemas/research_validation.py` |
| Paper validation workflow (slices 77–83) | `/paper-validation/candidates*`, `/run-plans*`, `/run-sessions*`, observations, `.../result` | Statuses and categorical outcomes (`success\|failure\|invalidated\|missed_entry\|no_trade\|inconclusive`), entry/discipline assessments, lessons text. **No P&L on session results** | `backend/src/app/api/routes/paper_validation.py`, `backend/src/app/schemas/paper_validation_*.py` |
| Paper-bot runtime | `GET /paper-validation/{run_id}/trades` (`status`, `limit` default 100 max 500), `/metrics` | Engine trades with `gross_pnl`/`net_pnl`/`fees`/`slippage` and run-level `PaperValidationMetrics` (win rate, PF, expectancy, max DD pct) | same router |
| Positions / orders | `GET /positions` (`status`, paging; no symbol/date filters), `GET /execution/orders` (paging only) | Raw proposal-flow rows. Positions lack `exit_price`/`fees`; orders carry no P&L | `backend/src/app/api/routes/positions.py`, `execution.py` |
| Backtests | `GET /backtests/{id}` (+ `/trades`, `limit` default 200 max 500) | `BacktestResult` full metric set incl. equity curve, OOS split metrics | `backend/src/app/api/routes/backtests.py`, `backend/src/app/schemas/backtest.py` |
| Dashboard | `GET /dashboard/summary` | Attention aggregates (daily discipline snapshot, discipline score summary, open paper trades, alerts/lessons, next recommended action). No date params | `backend/src/app/api/routes/dashboard.py`, `backend/src/app/schemas/dashboard.py` |

Key structural facts:

- **No stored equity history.** The dollar equity curve is computed in-memory per request by
  `PortfolioEquityCalculator`; `performance_snapshots` are manual, on-demand dumps. There is
  no `PaperPortfolioSnapshot` table and no scheduled snapshot job.
- **`None` is never zero.** `JournalTradeStatsMetrics` documents this contract explicitly;
  every metric family carries its own `*_sample_count`.
- **Sample confidence is server-authoritative.** `SampleConfidence`: `insufficient` (< 5
  closed trades), `low` (5–19), `moderate` (20–49), `high` (≥ 50); machine-readable
  `JournalStatsWarningCode` values (`low_sample`, `missing_pnl`, `partial_excursion_data`,
  `result_truncated`, …).
- **Setup taxonomy is fragmented** across detector `condition` strings
  (`liquidity_sweep`, `sfp`, `trend_pullback`, `order_block`, `breakout_retest`),
  `JournalTrade.setup_id` (FK to `setup_definitions`), and the `StrategyId`/`SetupType` enum
  used by `/analytics/setups`. These are **not** interchangeable keys; the UI must never join
  across them by name.
- **Two discipline scores exist** with different data and algorithms:
  `/analytics/discipline` (proposal-flow derived) and `/learning-analytics/discipline`
  (paper-validation session assessments). They must be labeled distinctly, never merged.

### 2.2 Frontend baseline

- Chart stack: **none installed** (`frontend/package.json` has no recharts/chart.js/visx/d3/
  lightweight-charts). Two hand-rolled SVG components exist:
  `frontend/src/components/portfolio/PaperPortfolioCharts.tsx` (equity polyline + daily
  P&L/drawdown div-bars) and `frontend/src/components/strategy/BacktestEquityChart.tsx`.
- Analyze routes today (all chartless scorecards/tables): `/analytics`,
  `/journal/statistics`, `/journal/comparison`, `/learning-analytics`, `/coaching`,
  `/strategy-quality`. Navigation source of truth:
  `frontend/src/components/layout/navigation-config.ts` (**do not touch**).
- API client: `frontend/src/lib/api/client.ts` (`apiFetch`, `ApiError`), facade
  `frontend/src/lib/api/index.ts` (`api.journal.statistics`, `api.journal.comparison`,
  `api.performance.portfolio`, `api.performance.snapshots`, `api.analytics.*`,
  `api.learningAnalytics.*`, `api.strategyQuality.*`, `api.coaching.*`,
  `api.validationPriority.*`, `api.dashboard.summary`). Data hook:
  `frontend/src/hooks/useAsyncData.ts`; per-widget partial loading via
  `loadSource`/`SourceResult` in `frontend/src/components/workflows`.
- Pagination contract: `{ items, total, limit, offset }` with `limit`/`offset` query params.
- State primitives: `frontend/src/components/states.tsx` (`EmptyState`, `LoadingState`,
  `ErrorState`, `StaleState`, `LimitationsState`, `BlockedState`, `UnavailableState`);
  `FreshnessPill` + freshness helpers in `frontend/src/components/workflows/freshness.ts`
  (delayed ≥ 5 min, stale ≥ 30 min, future skew → unavailable); `DataNumber` for tabular
  numerals; `Tabs`/`TabPanel`, `Tooltip`, `Skeleton*` primitives in
  `frontend/src/components/ui/`.
- Formatting: `formatDate`/`formatDecimal` in `frontend/src/lib/utils.ts`; domain helpers
  (`formatPercent` in `frontend/src/components/portfolio/portfolio-display.ts`,
  `formatRate`/`formatScore` in strategy-quality). **No shared currency or timezone-aware
  formatter exists** — PR 1 must add one rather than another page-local `pct()` helper.
- Filter persistence: journal/lessons deep-links parse URL params
  (`frontend/src/components/journal/journalContext.ts`,
  `.../lessons/lessonsContext.ts`); `/journal/comparison` seeds initial filters from the URL
  but does not write back; `/journal/statistics` filters are local state only. No shared
  filter bar exists.
- Tests: vitest + Testing Library per page (`frontend/src/app/(app)/analytics/page.test.tsx`
  and siblings), Playwright staging specs in `frontend/e2e/`.

---

## 3. Metric availability matrix

Status legend: **supported now** (server returns it), **derivable safely** (deterministic
client transform of complete server data — no re-aggregation of paginated raw rows),
**partially supported** (exists with material coverage caveats), **unsupported** (no data
path today), **requires backend work** (smallest change named in §11).

Primary sources abbreviated: **JS** = `GET /journal/statistics`
(`JournalTradeStatsMetrics`), **PP** = `GET /performance/portfolio`
(`PaperPortfolioResponse`), **JC** = `GET /journal/comparison`, **LA** =
`/learning-analytics/*`.

| Metric | Endpoint | Response field | Calculation required | Safe client-side? | Coverage / pagination limits | History exists? | Status |
|---|---|---|---|---|---|---|---|
| Total trades | JS | `overall.trade_count` (also PP `account.closed_trade_count`, `metrics.trade_count`) | none (server) | display only | JS closed trades only; scan cap 5000 with `truncated` flag | yes (recorded trades) | **supported now** |
| Wins / losses | JS | `overall.wins`, `overall.losses`, `overall.breakeven` | none | display only | undecided trades excluded (recorded `result` or `net_pnl` sign) | yes | **supported now** |
| Win rate | JS | `overall.win_rate` (also PP `metrics.win_rate`) | none — wins ÷ decided; breakeven excluded | display only | `None` when no decided trades — must not render as 0 % | yes | **supported now** |
| Realised P&L | JS `net_pnl_total`, `gross_pnl_total`; PP `account.cumulative_realized_pnl` | as named | none | display only | `pnl_sample_count` may be < `trade_count` (missing P&L rows) | yes | **supported now** |
| Average win | JS | `overall.average_winner` (PP `metrics.avg_win`) | none | display only | P&L sample only | yes | **supported now** |
| Average loss | JS | `overall.average_loser` (PP `metrics.avg_loss`) | none | display only | P&L sample only | yes | **supported now** |
| Expectancy | JS | `overall.expectancy` | none — mean net P&L per trade with recorded P&L (**currency expectancy, not R-expectancy**; label accordingly) | display only | P&L sample; `confidence` label must accompany | yes | **supported now** |
| Profit factor | JS | `overall.profit_factor` | none — gross wins ÷ \|gross losses\|; `None` when no losers (warning `no_losing_trades`) | display only | `None` ≠ ∞ ≠ 0; render "n/a — no losing trades" | yes | **supported now** |
| Average R-multiple | JS | `overall.average_r`, `r_sample_count` | none — mean of `net_pnl / planned_risk_amount` | display only | only trades with `planned_risk_amount > 0` (warning `missing_risk`) | yes | **supported now** |
| R-multiple distribution | none | — | per-trade R histogram | **no** — `GET /journal/trades` has no date filter and pages at max 200; client aggregation over unbounded pages is unsafe | — | raw inputs exist per trade | **requires backend work** (§11 B1) |
| Drawdown (max, % and $) | PP | `metrics.max_drawdown`, `metrics.max_drawdown_pct`; daily `daily_series[].daily_drawdown`, `daily_drawdown_pct` | none | display only | dollar drawdown from computed equity; depends on `starting_balance` config | recomputed per request; not stored | **supported now** |
| Drawdown curve (underwater) | PP | derive from `equity_curve[].equity` (running peak − equity) | deterministic transform of one complete array | **yes** | same as equity curve; canonical home Portfolio (AT-039 §8.2) | recomputed per request | **derivable safely** |
| Equity curve ($) | PP | `equity_curve[]` (`index`, `timestamp`, `equity`, `cumulative_realized_pnl`, `unrealized_pnl`, `event`) | none | display only | in-memory reconstruction; `timestamp` nullable on some points; live point flagged `event="live"` | reconstructed from trades, not snapshotted | **supported now** |
| Cumulative realised P&L | PP | `equity_curve[].cumulative_realized_pnl` (also `/performance/report` `account.equity_curve[].cumulative_pnl` for proposal flow only) | none | display only | as equity curve | yes | **supported now** |
| Daily performance | PP | `daily_series[]` (`date`, `starting_equity`, `ending_equity`, `daily_pnl`, `daily_drawdown`, `daily_drawdown_pct`, `trades_closed`) | none | display only | calendar days in requested `timezone`; only days with activity | yes | **supported now** |
| Weekly performance | PP | derive from `daily_series[]` | sum `daily_pnl`/`trades_closed` per ISO week | **yes** (complete array, pure fold) | inherits daily coverage | yes | **derivable safely** |
| Performance by symbol | JS `group_by=symbol` buckets; PP `breakdowns.by_symbol` | `buckets[].metrics.*` | none | display only | bucket pagination (`limit`≤200, `total_buckets`); per-bucket confidence | yes | **supported now** |
| Performance by setup | JS `group_by=setup` / `setup_version`; PP `breakdowns.by_setup` | as above | none | display only | only trades with `setup_id` recorded; auto-journal from position close usually lacks `setup_id`; "unassigned" bucket must be shown honestly | yes | **partially supported** (coverage gap, not API gap) |
| Performance by strategy | JS `group_by=strategy` / `strategy_version`; PP `breakdowns.by_strategy` | as above | none | display only | only trades with `user_strategy_id` | yes | **supported now** |
| Performance by direction | none in JS (`group_by` has no `direction`; PP breakdowns have no direction) | — | — | **no** — same unbounded-pagination problem as R distribution | per-trade `direction` exists | **requires backend work** (§11 B2). LA `setup-performance?dimension=direction` covers **validation session outcomes** by direction, not P&L |
| Performance by trade horizon | JS `group_by=timeframe` (proxy); no holding-duration grouping | `buckets[]` keyed by declared timeframe | none for the proxy | display only | `timeframe` is the declared chart timeframe, not realized holding time | yes (proxy) | **partially supported** (timeframe proxy now; duration buckets **require backend work**, §11 B3) |
| MFE (max favorable excursion) | JS aggregates `average_mfe_amount`, `mfe_sample_count`; per-trade on `JournalTradeRead` (`mfe_amount`, `mfe_price`, excursion provenance) | none | display only | only trades with recorded/replayed excursions; replay needs stored candles (AT-032); warning `partial_excursion_data` | partial | **partially supported** |
| MAE (max adverse excursion) | as MFE (`average_mae_amount`, `mae_sample_count`) | none | display only | as MFE | partial | **partially supported** |
| Execution quality | JC `decision_quality` (`average_entry_timing_pct`, `early_exit_rate`, `average_missed_profit`, `average_capture_pct`); JS capture family (`average_realized_vs_available_pct`, `capture_sample_count`); JS `slippage_total` | none | display only | timing needs planned + actual entry; capture needs excursions; warnings `partial_timing_data`, `partial_capture_data` | partial | **partially supported** |
| Discipline score | `GET /analytics/discipline` → `score`, `grade`; `GET /learning-analytics/discipline` → `discipline_score`, `discipline_grade`, `insufficient_data` | none | display only | two distinct scores (proposal-flow vs validation sessions) — label separately | current-window snapshot only | **supported now** (snapshot); **trend requires backend work** (§11 B4) |
| Rule compliance | JS `group_by=rule_compliance` buckets (`compliant\|partial\|violated\|unassessed`); JC `rule_compliance` | none — worst-assessment-wins precedence | display only | rule checks are manual (`POST /journal/trades/{id}/rule-checks`); most trades may be `unassessed` — show that bucket, never hide it | yes | **supported now** (with coverage caveat) |
| Post-loss behaviour | `GET /analytics/risk-behavior` → `revenge_trading_warnings` (COOLDOWN_AFTER_LOSS), `daily_loss_warnings`, `overtrading_warnings`; `GET /analytics/trade-review` → `trades_after_daily_loss_warning` | none | display only | warning **counts**, not post-loss P&L analysis; proposal-flow scope only | window counts | **partially supported** (full post-loss performance split **requires backend work**, §11 B5) |
| Human vs system comparison | JC | `cohorts[]` (human / paper_system / backtest × `JournalTradeStatsMetrics`), `scorecards[]`, `decision_quality`, `breakdowns` | none | display only | cohort classification from `source`; each cohort carries own `confidence` | yes | **supported now** |
| Validation setup success rate | LA `summary` → `rates.success_rate` (+ failure/invalidated/missed/no_trade/inconclusive); `setup-performance?dimension=...` per-group `success_rate`; `setup-ranking` `quality_score` | none | display only | manual session outcomes only (categorical, **no P&L**); `min_sample` gating; windowed aggregate | window aggregates only | **supported now** (windowed); **trend over time requires backend work** (§11 B6) |
| Validation outcome trend | none | — | time-bucketed outcome rates | **no** — would need per-session result join over paginated sessions (N+1) | raw sessions/results exist | **requires backend work** (§11 B6) |
| Lesson / mistake recurrence | `GET /lessons/candidates?mistake_type=...` (counts via `total`); `GET /learning-analytics/lessons` (keyword themes over session lessons text) | client may display `total` per queried `mistake_type` | only as explicit per-type queries (bounded, one request per type is not acceptable at scale) | limited | no recurrence aggregate; themes ≠ lesson candidates | raw rows exist | **partially supported** (proper recurrence aggregate **requires backend work**, §11 B7) |

Explicitly **unsupported** (no data path, do not fabricate): Sharpe/Sortino/volatility-based
ratios (no returns series store), benchmark-relative performance, per-trade slippage vs
quoted spread, funding-adjusted APR, and any live-account metric (paper-only posture,
`EXECUTION_MODE=paper`).

---

## 4. Analytics information architecture

### 4.1 Structure

The Analytics hub lives at the existing `/analytics` route with six sections implemented as
**query-parameter tabs** (`/analytics?tab=performance`, using the existing `Tabs` primitive) —
Level-2 URLs without touching `navigation-config.ts`. Deep links and back-button behavior
work because the tab and all filters are URL state (§6).

| Tab | Question it answers | Primary sources |
|---|---|---|
| **Overview** | "How am I doing, at a glance?" | JS `overall`, PP `account` + `trend`, dashboard-style stat tiles |
| **Performance** | "Where does the P&L come from, over time?" | PP `daily_series` + `equity_curve` (cumulative realised P&L view), JS overall |
| **Setups** | "Which setups and strategies earn their place?" | JS `group_by=setup\|setup_version\|strategy`, `GET /journal/setup-evidence` |
| **Behaviour** | "Am I trading with discipline?" | JS `group_by=rule_compliance`, `/analytics/discipline`, `/analytics/risk-behavior`, `/learning-analytics/discipline` |
| **Validation** | "Is the validation pipeline finding good setups?" | LA `summary`, `setup-performance`, `setup-ranking`, `/strategy-quality/summary` |
| **Comparison** | "Human or system — who executes better?" | JC |

Progressive disclosure: Overview shows at most 7 primary stats (AT-039 criterion 15); each
subsequent tab holds at most 2 full charts above the fold (AT-039 §8.3 chart budget), with
tables and drill-downs below.

### 4.2 What belongs where (anti-duplication assignments)

Consistent with the AT-039 §8.2 canonical metric catalog; one canonical home per metric,
compact `DataNumber`/sparkline references elsewhere:

| Surface | Owns (canonical) | References only |
|---|---|---|
| **Dashboard** (`/`) | attention queue (unchanged) | compact discipline + net-P&L stat tiles linking to `/analytics` (already sourced from `api.dashboard.summary` / `api.analytics.*`; no new charts) |
| **Portfolio** (`/portfolio`) — **owned by the parallel Portfolio workstream; this plan does not modify it** | full equity curve + drawdown/underwater chart, open exposure | — |
| **Journal statistics** (`/journal/statistics`) | the exhaustive filterable **table** of every `JournalTradeStatsMetrics` family (remains the numeric source of record) | links into `/analytics?tab=setups` for the charted view |
| **Analytics hub** (`/analytics`) | daily/weekly P&L chart, cumulative realised P&L line, setup win-rate/expectancy bars, rule-compliance breakdown, validation outcome distribution, human-vs-system paired bars | equity **sparkline** (links to Portfolio), discipline **scores** (links to source pages) |
| **Setup detail** (existing `/journal/statistics` filtered view + `/journal/setup-evidence` panel) | per-setup evidence tiers, per-setup metric table | per-setup stat tiles reuse Analytics components |
| **Validation detail** (`/paper-validation/run-sessions/[sessionId]`, `/strategy-quality`) | per-session observations/outcomes; per-detector calibration | Validation tab links to these, never re-charts calibration |

The chartless pages that today duplicate numbers (`/analytics` legacy cards vs
`/journal/statistics`) converge: `/analytics` becomes the visual hub; `/journal/statistics`
stays the numeric drill-down. No route is removed and no redirects are added in this
workstream.

---

## 5. Chart specifications

Charting stack (per AT-039 §8.1, confirmed for Phase D): **Recharts** for every chart below;
TradingView Lightweight Charts is **not** required by this blueprint and stays uninstalled.
All charts render inside a shared `ChartFrame` component (new, PR 1) that provides: title
(as a question), provenance caption (source endpoint + `generated_at`/`as_of` + applied
filters), sample-size badge, and the five states of §7. Numerals use `.font-data`; colors
use semantic tokens only (`--color-positive`/`--color-negative`/accent — never raw hex).

Global rules: no y-axis gridline overload (muted y-only), shared tooltip style, P&L never
color-only (sign always rendered), reduced-motion disables animations.

### C1 — Daily P&L bars (canonical: Analytics → Performance)

| Aspect | Specification |
|---|---|
| Purpose | "Which days made or lost money, and how large are swings?" |
| Source | PP `daily_series[]`: `date`, `daily_pnl`, `trades_closed` |
| X-axis | calendar date (respecting `timezone` filter); gaps between active days rendered as gaps, not zeros |
| Y-axis | daily net P&L (USD, signed) |
| Filters | date range, source, symbol, setup, timeframe (§6) |
| Empty state | `EmptyState`: "No closed paper trades in this range." + action "Widen date range" |
| Partial-data | if `account.limitations` non-empty → `LimitationsState` strip above chart listing them |
| Unavailable | `ErrorState` with retry (`useAsyncData.reload`); no axes rendered with fake zeros |
| Mobile | horizontal scroll within fixed-height frame; last 30 bars initially visible |
| Accessibility | `role="img"` + `aria-label` summarizing range, best/worst day; adjacent visually-hidden data table (same numbers) |
| Tooltip | date, daily P&L (signed, 2 dp), trades closed, ending equity |
| Precision | USD 2 dp; percentages 1 dp |
| Max points | 180 daily bars; beyond that auto-switch to weekly rollup (labeled "weekly — derived client-side from daily series") |

### C2 — Cumulative realised P&L line (canonical: Analytics → Performance)

| Aspect | Specification |
|---|---|
| Purpose | "Is realised P&L compounding or churning?" |
| Source | PP `equity_curve[]` field `cumulative_realized_pnl` (trade_close events); explicitly **not** the equity value, which stays canonical on Portfolio |
| X-axis | `timestamp` (null-timestamp points plotted by `index` with a `LimitationsState` note "N points lack timestamps") |
| Y-axis | cumulative realised P&L (USD) |
| Filters | date range, source, symbol, setup, timeframe |
| Empty | as C1 |
| Partial | `event="live"` point excluded (unrealised); note when excluded |
| Unavailable | `ErrorState` + retry; never a flat zero line |
| Mobile | full-width, 200 px height, pinch/scroll disabled (static), range selector below |
| Accessibility | `aria-label` with start/end values and net change; hidden table of every 10th point + final |
| Tooltip | timestamp, cumulative realised P&L, trade counter (`index`) |
| Precision | USD 2 dp |
| Max points | 500; decimate evenly above (keep first/last/extremes), caption "showing N of M points" |

### C3 — Setup win-rate bars (canonical: Analytics → Setups)

| Aspect | Specification |
|---|---|
| Purpose | "Which setups win most often — with enough sample to matter?" |
| Source | JS `group_by=setup` (toggle `setup_version`) → `buckets[].metrics.win_rate`, `wins`, `losses`, `confidence` |
| X-axis | win rate 0–100 % (horizontal bars; setup labels legible on mobile) |
| Y-axis | setup label (bucket `label`; "unassigned" bucket always shown last, never dropped) |
| Filters | date range, symbol, strategy, source, timeframe |
| Empty | "No closed trades have a recorded setup in this range." + link to journal |
| Partial | buckets with `confidence="insufficient"` render de-emphasised (muted bar + "n=X insufficient" badge), sorted after confident buckets |
| Unavailable | `ErrorState` + retry |
| Mobile | horizontal bars stack naturally; cap 8 bars + "show all" disclosure |
| Accessibility | native list semantics: each bar row is a labeled list item with text values |
| Tooltip | setup, win rate, wins/losses/breakeven, n, confidence |
| Precision | percent 1 dp; counts integer |
| Max points | 20 buckets per page (server `limit`); pager if `total_buckets` > 20 |

### C4 — Setup expectancy bars (canonical: Analytics → Setups)

As C3 with: source field `buckets[].metrics.expectancy` (+ `average_r` shown in tooltip when
`r_sample_count > 0`); x-axis signed USD expectancy per trade; zero line rendered; label
explicitly "expectancy (mean net P&L per trade)". Buckets with `expectancy = null` render as
"no P&L data" rows, **never** as zero-height bars.

### C5 — Rule-compliance breakdown (canonical: Analytics → Behaviour)

| Aspect | Specification |
|---|---|
| Purpose | "Do I perform better when I follow my rules?" |
| Source | JS `group_by=rule_compliance` → buckets `compliant\|partial\|violated\|unassessed` with full metric families |
| X-axis | compliance class (4 fixed buckets) |
| Y-axis | grouped bars: win rate (%) and expectancy (USD, secondary axis disclosed on toggle — one metric at a time on mobile) |
| Filters | date range, symbol, setup, strategy, source |
| Empty | "No rule checks recorded yet." + action linking to journal trade detail (rule checks are manual, `POST /journal/trades/{id}/rule-checks`) |
| Partial | `unassessed` bucket always visible with count — the honest denominator |
| Unavailable | `ErrorState` + retry |
| Mobile | 4 bars fit without scroll |
| Accessibility | table alternative with all four buckets × metrics |
| Tooltip | class, n, win rate, expectancy, confidence |
| Precision | percent 1 dp, USD 2 dp |
| Max points | 4 (fixed) |

### C6 — Validation outcome distribution (canonical: Analytics → Validation)

| Aspect | Specification |
|---|---|
| Purpose | "How do manual validation sessions actually end?" |
| Source | LA `summary` → `outcome_distribution` (+ `rates.*`, `sample_size`) |
| X-axis | outcome category (`success`, `failure`, `invalidated`, `missed_entry`, `no_trade`, `inconclusive`) |
| Y-axis | session count (rate shown in tooltip) |
| Filters | date range, `min_sample` (validation-specific; §6) |
| Empty | "No validation sessions with recorded outcomes in this range." + link to `/paper-validation/run-sessions` |
| Partial | when `sample_size < min_sample` → chart renders but is wrapped in an "insufficient sample (n=X < N)" qualifier; no rates emphasised |
| Unavailable | `ErrorState` + retry |
| Mobile | 6 bars, horizontal labels abbreviated with full names in tooltip |
| Accessibility | hidden table of category/count/rate |
| Tooltip | category, count, rate % |
| Precision | counts integer, rates 1 dp |
| Max points | 6 (fixed) |

### C7 — Setup success-rate by dimension (canonical: Analytics → Validation)

As C3 shape with: source LA `setup-performance?dimension=condition|timeframe|symbol|direction|confidence_bucket`
(dimension switcher); values `success_rate` with `sample_size` per group; groups below
`min_sample` shown muted with "insufficient" badge (server already applies gating). Explicit
caption: "Categorical session outcomes — no P&L is recorded for manual validation sessions."

### C8 — Human vs system paired bars (canonical: Analytics → Comparison)

| Aspect | Specification |
|---|---|
| Purpose | "Where does the human beat the system, and vice versa?" |
| Source | JC `cohorts[]` (human / paper_system / backtest) — win rate, expectancy, profit factor, average R; `decision_quality` shown as stat tiles beside the chart |
| X-axis | metric (win rate, expectancy, avg R) |
| Y-axis | value; paired/grouped bars per cohort |
| Filters | date range, symbol, setup, strategy, timeframe, source, market regime (JC natively supports all) |
| Empty | "Not enough closed trades in one or both cohorts." with per-cohort n |
| Partial | any cohort with `confidence="insufficient"` renders its bars muted + badge; comparison verdict text suppressed |
| Unavailable | `ErrorState` + retry |
| Mobile | one metric at a time (segmented control), 3 bars per view |
| Accessibility | per-metric table with cohort values and n |
| Tooltip | cohort, value, n, confidence |
| Precision | percent 1 dp, USD 2 dp, R 2 dp |
| Max points | 3 cohorts × 4 metrics |

### Deferred until backend work lands (do not stub with fake data)

- **Equity curve & drawdown/underwater charts** — canonical on Portfolio; owned by the
  parallel Portfolio workstream (its existing `PaperPortfolioCharts.tsx` may later migrate to
  the shared `ChartFrame`, in that workstream, not this one).
- **R-multiple distribution** (needs §11 B1), **performance by direction** (B2), **holding-
  duration performance** (B3), **discipline trend** (B4), **validation outcome trend** (B6),
  **mistake-recurrence trend** (B7). Each gets an `UnavailableState` placeholder **only if**
  its tab already exists; otherwise simply omitted — an absent chart is more honest than a
  disabled one.

---

## 6. Filter model

One shared `AnalyticsFilterBar` (new, PR 1) synchronised to URL query params
(`router.replace`, shallow) so every tab is deep-linkable and back/forward-safe. Server is
the source of truth for what each endpoint accepts; the bar only shows filters the active
tab's sources support (unsupported filters are hidden, not disabled-and-ignored).

| Filter | URL param | Backing support | Notes |
|---|---|---|---|
| Date range | `date_from`, `date_to` (ISO) | JS/JC: `date_from`/`date_to` datetimes; PP: `start_date`/`end_date` dates + `timezone`; LA and `/analytics/*`: `start_date`/`end_date` dates | one UI control; the API layer maps to each endpoint's params. Presets: 7 d / 30 d / 90 d / YTD / all |
| Symbol | `symbol` | JS (`symbol`, max 30 chars), PP (`symbol`), JC (`symbol`) | free-text with recent-symbols suggestions from loaded buckets |
| Setup | `setup_id` | JS (`setup_id`), JC (`setup_id`); PP uses `setup` (name string) — mapped in API layer | never join detector `condition` strings to `setup_id` (§2.1 taxonomy warning) |
| Strategy | `user_strategy_id` (+ optional `strategy_version_id`) | JS, JC | options from `GET /strategies` (paged, `limit` ≤ 200) |
| Direction | — | **not supported** by JS/PP/JC filters | hidden until §11 B2 lands; LA Validation tab exposes `dimension=direction` grouping instead |
| Horizon | `timeframe` | JS (`timeframe`, max 8 chars), PP (`timeframe`), JC (`timeframe`) | labeled "Timeframe" (declared chart timeframe), **not** "holding period"; duration buckets await §11 B3 |
| Paper account / source | `source` | PP `source` (`all\|proposal_flow\|paper_validation`); JS/JC `source` (`manual\|paper_execution\|paper_validation\|backtest\|imported\|system`) | single-tenant paper posture — there is no multi-account selector; `source` is the honest equivalent and is labeled "Trade source" |
| Validation status / sample gate | `min_sample` | LA endpoints (`min_sample` 1–100, default 5) | Validation tab only. Session-status filtering of analytics is **not supported** by LA endpoints (they aggregate recorded results); the run-sessions **list** page keeps its own status filter |
| Market regime | `market_regime` | JS, JC | secondary (behind "More filters" disclosure) |
| Rule compliance | `rule_compliance` | JS | Behaviour tab only |
| Execution actor | `execution_actor` (`human\|system`) | JS | Comparison tab uses JC cohorts instead; exposed on Setups tab as advanced filter |

Persistence rules: filters live in the URL only (shareable, no hidden localStorage state);
changing tabs preserves shared filters (date range, symbol) and drops tab-specific ones
(`min_sample`, `rule_compliance`); unknown/invalid param values are ignored with a visible
"ignored invalid filter X" notice — never silently coerced.

---

## 7. Data honesty requirements (source-honesty model)

Non-negotiable UI contract, building on existing primitives
(`frontend/src/components/states.tsx`, `FreshnessPill`, server `confidence`/`warnings`):

| Condition | Detection | Required behaviour |
|---|---|---|
| Loading | `useAsyncData.loading` / `SourceResult` pending | `LoadingState` skeleton matching final chart frame within 100 ms; no spinners for primary content; no layout shift on resolve |
| Empty | success response with `trade_count = 0` / empty arrays | `EmptyState` with the action that fills it ("Close 5 journaled trades to unlock expectancy"); axes may render, values may not |
| Partial | per-family `*_sample_count` < `trade_count`; `warnings[]` non-empty; a widget's source failed while siblings loaded (`loadSource`) | render what is real; annotate what is missing (e.g. "R shown for 12 of 30 trades — others lack planned risk"); failed widget shows inline `ErrorState` with retry while the page stands |
| Unavailable | `ApiError` (non-401) | `ErrorState` naming the source and offering retry. **A failed source must never render as a zero-value chart** — no axes with flat-zero series, no "0" stat tiles |
| Truncated | JS `truncated=true` (+ `max_rows`), bucket `total_buckets > limit` | banner: "Statistics cover the oldest N closed trades in range — narrow the date range for complete coverage"; charts inherit the banner; pagination controls for buckets |
| Stale | PP `account.as_of` / JS `generated_at` older than freshness thresholds (`freshnessFromTimestamp`: delayed ≥ 5 min, stale ≥ 30 min) | `FreshnessPill` in the provenance caption; `StaleState` strip when the whole tab is stale. Reserved for actual freshness — analytical caveats use `LimitationsState` (AT-040 hardening note) |
| Invalid timestamps | null `timestamp` on equity points; unparseable dates; future skew | plot by `index` with a limitation note (C2); future-skewed `as_of` → treat as unavailable per `freshnessFromTimestamp` |
| Insufficient sample | server `confidence="insufficient"` / `insufficient_data=true` / `sample_size < min_sample` | value still shown but visibly qualified: muted rendering + "n=X — insufficient" badge; no verdict/trend language; never hide n |
| Unsupported metric | metric marked `requires backend work`/`unsupported` in §3 | not rendered at all, or (inside an existing tab) an `UnavailableState` naming the missing capability — never a mocked chart, never zeros |
| Estimated / derived values | client-derived series (weekly rollup, underwater transform) | caption "derived client-side from <source field>"; derivations restricted to deterministic transforms of complete server arrays — the UI never re-aggregates paginated raw rows |

Additional invariants:

- `null` from the server means "not computable" and renders as "—" with a reason where the
  schema provides one (e.g. profit factor `None` + `no_losing_trades` → "n/a — no losing
  trades"). It never renders as `0`, `0 %`, or `$0.00`.
- Paper posture: every analytics surface keeps the verified paper indicator
  (`VerifiedPaperModeIndicator`); unknown/unverified posture shows "Paper mode not
  confirmed" (fail-closed, per AT-040 hardening notes). Copy never implies live-account
  performance or guaranteed returns.
- Provenance caption on every chart: source endpoint, `generated_at`/`as_of`, applied
  filters, and sample size.

---

## 8. Implementation PR sequence

Constraints honored by all four PRs: no changes to `navigation-config.ts` / `nav-items.ts`,
no backend changes, no changes to `frontend/src/components/portfolio/*` or `/portfolio`,
`/positions`, `/risk` pages (Portfolio workstream), no changes to `/knowledge`
(Knowledge workstream), no changes to `.ai/TASKS.md`, and design-system production
primitives (`frontend/src/components/ui/*`) are consumed, not modified — new shared chart
components live in a new `frontend/src/components/analytics/` folder.

Execution-time estimates below are **Cursor agent execution time** for a normal agent run
including tests, not calendar time. Recommended model for all four: **Fable 5** (normal
agent mode); none of the PRs needs a heavier reasoning tier because this blueprint fixes the
design decisions.

### PR 1 — Analytics foundation, filters, Overview + Performance

| Item | Content |
|---|---|
| Routes | `/analytics` (existing page restructured into `Tabs`: Overview, Performance; other tabs hidden until their PRs) |
| Components (new) | `frontend/src/components/analytics/ChartFrame.tsx` (provenance caption, states, sample badge), `AnalyticsFilterBar.tsx` (URL-synced, §6), `DailyPnlChart.tsx` (C1), `CumulativePnlChart.tsx` (C2), `OverviewStats.tsx` (≤ 7 `DataNumber` tiles + equity sparkline linking to `/portfolio`), `useAnalyticsFilters.ts` (URL param hook), `format.ts` (shared currency/percent/date-range formatters — replaces page-local `pct()` copies going forward) |
| Files likely touched | `frontend/package.json` (+ `recharts`), `frontend/src/app/(app)/analytics/page.tsx` + `page.test.tsx`, new `frontend/src/components/analytics/*`, `frontend/src/lib/api/types.ts` only if PP/JS response types are missing fields (verify first — most exist) |
| API dependencies | `GET /journal/statistics`, `GET /performance/portfolio` (both existing; no backend change) |
| Tests | page tests for loading/empty/error/truncated/insufficient states; `ChartFrame` unit tests (all §7 conditions); filter-bar URL round-trip tests; a11y assertions (aria-labels, hidden tables); no-fabricated-values test (source error ⇒ no zero series) |
| Conflict risks | lowest with parallel agents (new folder + one page). `package.json` merge conflict is possible with any parallel dependency change — keep the diff to one dependency line |
| Merge prerequisites | none beyond green CI (`npm run lint`, `vitest`, production build) |
| Estimated Cursor execution time | 60–90 min |

### PR 2 — Setup and strategy analytics

| Item | Content |
|---|---|
| Routes | `/analytics?tab=setups` |
| Components (new) | `SetupWinRateChart.tsx` (C3), `SetupExpectancyChart.tsx` (C4), `SetupBucketTable.tsx` (paged buckets, links to `/journal/statistics` filtered view and `/journal/setup-evidence` data), grouping toggle (setup / setup_version / strategy) |
| Files likely touched | `frontend/src/app/(app)/analytics/page.tsx` (+ test), `frontend/src/components/analytics/*` |
| API dependencies | `GET /journal/statistics` (`group_by=setup\|setup_version\|strategy`), `GET /journal/setup-evidence`, `GET /strategies` (strategy filter options) |
| Tests | bucket pagination, "unassigned" bucket visibility, insufficient-confidence muting, null-expectancy rendering ("no P&L data", not zero bars), deep-link `?tab=setups&setup_id=…` |
| Conflict risks | touches only files created in PR 1 + the analytics page; no overlap with Portfolio/Knowledge |
| Merge prerequisites | PR 1 merged |
| Estimated Cursor execution time | 45–75 min |

### PR 3 — Behaviour and human-versus-system comparison

| Item | Content |
|---|---|
| Routes | `/analytics?tab=behaviour`, `/analytics?tab=comparison` |
| Components (new) | `RuleComplianceChart.tsx` (C5), `DisciplineScoreCards.tsx` (both scores, distinctly labeled + linked to their source pages), `RiskBehaviourCounters.tsx` (post-loss warning counts with honest "counts, not performance" caption), `ComparisonChart.tsx` (C8), `DecisionQualityTiles.tsx` |
| Files likely touched | analytics page (+ test), `frontend/src/components/analytics/*`; `/journal/comparison` page untouched (it remains the numeric drill-down; Comparison tab links to it) |
| API dependencies | `GET /journal/statistics` (`group_by=rule_compliance`), `GET /analytics/discipline`, `GET /analytics/risk-behavior`, `GET /learning-analytics/discipline`, `GET /journal/comparison` |
| Tests | two-discipline-scores labeling (never merged), unassessed-bucket visibility, cohort insufficient-confidence muting + suppressed verdict copy, per-widget partial failure (one source fails, tab stands) |
| Conflict risks | reads several endpoints — mock-heavy tests; still frontend-only, no shared-file overlap |
| Merge prerequisites | PR 1 merged (PR 2 not required) |
| Estimated Cursor execution time | 60–90 min |

### PR 4 — Validation analytics and final chart polish

| Item | Content |
|---|---|
| Routes | `/analytics?tab=validation` |
| Components (new) | `ValidationOutcomeChart.tsx` (C6), `SetupSuccessByDimension.tsx` (C7 with dimension switcher), `ValidationRankingTable.tsx` (LA `setup-ranking`), links to `/strategy-quality` and `/paper-validation/run-sessions` |
| Polish scope | keyboard walkthrough of all tabs, reduced-motion verification, decimation caption checks (C2), mobile (390 px) pass on all charts, copy review against §7, remove any dead code from earlier PRs |
| Files likely touched | analytics page (+ test), `frontend/src/components/analytics/*`, possibly `frontend/e2e/` (one staging spec for the analytics hub) |
| API dependencies | `GET /learning-analytics/summary`, `/setup-performance`, `/setup-ranking`; `GET /strategy-quality/summary` |
| Tests | `min_sample` gating UI, categorical-only caption presence ("no P&L for manual sessions"), dimension switcher deep links, e2e smoke for tab navigation + filter persistence |
| Conflict risks | e2e folder shared with other workstreams — add a new spec file, don't edit existing specs |
| Merge prerequisites | PRs 1–3 merged |
| Estimated Cursor execution time | 60–90 min |

---

## 9. Testing strategy

Unit/page tests (vitest + Testing Library, mocking the `api` facade per existing pattern):

| Concern | Test |
|---|---|
| Loading | skeleton `ChartFrame` renders (`role="status"`), no layout jump snapshot on resolve |
| Empty | zero-trade responses render `EmptyState` with the journey action; no axes with values |
| Failed source | `ApiError` ⇒ `ErrorState` + retry; assert **no** SVG series elements and no "0" stat values exist in the DOM |
| Partial source | one of N `loadSource` results rejected ⇒ sibling widgets render, failed widget shows inline error |
| Truncated source | `truncated=true, max_rows=5000` ⇒ banner text includes coverage wording; bucket pager appears when `total_buckets > limit` |
| Insufficient sample | `confidence="insufficient"` / `insufficient_data=true` ⇒ muted rendering + "n=X" badge; verdict copy absent |
| Invalid dates | null `timestamp` points ⇒ index plotting + limitation note; future `as_of` ⇒ unavailable state (freshness helper contract) |
| Missing values | `profit_factor=null` + `no_losing_trades` warning ⇒ "n/a — no losing trades"; `expectancy=null` bucket ⇒ "no P&L data" row, no zero bar |
| Filter persistence | set filters ⇒ URL updated (`router.replace` mock); reload from URL ⇒ same request params; tab switch keeps shared filters, drops tab-specific ones; invalid param ⇒ visible "ignored" notice |
| Deep links | `/analytics?tab=setups&setup_id=…&date_from=…` renders the tab pre-filtered (test via mocked `useSearchParams`) |
| Mobile rendering | 390 px viewport tests: bar-count caps, single-metric comparison view, no horizontal page scroll (e2e viewport assertion) |
| Chart accessibility | every chart has `role="img"` + meaningful `aria-label`; hidden data-table alternative present with matching values; keyboard reachability of tab list and disclosures |
| No fabricated values | property-style test: for every §7 condition fixture, assert rendered numerals ⊆ numerals present in the fixture (nothing invented, nothing zero-filled) |
| Confirmed paper posture | `/health`-verified posture ⇒ `VerifiedPaperModeIndicator` active state; copy contains "paper" |
| Unverified posture | health check failing/unknown ⇒ "Paper mode not confirmed" fail-closed state (existing `isPaperModeConfirmed` contract) |

E2E (Playwright, staging spec added in PR 4): login → `/analytics` → tab walk → filter set →
reload preserves state → one chart renders with provenance caption → mobile viewport pass.

Backend: no changes in these PRs, so no backend tests change. If any §11 backend item is
picked up later, it ships with its own pytest coverage in that separate task.

---

## 10. Risks and dependencies

| Risk | Mitigation |
|---|---|
| Parallel agents (Knowledge hub, Portfolio/Risk command centre) touching shared files | All new code in `frontend/src/components/analytics/`; only `analytics/page.tsx`, its test, and one `package.json` line are shared surface. Portfolio components/pages and navigation config are explicitly out of scope. Rebase before merge; PR 1 is the only dependency-adding PR |
| `recharts` bundle size on mobile | dynamic-import chart components (`next/dynamic`, `ssr: false`) so tab-less visits pay nothing; verify with build output in PR 1 |
| Equity/drawdown chart ownership drift (this hub vs Portfolio) | AT-039 §8.2 catalog is the arbiter: Portfolio owns equity/drawdown; Analytics owns statistical charts. Overview references equity as sparkline only |
| Setup taxonomy confusion (detector `condition` vs `setup_id` vs `StrategyId`) | never join by name in UI; each chart states its keying; Validation tab charts are labeled "detector condition", Setups tab "journal setup" |
| Two discipline scores misread as one | distinct card labels + source links (§8 PR 3 tests enforce) |
| `journal_stats_max_rows` truncation on large histories | truncation banner + narrow-range suggestion (§7); no client attempt to page beyond the cap |
| No stored equity history — curves recomputed per request | acceptable for paper scale; if latency grows, §11 B8 (scheduled snapshots) is the fix, not client caching |
| Endpoint drift while PRs land | each PR re-verifies the §2 references it consumes; types in `frontend/src/lib/api/types.ts` are the contract checkpoint |

Dependencies: PR 1 → PR 2/3 → PR 4 (PR 2 and PR 3 are independent of each other). Backend
items below are independent of all four PRs and unblock the deferred charts.

---

## 11. Backend work register (out of scope here; smallest viable changes)

| ID | Unblocks | Smallest change |
|---|---|---|
| B1 | R-multiple distribution chart | either add `date_from`/`date_to` + `direction` filters to `GET /journal/trades` **and** cap-bounded client histogram, or (better) add an `r_distribution` bucket array to `JournalStatsResponse` computed in `journal_statistics_service.py` |
| B2 | performance by direction | add `DIRECTION` to `JournalStatsGroupBy` + grouping key in `journal_statistics_service.py` (column already exists on `journal_trades`) |
| B3 | performance by holding duration | derive duration buckets from `entry_time`/`exit_time` in the same service; new `group_by=duration_bucket` |
| B4 | discipline trend | persist periodic discipline scores (extend `PerformanceSnapshot.metrics` JSON or a small table) + a list endpoint; scores are currently recomputed per window with no history |
| B5 | post-loss performance split | server-side cohort: trades entered within N hours after a losing close vs others, as a `JournalStatsResponse` variant |
| B6 | validation outcome trend | time-bucketed `outcome_distribution` (e.g. `interval=week`) on `/learning-analytics/summary` |
| B7 | mistake recurrence | aggregate endpoint over `lesson_candidates.mistake_type` (counts by type × window) |
| B8 | durable equity history | scheduled worker caller for `PerformanceService.snapshot_account` (`backend/src/app/services/performance_service.py`) — today it runs only on demand via `POST /performance/snapshot` |

---

## 12. Recommended next implementation prompt

Use this prompt to start PR 1 (after this blueprint is reviewed and merged):

> Implement PR 1 of `docs/product/at040_analytics_and_charts_blueprint.md` (Analytics
> foundation, filters, Overview + Performance) exactly as specified in §8 "PR 1". Branch
> from `main` as `feat/at040-analytics-pr1-foundation`. Add `recharts` as the only new
> dependency (dynamic-imported, `ssr: false`). Create
> `frontend/src/components/analytics/` with `ChartFrame`, `AnalyticsFilterBar`,
> `useAnalyticsFilters`, `format.ts`, `OverviewStats`, `DailyPnlChart` (spec C1) and
> `CumulativePnlChart` (spec C2), and restructure `frontend/src/app/(app)/analytics/page.tsx`
> into URL-param tabs (Overview, Performance) using the existing `Tabs` primitive. Consume
> only `GET /journal/statistics` and `GET /performance/portfolio`. Enforce the §7
> source-honesty contract (a failed source must never render a zero-value chart; `null` is
> never 0; insufficient samples are visibly qualified with n; truncation banners for
> `truncated=true`). Do not modify navigation config, portfolio components/pages, knowledge
> pages, backend code, or `.ai/TASKS.md`. Add the §9 tests for loading/empty/failed/partial/
> truncated/insufficient states, filter URL round-trips, chart accessibility (aria-label +
> hidden table), and the no-fabricated-values assertion. Run frontend lint, vitest, and a
> production build; open one draft PR titled
> `feat(analytics): analytics hub foundation with filters, overview and performance charts (AT-040 PR 1)`.

---

*End of AT-040 Analytics & Charts blueprint. Companion documents:
`docs/product/at039_premium_ui_ux_blueprint.md` (§8 chart standards),
`docs/product/at040_design_system_foundation.md` (Phase D roadmap row).*
