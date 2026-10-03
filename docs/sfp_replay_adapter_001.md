# SFP replay adapter 001

Branch: `codex/sfp_replay_adapter_001`.
Exact parent: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092` (PR176).
Draft PR targets `codex/release_consolidation_wave_002` while PR176 remains open.

## Existing authorities and execution boundary

SFP is a research mode in PR173's existing Strategy Replay engine, service,
BacktestRun/Dataset jobs, worker/background execution, result JSON, verification,
comparison, cancellation, tenant/RBAC and audit authorities. It uses PR176's
canonical `detect_sfp`, `derive_levels`, level knowability check, BrainSetupState,
SfpDetection, SfpQuality and observation contracts. There is no alternate SFP
detector, setup lifecycle store, replay platform, migration or dependency change.

The adapter version is `sfp-research-replay-001/v1`. The outer replay engine keeps
`strategy-replay-001/v1`; existing Nested serialization and configuration remain
unchanged. An independent exact-base replay produced the same Nested result hash
before and after this change:
`b31440f48ac0382386a34610fb427add41a253d94dd377daa4a3ac4447555761`.

**SFP has no authorized automatic execution plan.** Results carry `metrics=null`,
`trades=[]`, sample `net_pnl=null`, and `mean_r=null`. Candidate trace entries carry
`entry=null`, `stop=null`, `targets=[]`, `risk_decision=null` and no trade sequence.
Available target space remains the canonical measured distance to opposing known
structure; it is never converted to a trade target. Capital, fees and slippage in
the shared request contract remain frozen comparison inputs, not simulated SFP
account activity. Funding observations are native settled-rate evidence, not PnL.

No execution Candidate, Brain operational setup/event, backtest trade, paper
trade, journal trade, account or risk state is created. The canonical detector's
confirmed setup is reported as `structural_confirmation_only`; other states are
`not_eligible`. This is not CandidateLifecycleService or ActionEligibility approval.
Risk applicability is `not_evaluated_no_authorized_execution_plan`. The adapter
never manufactures the entry/stop/size needed to ask RiskEngine for a verdict.
Risk blocks are therefore not applicable to this SFP version. Existing Nested
simulated risk blocks continue to use RiskEngine.

## Historical inputs and API

Use the existing Trader endpoint `POST /backtests/replays`, supplying the exact
immutable **SFP** strategy version ID, existing dataset ID, chronological windows,
shared assumptions, minimum sample threshold and idempotency key. Parameters come
only from the immutable version's `pattern_spec`; proposed parameters must use an
explicit fork through StrategyVersioningService.

The additional optional `sfp_evidence` object has these fields:

| Field | Existing canonical contract | Purpose |
| --- | --- | --- |
| `candles` | `{bar: OhlcvBar, observation: PublicMarketObservation}` pairs | Required trigger-candle proof and original receipt clocks |
| `context_levels` | `StructuralLevel` with complete basis bars/observations | Historical higher-timeframe alignment and opposing structure |
| `order_flow` | `OrderFlowObservation` | Verified two five-minute print windows, bounded CVD and flow |
| `derivatives` | `DerivativeObservation` | Venue-bound OI and settled funding observations |

These are serialized canonical historical facts, not references to a live
provider. For example, a producer with existing canonical pairs constructs:

```python
proof = SfpReplayEvidence(
    candles=[
        ReplayCandleEvidence(bar=bar, observation=observation)
        for bar, observation in historical_pairs
    ],
    context_levels=historical_context_levels,
    order_flow=historical_order_flow,
    derivatives=historical_derivatives,
)
# Supply proof as StrategyReplayCreate.sfp_evidence, then serialize mode="json".
```

Do not derive receipt clocks from candle timestamps. Legacy HistoricalCandle rows
alone cannot prove when an SFP level became knowable. Without explicit candle
proofs the job completes as missing data, with no invented setup or return.
Historical receipt acquisition/import is outside this adapter. Synthetic fixture
tests demonstrate contracts only and do not establish market performance.

Dataset bars establish coverage and validate symbol, venue, timeframe, prices,
volume and closed interval against each supplied proof. Proof hashes, envelope
binding, revision uniqueness, structural proof, optional evidence and freshness
hashes are checked. Context levels retain actual higher timeframes and canonical
source binding. The real detector excludes future levels at each sweep open.

Read results and verify using existing `GET /backtests/{id}` and
`POST /backtests/{id}/verify`. Existing trade-list reads return zero SFP trades.
The existing detail page displays SFP samples, buckets, missing/stale evidence and
limitations without displaying a zero return or simulated trade metrics.

## Causality and evidence interpretation

Each training/evaluation window uses an independent canonical detector history.
Candles must be closed, contiguous and fully covered within the declared windows
and as-of boundary. Neither setups nor trigger-candle history cross windows.
Explicit context proofs may precede a window, but become usable only at their
actual known_at, including pivot right-hand confirmation and receipt time.

Detection occurs at the canonical observation's availability time, which can
follow the candle close. Receipt times remain frozen. A proof received after the
window end is missing evidence for that window. Missing, forming, incomplete or
stale required proofs break contiguous detector history. Earlier valid segment
observations remain recorded; later facts cannot repair the gap retrospectively.
Expiry and invalidation counts are observed canonical events, not inferred price
outcomes across evidence gaps. The frozen trace makes these gaps explicit.

Optional evidence is selected by exact market/source identity and historical
availability time at each candle observation and setup event. CVD and five-minute
flow use the existing required-flow consumer checks; OI/funding use the existing
native derivative consumer checks. Freshness is re-evaluated at the historical
decision clock. Future observations cannot affect an earlier event. Missing and
stale evidence has no usable observation/value in the research projection.

Canonical SfpQuality remains unchanged: its disconnected CVD/flow/OI components
still report UNSUPPORTED. The separately bound `research_evidence` and per-candle
`evidence_frames` expose supplied native facts. Those facts do not alter SFP
confirmation, infer directional setups, change strategy policy, or authorize an
execution Candidate. Candle volume never substitutes for trade-print evidence.

## Samples and version comparisons

`replay.structural_levels` records the actual proven level considered at each
closed-candle observation, direction match, significance gate and freshness.
`candidates[].sfp_detection` retains exact canonical sweep, reclaim, confirmation,
failure, invalidation and expiry events, reason codes, quality components, proof
identities and knowability clocks. Quality includes HTF alignment, candle volume,
target space and measured directional efficiency.

Window `lifecycle_counts` count unique episodes with sweeps, forming states,
reclaims, confirmations, failed reclaims, invalidations and expiries. These counts
overlap by design. Unique level count and per-candle level-consideration count
are distinct. `setup_count` counts unique observed episodes; the inherited
`candidate_count` field counts unique structurally confirmed setups, not created
execution Candidates. `trade_count=0` records the absence of trades.

`research_buckets` count unique setup episodes grouped by window, symbol,
timeframe, direction, level type, exact strategy version, quality bucket and
measured regime proxy. Each episode is assigned using its last observed event in
that window. Confirmation counts retain episodes that later fail or expire.
Quality buckets are **coverage counts** of eight canonical price/volume components
(`measured_N_of_8`), not rankings or aggregate confidence. Regime bands describe
directional efficiency below one-third, below two-thirds, or at least two-thirds;
unmeasured history stays explicit. They are not a validated regime classifier.

The declared minimum sample threshold applies to unique SFP episodes. Below it
the result is `insufficient_sample`; complete samples meeting it remain only
`descriptive_only`. Missing required coverage is `missing_data`. Optional evidence
limitations remain explicit even if the episode threshold is met.

`POST /backtests/replays/compare` accepts the existing baseline/proposed run IDs.
It requires identical historical candle inputs, exact full SFP evidence and
receipt clocks, dataset, assumptions, windows, engine/adapter, risk-limit snapshot,
sample threshold and strategy family/instrument/direction. The versions may have
different explicit parameter sets. Results expose both versions' window lifecycle
counts and research buckets. SFP `evaluation_net_pnl_delta` is always null and
`improvement_claim` is always false, including when proposed counts look better.
No optimizer, strategy promotion or automatic improvement claim is present.

## Determinism and validation

The frozen job config binds strategy ID/content/parameter set, adapter version,
entire evidence payload (including receipt and freshness metadata), dataset and
candle hashes. Results bind canonical events, levels, evidence frames, buckets,
counts and limitations. Verification replays the same frozen inputs and checks
both stored content and output identity. Immutable strategy content is recomputed
at the replay boundary. Evidence, receipt, quality, dataset, assumptions and
version tampering refuse verification. Restart/reload and differing Decimal
contexts produce identical identities. Existing tenant and idempotency fences
remain in force.

Final commands, focused counts and limitations are recorded in `HANDOFF.md`.
No migration, live trading, market acquisition, deployment, activation, main merge
or CI wait is part of this task.
