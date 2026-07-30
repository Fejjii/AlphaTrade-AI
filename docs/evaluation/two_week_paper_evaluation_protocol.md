# Two-Week Paper Evaluation Protocol

Status: **proposal / operating protocol** — not a code change, not a promise of performance.

AlphaTrade remains **paper-only**. Live trading stays disabled
(`EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `PROVIDER_MODE=fallback` in
staging, `EXCHANGE_MODE` non-live). Nothing in this protocol changes those
invariants, deploys anything, or modifies production code. This document defines
**how a human trader runs a disciplined two-week paper trial** using AlphaTrade's
existing strategy lifecycle, backtesting, paper validation, journal, and
behavioural-analytics capabilities, and how the results are read afterward.

All specific numbers in this document (durations, minimum sample sizes, risk
percentages, thresholds) are **recommended starting defaults**, not permanent
rules. Where AlphaTrade already exposes a configurable setting (e.g.
`backtest_tier1_oos_min_trades`, `user_risk_settings.max_risk_per_trade_percent`),
this protocol references the existing setting rather than hardcoding a
competing number. See [Related repository documentation](#related-repository-documentation).

---

## 1. Evaluation purpose

This protocol exists to answer five questions with evidence, not to prove
profitability.

| Purpose | What "evidence" looks like |
|---|---|
| **System dependability** | Scheduler/scan/tick ticks run when expected, data freshness holds, alerts fire, no unhandled errors — see [system availability metrics](#63-system-availability-and-workflow-reliability). |
| **Trading-process discipline** | Rule compliance, stop respected, no revenge trades, no overtrading, journal completed every session — see [Behavioural-discipline criteria](#65-behavioural-discipline-criteria). |
| **Setup-level evidence** | Enough paper trades per setup, by symbol/timeframe/regime, to say something statistically meaningful — see [§3](#3-setup-classification). |
| **Human vs. system comparison** | Where the trader deviated from AlphaTrade's pre-trade/paper-validation guidance, and whether that deviation helped or hurt — via `GET /journal/comparison` and `/human-vs-system/{id}` ([human_vs_system.md](../human_vs_system.md)). |
| **Explicit non-goal** | **No profitability claim or guarantee is made or implied by this protocol, by AlphaTrade, or by any report it produces.** Paper fills are simulated, not exchange fills (see [paper_validation.md](../paper_validation.md) limitations). |

This protocol is a **process document**. It does not add features, change risk
defaults, or enable any new execution path. It only defines how existing
capabilities are used and read.

---

## 2. Evaluation duration and sample targets

### 2.1 Duration

- **Two calendar weeks** of active operating days (proposed default: 10
  trading days; extend for weekends/holidays as needed). This is a **trial
  window**, not a fixed regulatory or contractual term — it may be extended
  per [§2.4](#24-when-the-sample-is-insufficient).
- The window starts once a strategy is `paper_eligible` (see
  [strategy_library.md](../strategy_library.md#paper-eligibility-slice-38))
  and paper validation and/or manual paper trading has begun.

### 2.2 Minimum trade and observation targets (proposed defaults)

| Level | Minimum target over 2 weeks | Rationale |
|---|---|---|
| Overall (all setups combined) | ≥ 20 closed paper trades | Matches the existing `backtest_tier1_min_confirm_trades` default (20) already used for non-backtest confirmation evidence ([backtesting.md](../backtesting.md)). |
| Per **important** setup (Tier 1 candidate) | ≥ 10 closed trades | Below AlphaTrade's own Tier 1/Tier 2 backtest thresholds (30/15) by design — two weeks of live paper flow is a *smaller, faster* sample than a backtest, so its bar for promotion must be at least as strict, not looser. |
| Per symbol × timeframe × regime bucket | ≥ 5 observations before any bucket-specific claim | Below this, buckets are reported as `insufficient_data`, matching the `insufficient` confidence label already used in journal statistics (`journal_statistics_service`, <5 closed trades). |
| Daily minimum | ≥ 1 journal entry per trading day, even on no-trade days ("no trade taken, here is why") | Keeps the discipline record continuous — see [§4](#4-daily-operating-loop). |

These are **evaluation-window minimums for drawing conclusions**, not trade
quotas. Never manufacture trades to hit a number — see
[§8 defect-triage and anti-gaming note](#8-defect-triage-rules).

### 2.3 Target observations per important setup

"Important" means any setup the trader intends to size normally or scale in
the near term (typically the existing `StrategyId` / `setup_id` values already
tracked in [trading_analytics.md](../trading_analytics.md#setup-tracking), e.g.
`htf_trend_pullback`, `liquidity_sweep_reversal`).

Proposed target: **10–20 observations per important setup within the two-week
window**, split as evenly as practical across the symbol/timeframe/regime
buckets that setup actually trades. If a setup only fires 2–3 times in two
weeks, it is **not evaluable yet** in this window — carry it into the next
cycle (see [§2.4](#24-when-the-sample-is-insufficient)) rather than judging it.

### 2.4 When the sample is insufficient

A setup, symbol, or bucket is **insufficient** when it has fewer observations
than the §2.2/2.3 minimums. When insufficient:

1. Label every report and metric for that setup/bucket `insufficient_data`
   (mirrors the existing `insufficient` / `needs_more_sample` /
   `insufficient_data` states already returned by
   `paper_validation.md` promotion recommendations and
   `strategies/{id}/paper-eligibility`).
2. **Do not promote.** Do not report a win rate, expectancy, or "this setup
   works" conclusion from a sample below the minimum — report the raw count
   and explicitly flag it as too small to be meaningful.
3. Extend the collection window for that setup only (see
   [§9](#9-final-decision-outcomes) — "extend sample collection"); do not
   extend the whole trial just to prop up one thin setup.
4. Never average across buckets to disguise a thin sample as an aggregate
   pass — buckets are reported separately per [§3.4](#34-separate-evidence-by-symbol-timeframe-and-market-regime).

**Rule of thumb: a promotion decision made on fewer than the §2.2 minimum
trades is not a promotion decision — it is a guess, and must be labeled as
one if reported at all.**

---

## 3. Setup classification

This protocol layers a **paper-evaluation tier** on top of (not instead of)
the existing backtest evidence tiers in
[backtesting.md §Setup evidence tiers](../backtesting.md) and the paper
validation `recommendation` field in [paper_validation.md](../paper_validation.md).
Backtest tiers judge historical replay evidence; the tiers below judge the
**two-week live-paper trial** evidence layered on top.

### 3.1 Tiers

| Tier | Meaning | Minimum evidence (proposed defaults) |
|---|---|---|
| **Tier 1 — Trusted for continued normal paper sizing** | Setup has enough same-window paper trades with acceptable metrics and full rule compliance to keep trading it at planned size. | ≥ 10 closed paper trades in the window; win rate and expectancy computed per [§3.3](#33-minimum-evidence-requirements); rule compliance ≥ 90% (`followed`, using the existing worst-assessment classification from `journal_statistics_service`); max drawdown for the setup's paper equity slice within the configured risk settings ([risk_management.md](../risk_management.md)); backtest evidence (if any) not below `tier2`. |
| **Tier 2 — Provisional / probe-only** | Setup shows early promise or has passed backtest tier1/tier2 but has not yet accumulated enough live-paper trades, or has minor rule-compliance gaps. | 5–9 closed paper trades, or ≥ 10 trades with rule compliance 75–89%, or expectancy positive but with wide confidence interval (small n). Trade at reduced/probe size only, per the trader's existing risk settings — this protocol does not introduce a new sizing mechanism. |
| **Tier 3 — Under review / not yet evidenced** | New setup, thin sample (< 5 trades), rule compliance < 75%, negative expectancy, or any open P0 defect touching that setup (see [§8](#8-defect-triage-rules)). | Any trade count below Tier 2 thresholds, or any setup with an unresolved critical lesson blocker (`unresolved_lesson_observations` per [strategy_library.md](../strategy_library.md#paper-eligibility-slice-38)). |

Tier assignment is **evaluation-window scoped** — a setup's tier can differ
between the two-week paper-trial tier here and its backtest evidence tier in
`GET /journal/setup-evidence` / `research_validation.md`. Both should be
reported side by side, never merged into one number.

### 3.2 Promotion and demotion rules

- **Promotion (Tier 3 → 2, or 2 → 1)** requires meeting the *higher* tier's
  minimum evidence in [§3.1](#31-tiers) **and** no open P0 defect for that
  setup ([§8](#8-defect-triage-rules)) **and** an explicit human sign-off
  recorded in the [setup evidence summary](#73-setup-evidence-summary-template)
  — promotion is never automatic.
- **Demotion (Tier 1 → 2, or → 3)** is immediate and does not wait for the
  end of the two-week window when any of the following occurs:
  - Rule compliance drops below the tier's minimum in a rolling assessment.
  - A P0 defect is opened against that setup.
  - Two consecutive losing trades exceed the setup's expected loss size
    (stop not respected, or MAE far beyond planned invalidation).
  - The setup is flagged `restricted` by existing paper-eligibility gates
    ([strategy_library.md](../strategy_library.md#paper-eligibility-slice-38)).
- Demotions are logged in the daily report ([§7.1](#71-daily-evaluation-report))
  the day they occur — never silently.
- **No setup may be promoted on the strength of a single strong trade or a
  short win streak.** Promotion always references the minimum sample sizes in
  [§2](#2-evaluation-duration-and-sample-targets) and [§3.1](#31-tiers).

### 3.3 Minimum evidence requirements

Per setup, the evidence summary must report (using existing, already-computed
fields where possible — no new metric definitions):

| Metric | Source |
|---|---|
| Win rate | `journal_statistics_service` win/loss/breakeven split, or `paper_validation` metrics |
| Expectancy (after estimated fees/slippage) | `journal_trades.net_pnl` aggregate, or `paper_trades` fees/slippage fields |
| Average win / average loss | Same PnL family as above |
| MFE / MAE | `journal_trades` excursion fields (manual entry or AT-032 replay) — see [journal_intelligence_foundation.md §5](../journal_intelligence_foundation.md) |
| Drawdown (setup-level slice) | Derived from the sequence of closed trades for that setup within the window; report alongside, not instead of, portfolio-level `max_drawdown_pct` ([paper_validation.md](../paper_validation.md)) |
| Rule compliance | `journal_trade_rule_checks` worst-assessment classification (`violated` > `partial` > `compliant` > `unassessed`) |

Metric families with insufficient sample use `None`/`insufficient_data`
labels rather than a silently computed number — matching existing
`journal_statistics_service` semantics (never a silent zero).

### 3.4 Separate evidence by symbol, timeframe, and market regime

Do not report one blended number per setup. Break out at minimum:

- **Symbol** (e.g. BTC-PERP vs. ETH-PERP)
- **Timeframe** (e.g. 15m vs. 1h vs. 4h)
- **Market regime** (`MarketRegime` values already recorded on journal trades,
  e.g. trending / ranging / high-volatility)

A setup can be Tier 1 on one symbol/timeframe/regime combination and Tier 3
on another within the same window — report both. Buckets below the §2.2
minimum are `insufficient_data`, never merged upward into a healthier bucket.

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
     system's read — this feeds [§6.5](#65-behavioural-discipline-criteria)
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
| Expectancy after estimated fees/slippage | (win rate × avg win) − (loss rate × avg loss), net of `fees`/`slippage`/`funding` | Journal PnL fields |
| Average win / average loss | Mean net PnL per winning/losing trade | Journal PnL fields |
| Maximum drawdown | Equity-curve based, both portfolio-level and setup-level slice | `paper_validation.md` `max_drawdown_pct` pattern |
| Rule compliance | % `followed` across recorded rule checks (worst-assessment per trade) | `journal_trade_rule_checks` |
| Revenge-trade violations | Count of trades entered inside the mandatory cooldown window after a loss ([§4.8](#4-daily-operating-loop)), or that violate `overtrading_guard_enabled` | Journal timestamps + risk-behavior analytics |
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

- Sample size at or above the [§2](#2-evaluation-duration-and-sample-targets)
  minimums for any setup being judged.
- Tier assignment per [§3](#3-setup-classification) is internally consistent
  (metrics support the claimed tier).
- Evidence is broken out by symbol/timeframe/regime, not blended.

#### 6.2.3 Profitability evidence

- Reported **as observed data only** (expectancy, win rate, drawdown) with
  explicit confidence labeling by sample size.
- **Never reported as a guarantee, projection, or claim of future
  performance.** Two weeks of paper data is a discipline and dependability
  signal first, and at most a weak profitability signal — label it as such
  in every report.

#### 6.2.4 Behavioural-discipline criteria

- Rule compliance ≥ proposed default 90% for any setup considered for Tier 1.
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

Sample size: <n trades> (minimum required: <per §2/§3>) — <sufficient|insufficient>
Breakdown: symbol × timeframe × regime table (counts, win rate, expectancy per bucket)
Win rate: <...> | Expectancy (net of fees/slippage): <...>
Avg win / avg loss: <...> | MFE/MAE (avg): <...>
Setup-level max drawdown: <...>
Rule compliance: <...>%
Revenge-trade violations: <count>
Early-exit cost / missed-profit total: <...>
Backtest evidence tier (if any, from GET /journal/setup-evidence): <tier1|tier2|tier3|none>
Two-week paper-trial tier (this protocol, §3): <Tier 1|2|3>
Tier change this window: <none | promoted from X | demoted from X — reason>
Recommendation: <continue|revise|demote|archive|extend sample — see §9>
```

### 7.4 End-of-week review

```markdown
## End-of-Week Review — Week <1|2> (<date range>)

Trades taken: <n> | Journal completion rate: <%>
Setups evaluated this week: <list with tier and sample size>
Behavioural-discipline summary: rule compliance <%>, revenge-trade violations <n>,
  guard triggers <n>
System reliability: scheduler/tick success rate <%>, stale-data incidents <n>,
  P0 defects <n> (see §8)
Human vs. system: entry timing %, plan adherence score, actor scorecard summary
  (GET /journal/comparison)
Carried-over issues into week 2 (if week 1): <list>
Preliminary read (not a decision): <free text — explicitly non-binding>
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
<table: setup | sample size | tier assigned | recommendation | rationale>

### Product-readiness assessment
<pass/fail against §6.2.1 criteria, with evidence>

### Strategy-evidence assessment
<per-setup, referencing §3 tiers and sample sizes>

### Profitability evidence (explicitly non-binding, no guarantees)
<observed win rate / expectancy / drawdown per setup, with confidence labels>

### Behavioural-discipline assessment
<pass/fail against §6.2.4 criteria, with evidence>

### Human vs. system comparison summary
<...>

### Final decision (select one or more per setup — see §9)
- [ ] Continue paper testing
- [ ] Revise setup
- [ ] Demote setup
- [ ] Archive setup
- [ ] Extend sample collection
- [ ] Prepare restricted real-money discussion (only if criteria in §9 are met)

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

At the end of the two-week window, each setup receives exactly one primary
outcome (a setup may carry secondary notes, e.g. "revise AND extend"):

| Outcome | When to choose it |
|---|---|
| **Continue paper testing** | Tier 1 or solid Tier 2 evidence, no P0 defects, discipline criteria met — keep running as-is for another cycle to build a larger sample before any further decision. |
| **Revise setup** | Evidence shows a specific, correctable issue (e.g. stop placement too tight, entries firing in the wrong regime) — update the strategy card/structured rules ([strategy_library.md](../strategy_library.md)) and restart the setup's sample count at the new version. |
| **Demote setup** | Tier 1 → 2 or 2 → 3 per [§3.2](#32-promotion-and-demotion-rules) triggers, without necessarily discontinuing it — keep at reduced size while gathering more evidence. |
| **Archive setup** | Persistent negative expectancy, chronic rule-compliance failure, or a P0 defect tied to the setup's logic that cannot be resolved — mark the strategy `archived` ([strategy_library.md](../strategy_library.md#lifecycle)); stop trading it. |
| **Extend sample collection** | Sample below [§2](#2-evaluation-duration-and-sample-targets) minimums for that specific setup/bucket — continue collecting without promoting or demoting; do not treat the thin sample as a verdict. |
| **Prepare a restricted real-money discussion** | Only after **strong, multi-window evidence**: Tier 1 status sustained across at least two consecutive two-week windows, product-readiness criteria fully met with zero unresolved P0 defects, behavioural-discipline criteria met, and explicit human sign-off. This outcome **starts a discussion**, not a transition — it does not itself enable `ENABLE_REAL_TRADING` or any live execution path. Any move toward Mode B/C/D broker integration follows the existing phased safety roadmap in [AT010_real_money_safety_roadmap.md](../AT010_real_money_safety_roadmap.md) and requires a separate, explicitly authorized safety/risk/approval program (per workspace trading-safety rules) — this protocol cannot authorize that step on its own. |

No outcome in this table changes `EXECUTION_MODE`, `ENABLE_REAL_TRADING`,
`EXCHANGE_MODE`, or any deployment configuration. Those remain governed by
existing repository safety controls (`core/deployment_safety.py`,
`core/exchange_safety.py`).

---

## Related repository documentation

- [paper_validation.md](../paper_validation.md) — paper bot runtime, scan/tick, promotion recommendations
- [strategy_library.md](../strategy_library.md) — strategy lifecycle, paper eligibility gates, lesson → version flow
- [backtesting.md](../backtesting.md) — setup evidence tiers (tier1/tier2/tier3), walk-forward semantics
- [research_validation.md](../research_validation.md) — advisory bridge from backtest evidence into the paper validation queue
- [journal_intelligence_foundation.md](../journal_intelligence_foundation.md) — canonical journal trade schema, statistics, excursion replay, human-vs-system decision quality (AT-036)
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

- All specific numbers (10 trading days, 20/10/5 minimum trade counts, 90%
  rule-compliance bar, cooldown durations) are **recommended starting
  defaults** for the first run of this protocol. They are intentionally
  conservative and should be revisited after the first two-week cycle based
  on observed data volume — do not treat them as fixed policy.
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
