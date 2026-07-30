# Two-Week Paper Evaluation Protocol

Status: **proposal / operating protocol** — not a code change, not a promise of performance.

AlphaTrade remains **paper-only**. Live trading stays disabled
(`EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `PROVIDER_MODE=fallback` in
staging, `EXCHANGE_MODE` non-live). Nothing in this protocol changes those
invariants, deploys anything, or modifies production code. This document defines
**how a human trader runs a disciplined two-week paper pilot** using AlphaTrade's
existing strategy lifecycle, backtesting, paper validation, journal, and
behavioural-analytics capabilities, and how the results are read afterward.

**The two-week window is an operational and process-reliability pilot.** It
validates that the system runs dependably and that the trader follows a
disciplined process. It may collect **preliminary** setup evidence, but on its
own it does **not** establish robust strategy profitability and does **not**
authorize canonical Tier 1 promotion from a small sample. Robust setup
evidence requires the extended sample framework in
[§2](#2-evaluation-window-and-sample-framework), typically several two-week
pilots strung together.

All specific numbers in this document (durations, minimum sample sizes, risk
percentages, thresholds) are **recommended starting defaults**, not permanent
rules, and are explicitly configurable. Where AlphaTrade already exposes a
configurable setting (e.g. `backtest_tier1_oos_min_trades`,
`user_risk_settings.max_risk_per_trade_percent`), this protocol references the
existing setting rather than hardcoding a competing number. See
[Related repository documentation](#related-repository-documentation).

---

## 1. Evaluation purpose

This protocol exists to answer five questions with evidence, not to prove
profitability.

| Purpose | What "evidence" looks like |
|---|---|
| **System dependability** | Scheduler/scan/tick ticks run when expected, data freshness holds, alerts fire, no unhandled errors — see [system availability metrics](#63-system-availability-and-workflow-reliability). |
| **Trading-process discipline** | Rule compliance, stop respected, no revenge trades, no overtrading, journal completed every session — see [Behavioural-discipline criteria](#624-behavioural-discipline-criteria). |
| **Preliminary setup-level evidence** | A first, honestly-labeled sample per setup, by symbol/timeframe/regime — feeds the canonical evidence framework in [§3](#3-setup-classification) but is not, by itself, sufficient to promote a setup. |
| **Human vs. system comparison** | Where the trader deviated from AlphaTrade's pre-trade/paper-validation guidance, and whether that deviation helped or hurt — via `GET /journal/comparison` and `/human-vs-system/{id}` ([human_vs_system.md](../human_vs_system.md)). |
| **Explicit non-goal** | **No profitability claim or guarantee is made or implied by this protocol, by AlphaTrade, or by any report it produces.** Paper fills are simulated, not exchange fills (see [paper_validation.md](../paper_validation.md) limitations). Two weeks is a process/dependability pilot first and, at most, a very early and low-confidence profitability signal. |

This protocol is a **process document**. It does not add features, change risk
defaults, or enable any new execution path. It only defines how existing
capabilities are used and read.

---

## 2. Evaluation window and sample framework

### 2.1 The two-week window is a pilot, not a proof

- **Two calendar weeks** of active operating days (proposed default: 10
  trading days; extend for weekends/holidays as needed) is a **pilot window**
  for exercising the daily operating loop, the system's dependability, and
  the trader's process discipline end to end.
- The window starts once a strategy is `paper_eligible` (see
  [strategy_library.md](../strategy_library.md#paper-eligibility-slice-38))
  and paper validation and/or manual paper trading has begun.
- The pilot is explicitly **not** sized to be a statistically robust
  profitability study. It is one data point toward the extended sample
  targets in [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable),
  usually the first of several consecutive pilots feeding the same setup's
  evidence base.

### 2.2 Sample framework (proposed defaults, explicitly configurable)

| Level | Target sample | What it is for |
|---|---|---|
| Two-week pilot, combined (all setups) | **≈ 20+ closed paper trades** | Process/dependability sample — enough activity to exercise the daily loop, journal discipline, and system reliability checks. Not a profitability sample. |
| Serious setup evidence, per **important** setup | **≈ 30–50 closed trades** | The minimum sample this protocol considers meaningful for judging a single setup's win rate/expectancy with reasonable confidence — deliberately at or above AlphaTrade's own backtest `tier2_min_trades`/`tier1_oos_min_trades` defaults (30), not below them. |
| Broader evaluation target, overall | **≈ 100–200 closed paper trades** | The scale at which cross-setup, cross-regime conclusions become reasonably reliable. |
| Serious evidence window | **At least 4–6 weeks; preferably 8–12 weeks** when market/setup frequency permits | The time horizon over which the 30–50-per-setup and 100–200-overall targets are realistically expected to accumulate — almost never inside a single two-week pilot. |
| Daily minimum (pilot process check) | ≥ 1 journal entry per trading day, even on no-trade days ("no trade taken, here is why") | Keeps the discipline record continuous — see [§4](#4-daily-operating-loop). |
| Symbol × timeframe × regime buckets below useful sample | **Descriptive only** — report the raw counts and observed values, never a comparative or promotion-relevant claim | Below roughly 5 observations, a bucket is too thin to compare against another bucket or to support any decision; it exists in the report as raw data, not as evidence. |

These are **targets for accumulating a meaningful sample across one or more
pilots**, not trade quotas for any single two-week window. **Never
manufacture trades to reach a target** — see
[§8 defect-triage and anti-gaming note](#8-defect-triage-rules).

### 2.3 Target observations per important setup within a single pilot

"Important" means any setup the trader intends to size normally or scale in
the near term (typically the existing `StrategyId` / `setup_id` values already
tracked in [trading_analytics.md](../trading_analytics.md#setup-tracking), e.g.
`htf_trend_pullback`, `liquidity_sweep_reversal`).

Within one two-week pilot, an important setup should accumulate **as many
observations as market frequency honestly allows**, understood as a partial
contribution toward the [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable)
serious-evidence target of ~30–50 trades — not as a standalone proof point. A
setup that fires only 2–3 times in two weeks is simply early in its evidence
accumulation; it is not "insufficient" as a fault of the pilot, it is
expected, and it carries forward into the next pilot (see
[§2.4](#24-when-the-sample-is-insufficient)).

### 2.4 When the sample is insufficient

A setup, symbol, or bucket is **insufficient** whenever it sits below the
serious-evidence targets in [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable)
— which, for most setups, includes the entirety of a single two-week pilot.
When insufficient:

1. Label the report with the operational status **`insufficient sample`**
   (see [§3.2](#32-operational-statuses-used-during-the-two-week-pilot)) —
   this mirrors, and is consistent with, the existing `insufficient_data` /
   `needs_more_sample` states already returned by
   [paper_validation.md](../paper_validation.md) promotion recommendations
   and `strategies/{id}/paper-eligibility`.
2. **Do not claim, promote, or imply a canonical evidence tier.** Report the
   raw count and observed values, explicitly flagged as too small to support
   any conclusion — see [§3.3](#33-canonical-tier-1-promotion-requirements)
   for why a single pilot's sample essentially never clears that bar alone.
3. Carry the setup forward for continued sample collection (see
   [§9](#9-final-decision-outcomes) — "extend sample collection"). Do not
   extend or distort the whole pilot's reporting cadence just to manufacture
   a bigger number for one thin setup.
4. Never average across buckets to disguise a thin sample as an aggregate
   pass — buckets are reported separately per
   [§3.6](#36-separate-evidence-by-symbol-timeframe-and-market-regime).

**Rule of thumb: any tier claim made on a sample below the [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable)
serious-evidence target is not a tier claim — it is a guess, and must be
labeled as one if reported at all.**

---

## 3. Setup classification

This protocol does **not** introduce a second, competing tier system. There
is exactly **one canonical evidence framework**, already defined elsewhere in
the repository:

| Canonical source | What it classifies |
|---|---|
| [backtesting.md — Setup evidence tiers](../backtesting.md) | Historical backtest replay evidence: `tier1` / `tier2` / `tier3`, driven by `backtest_tier1_*` / `backtest_tier2_*` settings. |
| [paper_validation.md — Promotion](../paper_validation.md) | Paper-validation runtime recommendation: `continue` / `improve` / `restrict` / `retire` / `insufficient_data` / `paper_validated`. |
| `GET /journal/setup-evidence` (see [journal_intelligence_foundation.md](../journal_intelligence_foundation.md), [research_validation.md](../research_validation.md)) | Combined backtest + confirm-trade evidence tiers used for research-validation promotion. |

This protocol's job is to **feed disciplined, honestly-labeled paper trades
into that one framework** — never to define a parallel "two-week tier" that
could be confused with, or contradict, the canonical tiers above.

### 3.1 What this protocol reports instead of a competing tier

During and at the end of a two-week pilot, reports use **operational
statuses** that describe progress toward the canonical framework, not a tier
of their own.

### 3.2 Operational statuses used during the two-week pilot

| Status | Meaning | Typical trigger |
|---|---|---|
| **Insufficient sample** | Below the [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable) serious-evidence target for this setup/bucket. | Fewer than ~30 trades for the setup, or fewer than ~5 for a symbol/timeframe/regime bucket. |
| **Preliminary** | Early trend visible (directionally positive or negative), but sample and/or regime coverage too thin for a canonical tier claim. | Roughly 10–29 trades with reasonably stable metrics and no P0 defects. |
| **Continue testing** | Metrics acceptable so far, no defects, rule compliance holding — keep running at planned (paper) size to build sample. | Any status above with no red flags. |
| **Revision required** | A specific, identifiable process or rule issue is visible in the data (e.g. stop not respected, entries firing outside the intended regime) that should be fixed before more sample is collected on the current version. | Rule-compliance or drawdown concerns traced to a correctable cause. |

These statuses are always reported **alongside**, and never **instead of**,
the setup's canonical evidence tier when one is determinable (from
`GET /journal/setup-evidence`, backtest tier, or paper-validation
recommendation). If no canonical tier has yet been computed for the setup,
the report says so explicitly (`canonical tier: not yet determinable`)
rather than substituting an operational status as if it were one.

### 3.3 Canonical Tier 1 promotion requirements

Tier 1 (per the canonical frameworks in [§3](#3-setup-classification)) is
**never** awarded from a two-week pilot's ~10-trade sample alone. Promotion to
canonical Tier 1 requires **all** of the following:

- The configured minimum sample requirement is met — per
  [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable),
  proposed default ≈ 30–50 closed trades for the setup (consistent with, not
  weaker than, `backtest_tier1_oos_min_trades` / `backtest_tier2_min_trades`
  defaults of 30 in [backtesting.md](../backtesting.md)), ideally supported
  by the broader ≈ 100–200-trade overall target and a ≥ 4–6-week (preferably
  8–12-week) collection window.
- **Positive expectancy after fees, funding, and slippage** — not gross PnL.
- **Acceptable maximum drawdown**, measured against the trader's configured
  risk settings ([risk_management.md](../risk_management.md)), not an
  arbitrary or unconfigured number.
- **Strong rule compliance** — proposed default ≥ 90% `followed`
  classification (worst-assessment basis, `journal_trade_rule_checks`).
- **Evidence across relevant market regimes**, not a single regime that
  happened to be favorable during the sample window (see
  [§3.6](#36-separate-evidence-by-symbol-timeframe-and-market-regime)).
- **No unresolved safety or data-honesty (P0) defect** touching the setup
  (see [§8](#8-defect-triage-rules)).
- **Explicit human review and sign-off**, recorded in the
  [setup evidence summary](#73-setup-evidence-summary) — promotion is never
  automatic and never inferred silently from metrics crossing a threshold.

A single two-week pilot is, by design, expected to produce at most a
**preliminary** or **continue testing** status (§3.2) toward this bar — it is
normally one contributing pilot among several, not the deciding evidence run.

### 3.4 Demotion and restriction triggers

Regardless of prior canonical tier, any of the following triggers an
immediate demotion/restriction review — it does not wait for the end of the
pilot window:

- Rule compliance drops below the proposed 90% bar in a rolling assessment.
- A P0 defect is opened against the setup ([§8](#8-defect-triage-rules)).
- Two consecutive losing trades exceed the setup's expected loss size (stop
  not respected, or MAE far beyond planned invalidation).
- The setup is flagged `restricted` by existing paper-eligibility gates
  ([strategy_library.md](../strategy_library.md#paper-eligibility-slice-38))
  or receives a `restrict`/`retire` recommendation from paper validation.

Demotions/restrictions are logged in the daily report
([§7.1](#71-daily-evaluation-report)) the day they occur — never silently,
and never deferred to the end-of-week summary.

### 3.5 Minimum evidence requirements (metrics)

Per setup, the evidence summary must report (using existing, already-computed
fields where possible — no new metric definitions):

| Metric | Source |
|---|---|
| Win rate | `journal_statistics_service` win/loss/breakeven split, or `paper_validation` metrics |
| Expectancy (after fees, funding, and slippage) | `journal_trades.net_pnl` aggregate, or `paper_trades` fees/slippage/funding fields |
| Average win / average loss | Same PnL family as above |
| MFE / MAE | `journal_trades` excursion fields (manual entry or AT-032 replay) — see [journal_intelligence_foundation.md §5](../journal_intelligence_foundation.md) |
| Drawdown (setup-level slice) | Derived from the sequence of closed trades for that setup within the sample; report alongside, not instead of, portfolio-level `max_drawdown_pct` ([paper_validation.md](../paper_validation.md)) |
| Rule compliance | `journal_trade_rule_checks` worst-assessment classification (`violated` > `partial` > `compliant` > `unassessed`) |

Metric families with insufficient sample use `None`/`insufficient sample`
labels rather than a silently computed number — matching existing
`journal_statistics_service` semantics (never a silent zero).

### 3.6 Separate evidence by symbol, timeframe, and market regime

Do not report one blended number per setup. Break out at minimum:

- **Symbol** (e.g. BTC-PERP vs. ETH-PERP)
- **Timeframe** (e.g. 15m vs. 1h vs. 4h)
- **Market regime** (`MarketRegime` values already recorded on journal trades,
  e.g. trending / ranging / high-volatility)

A setup can carry different operational statuses across symbol/timeframe/regime
combinations within the same pilot — report all of them. Buckets below the
useful-sample floor in [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable)
are **descriptive only**, never merged upward into a healthier bucket and
never used to support a canonical tier claim.

---

## 4. Daily operating loop

Each trading day in the window follows the same loop. Steps map to existing
AlphaTrade surfaces rather than introducing new tooling.

1. **Morning preparation**
   - Review yesterday's [end-of-day review](#daily-eod-in-loop) and any open
     lesson candidates (`/lessons`).
   - Confirm risk settings for the day (`GET /risk/settings`) and today's
     daily-loss/green-day state ([risk_management.md](../risk_management.md)).
   - Confirm paper validation runs are healthy: `GET
     /paper-validation/scheduler/history`, market watcher status
     ([market_watcher.md](../market_watcher.md)) if used.

2. **Market observations**
   - Read-only market watcher scan or manual market review. No orders placed
     at this step under any circumstance.

3. **Signal review**
   - Review any `paper_signal` detections (`scan_only` mode) or system
     recommendations from pre-trade analysis (`POST /pretrade/analyze`,
     [pre_trade_analysis.md](../pre_trade_analysis.md)).
   - Note explicitly whether the trader agrees or disagrees with the
     system's read — this feeds [§6.2.4](#624-behavioural-discipline-criteria)
     human-vs-system comparison later.

4. **Pre-trade plan**
   - For any trade under consideration, complete the plan fields in
     [§5](#5-trade-review-fields) *before* execution: thesis, setup,
     entry, invalidation, stop, take-profit/runner plan, risk/reward,
     confidence, position size, leverage.
   - Run loss acceptance (`POST /risk/loss-acceptance`) where the workflow
     requires it — this is a human gate, not a go/no-go from the system
     ([pre_trade_analysis.md](../pre_trade_analysis.md#loss-acceptance-slice-34)).

5. **Paper execution**
   - Execute only in paper mode (proposal → approval → paper fill, or
     `auto_paper` paper-validation runtime). No live order path exists to
     accidentally use.

6. **Journal completion**
   - Complete the journal entry same-day (never batched to end of week).
     Use `GET /journal/prefill` from the position/paper trade/proposal to
     avoid re-typing plan data ([trading_analytics.md](../trading_analytics.md)).
   - Record every field in [§5](#5-trade-review-fields), including on
     no-trade days ("no setups met criteria" is itself a data point).

7. **End-of-day review** <a id="daily-eod-in-loop"></a>
   - Fill the [daily evaluation report](#71-daily-evaluation-report) template.
   - Review discipline score (`GET /analytics/discipline`) and risk-behavior
     summary (`GET /analytics/risk-behavior`).
   - Note any rule violations, near-misses, or emotional-state flags for
     follow-up.

8. **Cooldown after losses**
   - After any losing trade, impose a mandatory pause (proposed default: no
     new entries for the remainder of the current session, or a minimum
     30–60 minute cooldown before the next signal review) before evaluating
     the next setup. This is a **process control**, not an
     AlphaTrade-enforced lock unless `one_loss_stop_enabled` is also set in
     risk settings.

9. **Stop-after-loss and overtrading controls**
   - Respect existing configured guards: `one_loss_stop_enabled`,
     `max_trades_per_day`, `overtrading_guard_enabled`, `daily_loss_limit`,
     `green_day_protection_enabled`
     ([risk_management.md](../risk_management.md)).
   - If a guard fires, the day's trading stops for that account — no manual
     override during the evaluation window. Any override must be logged as a
     rule violation in the journal, not silently bypassed.

---

## 5. Trade review fields

Every paper trade reviewed in this protocol records the following fields.
Where AlphaTrade already has a structured field for this, use it (canonical
`journal_trades` schema, [journal_intelligence_foundation.md](../journal_intelligence_foundation.md))
rather than free text.

| Field | Notes / existing source |
|---|---|
| Thesis | `journal_trades.thesis` |
| Regime | `journal_trades.market_regime` (+ `regime_notes`) |
| Setup | `journal_trades.setup_id` / `user_strategy_id` |
| Entry | `entry_price`, `entry_plan`, `planned_entry_price` |
| Invalidation | `invalidation` |
| Stop loss | `planned_stop_price` (plan) vs. actual stop behavior at close |
| Take profit | `planned_targets` (JSON) |
| Runner logic | `runner_enabled`, `runner_plan` |
| Risk/reward | Derived from planned stop/target distances at entry |
| Confidence | Free-text or scored note at entry time (record even though not a system-computed field) |
| Position sizing | `size`, cross-checked against `POST /risk/size` recommendation |
| Leverage | `leverage` |
| Result | `result` (win/loss/breakeven), falls back to net-PnL sign per existing semantics |
| Fees/slippage | `fees`, `slippage`, `funding` |
| MFE/MAE | `mfe_amount`/`mae_amount` (manual or AT-032 replay), `available_profit`, `realized_vs_available_pct` |
| Rule adherence | `journal_trade_rule_checks` (`followed` / `violated` / `partial` / `not_applicable` / `unassessed`) |
| Emotional state | `journal_trade_observations` (category `emotional`, with emotion tags) |
| Human vs. system decision | Whether the trade followed, deviated from, or ignored system guidance (pre-trade analysis, paper-validation signal); linked via `/human-vs-system/{id}` or `GET /journal/comparison` |

---

## 6. Metrics and acceptance criteria

### 6.1 Core metrics (proposed defaults — tune via existing settings, not new hardcoded numbers)

| Metric | Definition | Existing source |
|---|---|---|
| Setup win rate | wins / (wins + losses), closed trades only | `journal_statistics_service` |
| Expectancy after fees, funding, and slippage | (win rate × avg win) − (loss rate × avg loss), net of `fees`/`slippage`/`funding` | Journal PnL fields |
| Average win / average loss | Mean net PnL per winning/losing trade | Journal PnL fields |
| Maximum drawdown | Equity-curve based, both portfolio-level and setup-level slice | `paper_validation.md` `max_drawdown_pct` pattern |
| Rule compliance | % `followed` across recorded rule checks (worst-assessment per trade) | `journal_trade_rule_checks` |
| Revenge-trade violations | Count of trades entered inside the mandatory cooldown window after a loss ([§4 step 8](#4-daily-operating-loop)), or that violate `overtrading_guard_enabled` | Journal timestamps + risk-behavior analytics |
| Early-exit cost | Trades with `realized_vs_available_pct` well below 100% due to early exit, per existing runner-analyzer definition (capture < 50% of MFE flagged) | `human_vs_system_service` runner analyzer, `journal_statistics_service` early-exit rate |
| Missed-profit analysis | `available_profit − net_pnl` where positive, using the existing conservative (capped) estimate | Runner analyzer, [human_vs_system.md](../human_vs_system.md) |
| Human vs. system comparison | Entry timing %, plan-adherence score, actor scorecards (human vs. system) | `GET /journal/comparison` ([journal_intelligence_foundation.md §7](../journal_intelligence_foundation.md)) |
| System availability / workflow reliability | See [§6.3](#63-system-availability-and-workflow-reliability) | Runtime history, alerts |

### 6.2 Acceptance criteria — four distinct categories

These categories must not be blended into one pass/fail score. A strong
result in one category never substitutes for a weak result in another.

#### 6.2.1 Product-readiness criteria

- Paper validation scan/tick runs complete without unhandled errors during
  the window (`paper_validation_runtime_history` status `success`/`partial`,
  not chronic `failed`).
- Data freshness held (`is_live`/`fallback_used` reported correctly, no
  silent stale-data trades — see [architecture.md](../architecture.md) if
  present for provider fallback semantics).
- Alerts fired as expected for stop hits, TP hits, runner exits, loss-lock
  warnings.
- No P0 defects open at end of window (see [§8](#8-defect-triage-rules)).

#### 6.2.2 Strategy-evidence criteria

- Sample size and operational status honestly reported per
  [§2](#2-evaluation-window-and-sample-framework) and
  [§3.2](#32-operational-statuses-used-during-the-two-week-pilot) — the
  pilot's own operational status (insufficient sample / preliminary /
  continue testing / revision required) is internally consistent with the
  underlying metrics.
- **No canonical Tier 1/2/3 claim is made from this pilot alone** unless the
  full [§3.3](#33-canonical-tier-1-promotion-requirements) requirements are
  independently met (they typically are not, within a single two-week
  window).
- Evidence is broken out by symbol/timeframe/regime, not blended
  ([§3.6](#36-separate-evidence-by-symbol-timeframe-and-market-regime)).

#### 6.2.3 Profitability evidence

- Reported **as observed data only** (expectancy, win rate, drawdown) with
  explicit confidence labeling by sample size, using the operational statuses
  in [§3.2](#32-operational-statuses-used-during-the-two-week-pilot).
- **Never reported as a guarantee, projection, or claim of future
  performance, and never treated as sufficient on its own to establish
  robust strategy profitability.** The two-week window is a process and
  dependability pilot first; any profitability read from it is preliminary
  and low-confidence by construction, and must be labeled as such in every
  report — see [§2.1](#21-the-two-week-window-is-a-pilot-not-a-proof).

#### 6.2.4 Behavioural-discipline criteria

- Rule compliance ≥ proposed default 90% for any setup being considered for
  extended-evidence review toward canonical Tier 1
  ([§3.3](#33-canonical-tier-1-promotion-requirements)).
- Zero unresolved revenge-trade violations at window close (or all explicitly
  reviewed and journaled).
- Journal completed same-day for every trading day (100% coverage is the
  target; gaps must be explained in the weekly review).
- No unauthorized override of an active risk guard
  (`daily_loss_limit`/`one_loss_stop_enabled`/`overtrading_guard_enabled`)
  during the window.

### 6.3 System availability and workflow reliability

Track for the whole window, independent of any individual trade's outcome:

- Scheduler/manual tick success rate (`paper_validation_runtime_history`).
- Data freshness incidents (`stale`/`unavailable` observations,
  `data_stale` alerts).
- Alert delivery reliability (in-app; external delivery only if already
  enabled per [alerts.md](../alerts.md)).
- Any unhandled exception, 5xx, or audit-log gap encountered during daily
  use.

---

## 7. Daily and final review templates

These are intentionally short. They record facts and links to existing
records — they do not duplicate data already captured by the journal or
analytics endpoints.

### 7.1 Daily evaluation report

```markdown
## Daily Evaluation Report — <date>

- Trading day: <N of 10>
- Journal entries completed today: <count> (target: all trades + no-trade note)
- Trades taken: <count> | Wins: <n> | Losses: <n> | Breakeven: <n>
- Setups touched today: <setup ids>
- Rule violations today: <none | list with journal_trade_rule_checks refs>
- Cooldown / stop-after-loss triggered: <yes/no — details>
- Overtrading guard / daily loss guard triggered: <yes/no — details>
- System issues today: <none | link to defect log entry, see §8>
- Discipline score (GET /analytics/discipline): <score/grade>
- Notes for tomorrow: <free text>
```

### 7.2 Individual trade review

```markdown
## Trade Review — <journal_trade id / external_ref>

Thesis: <...>
Regime: <...>
Setup: <setup_id / strategy_version>
Entry: <price / time>
Invalidation: <...>
Stop loss: <planned> vs <actual behavior>
Take profit / runner: <planned targets> / <runner plan and outcome>
Risk/reward (planned): <R multiple>
Confidence (at entry): <low/med/high + note>
Position size / leverage: <...>
Result: <win/loss/breakeven> | Net PnL: <...>
Fees/slippage: <...>
MFE / MAE: <...> | Realized vs available %: <...>
Rule adherence: <followed/violated/partial/unassessed + which rules>
Emotional state: <tags>
Human vs. system: <followed system guidance | deviated — why | no system signal>
Lesson candidate created: <yes/no — link>
```

### 7.3 Setup evidence summary

```markdown
## Setup Evidence Summary — <setup_id> — window <start>–<end>

Sample size this pilot: <n trades> | Cumulative sample across pilots: <n trades>
  (serious-evidence target: ~30-50 per §2.2) — <insufficient sample|on track|met>
Breakdown: symbol × timeframe × regime table (counts, win rate, expectancy per bucket;
  buckets below useful sample are descriptive only, see §3.6)
Win rate: <...> | Expectancy (net of fees/funding/slippage): <...>
Avg win / avg loss: <...> | MFE/MAE (avg): <...>
Setup-level max drawdown: <...>
Rule compliance: <...>%
Revenge-trade violations: <count>
Early-exit cost / missed-profit total: <...>
Canonical evidence tier (backtest / paper-validation / GET /journal/setup-evidence,
  §3.1): <tier1|tier2|tier3|not yet determinable>
Operational status this pilot (§3.2): <insufficient sample|preliminary|continue testing|revision required>
Status change this window: <none | changed from X — reason>
Recommendation: <continue testing|revise|extend sample collection|demote/restrict|archive — see §9>
```

### 7.4 End-of-week review

```markdown
## End-of-Week Review — Week <1|2> (<date range>)

Trades taken: <n> | Journal completion rate: <%>
Setups evaluated this week: <list with operational status and sample size, §3.2>
Behavioural-discipline summary: rule compliance <%>, revenge-trade violations <n>,
  guard triggers <n>
System reliability: scheduler/tick success rate <%>, stale-data incidents <n>,
  P0 defects <n> (see §8)
Human vs. system: entry timing %, plan adherence score, actor scorecard summary
  (GET /journal/comparison)
Carried-over issues into week 2 (if week 1): <list>
Preliminary read (not a decision, no profitability claim): <free text — explicitly non-binding>
```

### 7.5 Final two-week decision report

```markdown
## Final Two-Week Decision Report — <start>–<end>

### Summary
Total trades: <n> | Total journal entries: <n> | Overall journal completion: <%>
Overall rule compliance: <%>
System availability / reliability summary: <...>
P0 defects encountered: <n> (all resolved before continuing? y/n)

### Per-setup outcomes
<table: setup | sample size (pilot / cumulative) | operational status (§3.2) |
  canonical evidence tier if determinable (§3.1) | recommendation | rationale>

### Product-readiness assessment
<pass/fail against §6.2.1 criteria, with evidence>

### Strategy-evidence assessment
<per-setup, referencing §2 sample targets and §3 operational statuses —
  explicitly note that no canonical Tier 1 claim is made unless §3.3 is fully met>

### Profitability evidence (explicitly preliminary, non-binding, no guarantees)
<observed win rate / expectancy / drawdown per setup, with confidence labels>

### Behavioural-discipline assessment
<pass/fail against §6.2.4 criteria, with evidence>

### Human vs. system comparison summary
<...>

### Final decision (select one or more per setup — see §9)
- [ ] Continue testing
- [ ] Revise setup
- [ ] Extend sample collection
- [ ] Demote / restrict setup
- [ ] Archive setup (only where evidence or rule failure clearly justifies it)
- [ ] Prepare restricted real-money discussion (only if the extended criteria in §9 are met)

### Sign-off
Reviewed by: <name/role> | Date: <...>
```

---

## 8. Defect-triage rules

- **P0 (safety / data-honesty defects) stop the evaluation immediately** for
  the affected scope. Examples: a paper trade fills without going through
  the risk engine; `real_trading_enabled` reports incorrectly; stale/mocked
  data is presented as live without the `is_live`/`fallback_used` flags;
  any exchange-mutating call is triggered outside an explicitly authorized
  test. On a P0: stop trading in the affected scope, record the defect,
  follow the repository's existing blocker/review protocol
  (`.ai/MASTER_WORKFLOW.md` §9/§11/§12) — do not continue evaluation on the
  affected setup/system path until resolved and re-verified.
- **Lower-severity issues (P1–P3)** are logged in the daily report
  ([§7.1](#71-daily-evaluation-report)) and tracked, but **do not halt the
  trial**. Examples: a UI label is misleading but data is correct; a
  non-critical alert type is missing; latency is higher than expected on a
  non-critical endpoint.
- **No feature expansion during the evaluation window.** The two weeks test
  the system and process **as they exist at window start**. New features,
  new setups, or new risk defaults introduced mid-window invalidate
  comparability — hold them for the next cycle unless required to fix a P0.
- Defect log entries reference existing audit/observability records
  (`AuditLog`, `paper_validation_runtime_history`) rather than duplicating
  them — see [observability.md](../observability.md) if further detail is
  needed on the audit trail.

---

## 9. Final decision outcomes

At the end of the two-week pilot, each setup normally receives one of the
following outcomes (a setup may carry secondary notes, e.g. "revise AND
extend"). **Archive is reserved for cases where the evidence or a rule
failure clearly justifies it** — it is not a default outcome for a merely
thin or inconclusive sample.

| Outcome | When to choose it |
|---|---|
| **Continue testing** | Operational status `preliminary` or `continue testing` (§3.2), no P0 defects, discipline criteria met — keep running at planned (paper) size into the next pilot to build toward the [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable) serious-evidence target. This is the expected outcome for most setups after a single pilot. |
| **Revise** | Evidence shows a specific, correctable issue (e.g. stop placement too tight, entries firing in the wrong regime) — update the strategy card/structured rules ([strategy_library.md](../strategy_library.md)) and restart the setup's sample count at the new version. |
| **Extend sample collection** | Sample below [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable) targets for that specific setup/bucket (the normal case for a first pilot) — continue collecting without claiming a canonical tier; do not treat the thin sample as a verdict. |
| **Demote / restrict** | Triggers in [§3.4](#34-demotion-and-restriction-triggers) fire, or the setup already held a canonical tier that the current evidence no longer supports — reduce size or pause new entries while gathering more evidence; this does not require archiving the setup. |
| **Archive** | Persistent negative expectancy over a serious-evidence sample, chronic rule-compliance failure, or a P0 defect tied to the setup's logic that cannot be resolved — mark the strategy `archived` ([strategy_library.md](../strategy_library.md#lifecycle)); stop trading it. Not used for a setup that is simply early in sample collection. |
| **Prepare a restricted real-money discussion** | Only after **strong, extended evidence**, all of the following: (a) ≈ 100–200 total paper trades across the strategy, (b) ≈ 30–50 closed trades for the specific important setup(s) in question, (c) evidence spanning multiple market regimes, (d) expectancy computed net of fees, slippage, and funding, (e) stable drawdown and sustained behavioural discipline over at least 4–6 weeks (preferably 8–12+), and (f) a **separate, explicit safety approval** distinct from this protocol's own sign-off. This outcome **starts a discussion**, not a transition — it does not itself enable `ENABLE_REAL_TRADING` or any live execution path. Any move toward Mode B/C/D broker integration follows the existing phased safety roadmap in [AT010_real_money_safety_roadmap.md](../AT010_real_money_safety_roadmap.md) and requires a separate, explicitly authorized safety/risk/approval program (per workspace trading-safety rules) — this protocol cannot authorize that step on its own, and a single two-week pilot can never by itself satisfy this outcome. |

No outcome in this table changes `EXECUTION_MODE`, `ENABLE_REAL_TRADING`,
`EXCHANGE_MODE`, or any deployment configuration. Those remain governed by
existing repository safety controls (`core/deployment_safety.py`,
`core/exchange_safety.py`).

---

## Related repository documentation

- [paper_validation.md](../paper_validation.md) — paper bot runtime, scan/tick, promotion recommendations
- [strategy_library.md](../strategy_library.md) — strategy lifecycle, paper eligibility gates, lesson → version flow
- [backtesting.md](../backtesting.md) — canonical setup evidence tiers (tier1/tier2/tier3), walk-forward semantics
- [research_validation.md](../research_validation.md) — advisory bridge from backtest evidence into the paper validation queue
- [journal_intelligence_foundation.md](../journal_intelligence_foundation.md) — canonical journal trade schema, statistics, excursion replay, human-vs-system decision quality (AT-036), `GET /journal/setup-evidence`
- [journal_learning.md](../journal_learning.md) and [lesson_workflow.md](../lesson_workflow.md) — discipline analysis and lesson review lifecycle
- [human_vs_system.md](../human_vs_system.md) — per-trade and aggregate human-vs-system comparison
- [trading_analytics.md](../trading_analytics.md) — setup tracking, discipline score, risk-behavior analytics
- [risk_management.md](../risk_management.md) — user risk settings, daily discipline snapshot, guard resolution order
- [pre_trade_analysis.md](../pre_trade_analysis.md) — deterministic pre-trade engine, position sizing, loss acceptance
- [market_watcher.md](../market_watcher.md) — read-only market scanning and paper-validation bridge
- [alerts.md](../alerts.md) — paper validation alert types and delivery
- [observability.md](../observability.md) — audit trail and reliability signals (if present; consult for latest observability surface)
- [AT010_real_money_safety_roadmap.md](../AT010_real_money_safety_roadmap.md) and [AT010_risk_register.md](../AT010_risk_register.md) — phased real-money safety program referenced by [§9](#9-final-decision-outcomes)
- [evaluation.md](../evaluation.md) — existing RAG/agent/guardrail evaluation harness (distinct scope: this protocol evaluates trading process and setups, not model output quality)

---

## Assumptions and limitations of this protocol

- All specific numbers (10 trading days; ≈20+ combined pilot trades; ≈30–50
  per-setup serious-evidence target; ≈100–200 overall broader target; 4–6
  week, preferably 8–12 week, serious-evidence window; 90% rule-compliance
  bar; cooldown durations) are **recommended starting defaults**, explicitly
  configurable, not permanent hardcoded policy. They should be revisited
  after each pilot cycle based on observed data volume and market frequency.
- This protocol does not define new database fields, API endpoints, or
  configuration keys. Every metric and field referenced above already exists
  in the codebase as of this document's writing; where a metric is not
  currently computed automatically (e.g. "confidence at entry", "cooldown
  triggered"), it is recorded as a manual note in the journal/daily report
  rather than invented as a new system field.
- Paper fills are simulated, not exchange fills. All profitability-adjacent
  numbers in this protocol inherit that limitation from
  [paper_validation.md](../paper_validation.md) and
  [trading_analytics.md](../trading_analytics.md).
- A single two-week pilot is a process/dependability exercise. Robust
  strategy-profitability evidence and any canonical Tier 1 promotion require
  the extended sample framework in
  [§2.2](#22-sample-framework-proposed-defaults-explicitly-configurable) and
  [§3.3](#33-canonical-tier-1-promotion-requirements), which normally spans
  multiple consecutive pilots.
