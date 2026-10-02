# Confluence Intelligence V2 — analysis foundation

Branch: `codex/confluence_intelligence_v2_001`.
Exact parent baseline: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092`.
PR target: `codex/release_consolidation_wave_002`, verified at that exact SHA.

## Boundary and canonical records

`app.confluence.assess_confluence` is a public, typed, pure analysis function.
It accepts the existing `ExecutableStrategyPolicy`, `AssessmentCommand`,
`SetupAssessment` and `FirstSliceEvidenceBundle`. It does not rerun a detector,
fetch market data, write records, create Candidates, evaluate ActionEligibility,
or call execution. It supports the existing Nested and SFP adapter kinds and
returns the exact original setup record with its existing identity and hash.

The caller supplies authorized records. Organization, user, account, strategy
version, compiled setup, evidence window, policy and observation bindings are
checked. Corrupt hashes and foreign lineage are rejected. Payload availability,
causality and freshness are checked at the explicit analysis time. SFP's deduplicated
observation IDs and Nested's canonical history envelope are preserved.

The assessment is exposed as `ConfluenceAssessment`, with typed components,
`AssessmentCoverage`, `HistoricalExpectancy`, `DataQuality` and
`RiskEligibilityContext`. This initial foundation has no HTTP endpoint, UI,
persistence migration or runtime caller. Existing execution and eligibility paths
do not import this package. Later presentation integration should display score,
coverage and the analysis state together.

```python
from app.confluence import assess_confluence

assessment = assess_confluence(
    executable=resolved_canonical_policy,
    command=canonical_command,
    setup=existing_setup_assessment,
    evidence=existing_evidence_bundle,
    user_id=authorized_user_id,
    account_id=authorized_account_id,
    assessed_at=explicit_aware_timestamp,
    policy_version="confluence-research/v2.001",
    # Optional existing canonical records:
    portfolio=portfolio_snapshot,
    portfolio_observed_at=actual_portfolio_snapshot_timestamp,
    daily_risk=daily_risk_state,
    analytics=exact_strategy_version_analytics_report,
    eligibility=existing_action_eligibility,
    btc_context=measured_closed_btc_series,
)
payload = assessment.model_dump(mode="json")
```

## Separate evidence dimensions

- **Hard requirements:** canonical rule results, causal/current setup record,
  bound closed candle history and required-role payloads. Every hard check has
  zero scoring weight. A false canonical check produces
  `hard_requirements_failed`; absent, unsupported, corrupt, future or stale
  required payload produces `required_data_unavailable`. Both suppress the
  quality score. Optional evidence cannot compensate for either condition.
- **Optional confluence:** HTF, volume, flow, CVD, OI, funding, volatility,
  liquidity and measured BTC context, with independent availability coverage.
- **Quality components:** only the five explicitly normalized research components
  below. Context is never silently given a score contribution.
- **Historical expectancy:** recorded canonical closed-journal net PnL for the
  exact strategy-version cohort, including sample denominator, cohort filters,
  minimum sample threshold and truncation. No expectancy is fabricated when
  history or recorded PnL is missing. It has zero quality weight.
- **Data quality:** unavailable/stale component keys, required/optional/context
  coverage and insufficient score-coverage flag.
- **Risk eligibility:** the existing canonical `ActionEligibility` record is
  copied with its own availability/validity. Missing eligibility stays unknown;
  fresh or stale recorded blocks never alter the quality score or setup state.
  Existing Risk and ActionEligibility remain final trading authorities.

Every component exposes availability, value, unit, normalized contribution,
weight, source references, timestamp, freshness, age and reason. Missing evidence
retains null values/timestamps and an explicit reason. Unusable inspected payloads
may retain their measured value for explanation, with no normalized contribution.
Daily risk also carries recorded day, PnL, limits, target and trade-count facts;
exposure carries recorded account equity. These facts do not grant permission.

## Versioned quality policy

`get_policy("confluence-research/v2.001")` returns a frozen provisional policy.
Unknown versions fail. The complete weights, thresholds, arithmetic and
normalization identifiers are retained by a policy content hash in each result.
No strategy parameter, detector specification or active fusion policy is changed.
Future weight/threshold changes require a new explicit registry version.

| Component | Weight | Normalized contribution / measured context |
| --- | ---: | --- |
| Pattern structure | 20 | Canonical confirmed setup = 1; other states = 0. All detector hard checks stay independent. |
| Higher timeframe regime | 20 | Direction of the last two closed 4h closes: aligned = 1, opposed = 0, flat = 0.5. Explicit ordinal proxy. |
| Volume | 20 | `min(1, trigger_base_volume / prior_20_bar_mean / 1.5)`; full lookback and positive denominator required. |
| Five-minute order flow | 20 | `(1 + direction_sign * signed_quote_imbalance) / 2` from canonical real prints. |
| CVD | 20 | Current 5m base-volume delta sign supports setup = 1; opposes = 0; undefined sign remains unscored. |
| Open interest | 0 | Provider-reported absolute quantity and original units; no inferred directional growth. |
| Funding | 0 | Provider-reported settled rate; no annualization or invented directional score. |
| Volatility | 0 | Measured trigger candle `(high-low)/close`; no ATR or directional inference. |
| Liquidity | 0 | Explicitly unsupported: this canonical bundle has no depth/liquidity payload. Candle volume is not a substitute. |
| BTC context | 0 | Optional measured, closed BTCUSDT series on the same venue/market; two-close return only. |
| Existing exposure | 0 | Existing `PortfolioState.open_exposure_notional`, requiring its actual snapshot timestamp. |
| Daily risk state | 0 | Existing `DailyRiskState`, with recorded lock, PnL, count and limits. |
| Measured strategy expectancy | 0 | Existing exact-version `StrategyAnalyticsReport.overall.expectancy` and PnL sample count. |

Quality score = `100 * sum(weight * normalized_contribution) / available_scored_weight`,
rounded to two decimal places with Decimal precision 28 and half-even rounding.
The caller's Decimal context is restored. **80 means 80 quality points, never an
80 percent probability of winning.** There is no probability field or calibration
claim. The 80-point reference band is descriptive only.

Missing optional evidence reduces component coverage. Missing/undefined scored
evidence also reduces available-weight coverage against the fixed total of 100.
The available-weight mean is explicit: a high score with low coverage can occur.
Coverage below 0.5 is flagged, and must accompany any displayed score. Coverage
is a completeness ratio, not statistical confidence or a trading gate.

HTF and BTC candles must be closed, contiguous, source-bound, causal and younger
than one full candle interval. Flow and derivatives reuse their existing canonical
consumer validators and freshness policies. Required flow and derivative payloads
must also match their selected command envelopes. Portfolio/daily snapshots have
a versioned 60-second analysis age limit; analytics has a 24-hour limit. A missing
portfolio timestamp remains unknown and is never replaced by the analysis clock.

The two-close HTF measure is a provisional proxy. CVD and flow share prints and
are correlated evidence; these weights do not imply independent confirmation or
an empirically demonstrated edge. CVD retains the existing bounded ten-minute,
zero-at-window-start reset semantics. No absolute provider-CVD claim is made.

## Descriptive comparison helpers

`app.confluence.comparisons` exposes `ResearchCase`, `FilterComparison` and:

- `compare_with_order_flow_filter(cases)`: normalized directional imbalance >= 0.5
  (nonopposing; a neutral measured value passes).
- `compare_with_cvd_filter(cases)`: supportive current 5m delta sign = 1.
- `compare_with_oi_filter(cases, minimum_open_interest=..., units=..., filter_version=...)`:
  explicit nonnegative absolute OI threshold; identical quantity units required.

Each case pairs a recorded assessment with an existing `JournalTradeRead`.
Comparisons require one tenant/user/account, strategy version, compiled setup,
detector, market/source identity, direction, analysis-policy hash and journal
source/exchange cohort. Duplicate journal IDs, foreign attribution and corrupt
assessment hashes fail. Open/missing/nonfinite outcomes, incomplete timestamps,
outcomes entered before assessment, and blocked analyses are excluded and counted.
Only recorded closed net PnL is used; fees are not deducted a second time.

Results show the same eligible baseline, filtered subset, measured rejected
subset, missing-filter count, excluded-outcome count, expectancy difference and
sample counts. Empty cohorts yield null expectancy. Twenty observations is a
versioned descriptive sample reference, not evidence of an edge. Filter thresholds,
units, operator, method, version and sample reference are content-hashed.

OI thresholds do not establish whether OI increased or which side entered.
Missing filters remain unknown and are not classified as measured rejection.
These comparisons report association only: filtered trades are a subset of
baseline, and selection, regime, missing evidence and execution costs can confound
differences. They do not establish causality or recommend activation.

## Verification and handoff

- 57 new deterministic cases pass, including both directions/families, exact
  80-point semantics, missing/stale/corrupt required evidence, coverage, scope
  rejection, unchanged risk decisions, expectancy denominators, comparison
  exclusions and independent Decimal arithmetic.
- Focused backend regression matrix: **504 passed, 8 skipped**. The eight existing
  Nested/SFP governed paper persistence cases require local PostgreSQL, which was
  not provisioned for this pure analysis change. One existing Starlette/httpx
  deprecation warning remains. No new test is skipped.
- Full backend Ruff lint and format checks pass: 1,043 files formatted.
- Focused mypy passes for all seven confluence source modules.
- No frontend code, execution, eligibility, detector, dependency, database
  migration, deployment configuration or live-trading setting is changed.
- No full repository test-suite, browser, deployment or live venue validation is
  claimed. GitHub CI may run after draft PR creation; it is not awaited.

Next action: review the draft PR and its provisional score/coverage semantics.
Any runtime presentation, additional canonical liquidity adapter, expanded HTF
model, paired OI changes or policy calibration is separate research scope.
No automatic eligibility/execution wiring is authorized by this change. STOP.
