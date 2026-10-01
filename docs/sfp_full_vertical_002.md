# SFP Full Vertical 002 handoff

Parent: [PR158](https://github.com/Fejjii/AlphaTrade-AI/pull/158), commit
`ad08031229899e3299830a9767a2ca39ff5cb9b6`.
Child branch: `codex/sfp_full_vertical_002`; draft PR targets
`codex/sfp_detector_foundation_001`. The accepted detector and its contracts,
level derivation, quality calculation and synthetic tests are unchanged.

## Canonical runtime

SFP registers as `StrategyId.SFP` / `swing_failure_pattern/v1` in the existing
strategy library. Explicit typed parameters and the full authored spec bind to
an immutable `UserStrategyVersion` and canonical compiled hash. The existing
compile/review/approval service remains required; proposing a template creates
no execution permission. Legacy AST serialization and parameter bounds remain
compatible. The generic AST trigger for SFP fails closed; the registered family
adapter provides setup truth through the sole `evaluate_setup` boundary.

Watcher uses shared OHLCV family assembly. Every original candle observation is
selected under the existing canonical STRUCTURE role, and the latest candle is
also selected under TRIGGER_OHLCV. The canonical evidence window binds the whole
causal proof, market identity, direction, immutable version, compiled definition
and required policies. Current final confirmation alone can become
`CONFIRMED_SETUP`. Older confirmations, provisional candles, missing/stale data,
contract conflicts and future evidence cannot create a Candidate.

Confirmed SFP goes through the existing Watcher persistence/lease fence and
`CandidateLifecycleService.create_from_confirmed_setup`. Tenant/version-scoped
Brain episode locking adds structural idempotency to existing canonical window
uniqueness. One scan selects one current confirmed episode deterministically if
several levels confirm together. Other detected episodes remain in setup history.
Existing account decisions are preserved on detector replay. Existing risk and
ActionEligibility remain authoritative: the daily-loss gate blocks both directions.

## Durable evidence and setup history

Migration `a2sfp002`, after `a1brain001`, adds the first durable adapter for the
existing `PublicMarketObservation` envelope, with optional original canonical
OHLCV payloads. This is public market evidence, with no tenant owner; it introduces
no alternative evidence identity or strategy-specific observation contract.
Public receipts are immutable and keyed by complete evidence identity plus the
existing observation UUID. Contradictory content fails closed. Later acquisition
cannot overwrite or backdate first receipt clocks. Historical download at startup
is observed at download time and cannot invent earlier SFP setups.

Bounded history reads retain original candle prices and known-at times across
restarts and rolling provider windows, including setup expiry horizons longer
than one fetch. Reads select the latest revision knowable at evaluation time;
a provider regression to an older known revision fails closed. Live provider
fetches remain bounded by level/quality lookback; retained evidence supplies the
longer active-episode horizon. Missing intervals continue to fail closed.

SFP uses the existing `strategy_brain_setups` and `strategy_brain_setup_events`
tables for FORMING, CONFIRMED, INVALIDATED and EXPIRED. Market events converge on
tenant/version/episode-scoped IDs; terminal episodes cannot revive. Durable clock
expiry and evidence-unavailability events can be recorded without inventing a
market candle. Failures never advance the stored market evidence timestamp.
History retains detector event/setup IDs, scoped setup IDs, level ID and basis
proofs, sweep/reclaim/confirmation observation IDs, evidence/closure/observation
times, strategy version and compiled hashes, quality components and risk links.

## API and grounded reads

- `POST /strategy-brain/templates/sfp`: explicit typed SFP research template,
  through the existing tenant/user library authority and Trader RBAC.
- Existing `GET /strategy-brain/overview`: includes registered SFP versions
  and tenant-scoped setup projections.
- Existing `GET /strategy-brain/setups/{setup_id}`: grounded setup history.
- Existing strategy Brain research lifecycle endpoint accepts SFP; it does not
  replace canonical approval.
- Existing interactive Brain reads recognize SFP, sweep and reclaim queries and
  expose stored condition, swept structure, quality and target-space evidence.

Confirmed reclaim, failed reclaim, breakout and structural invalidation remain
separate detector conditions. Missing HTF context is reported as MISSING; CVD,
order flow and open interest remain UNSUPPORTED. Available target space is a
structural distance component, not an executable target or win probability.
Read freshness uses candle closure and the approved evidence-age parameter;
new scans cannot make old market evidence appear fresh. No read claims current
market conditions without current proof.

## Intentionally deferred

- SFP trade-plan terms and automated execution authorization. Existing canonical
  risk eligibility runs first; new automated SFP plans return
  `sfp_execution_plan_not_authorized`. No targets/stops are invented from quality.
- Telegram producer/delivery and new alert projections.
- Optional HTF acquisition/confluence and unsupported trade-flow/OI inputs.
- Production migration application, runtime activation, CI waiting, merge and
  deployment. The parent consolidation must apply `a2sfp002` before enabling
  these runtime reads/writes. Public receipt retention/archival is operational
  follow-up; runtime history reads are bounded.

No new Candidate authority, risk engine, execution path, strategy store or
strategy-specific setup table was introduced. Validation uses synthetic market
sources and a disposable local PostgreSQL 16 container; no provider credentials.

## Focused validation

Run from `backend`:

```sh
.venv/bin/pytest tests/test_sfp_detector.py tests/test_sfp_strategy_brain_runtime.py \
  tests/test_strategy_brain_nested.py tests/test_at067_canonical_strategy_evaluation_policy.py
.venv/bin/mypy src/app/strategy_brain/sfp_runtime \
  src/app/db/public_market_observations.py src/app/persistence/public_market_observations.py \
  --follow-imports=silent
```

Result: **149 passed** (77 accepted SFP detector tests, 23 SFP runtime/persistence
tests, 31 Nested Brain/shared regressions, 18 canonical strategy policy tests).
No skips. Ruff passed for changed Python files; mypy passed for the six new
source modules. The single warning is an existing FastAPI/httpx deprecation.

The new integration file covers both directions, approval/version binding,
forming/current vs historical confirmation, missing/stale/provisional/future
proof, immutable receipts, file-backed engine/session restart, tenant isolation,
failed reclaim/invalidation/expiry, replay convergence, bootstrap causality,
rolling history, migration upgrade/downgrade, governed Candidate creation,
existing daily-risk blocking, and refusal of execution calls. Ruff checks cover
all changed Python files. The complete backend suite was not run.

## Files changed

- `backend/src/app/api/routes/strategy_brain.py`
- `backend/src/app/db/migrations/versions/a2sfp002_public_market_receipts.py`
- `backend/src/app/db/models.py`
- `backend/src/app/db/public_market_observations.py`
- `backend/src/app/evidence_pipeline/watcher_port.py`
- `backend/src/app/interactive_agent/classify.py`
- `backend/src/app/persistence/public_market_observations.py`
- `backend/src/app/schemas/common.py`
- `backend/src/app/schemas/setup_ast.py`
- `backend/src/app/services/automated_paper_loop.py`
- `backend/src/app/services/canonical_strategy_evaluation.py`
- `backend/src/app/services/setup_ast_compiler.py`
- `backend/src/app/signal_fusion/evaluator.py`
- `backend/src/app/signal_fusion/strategy_evaluation_policy.py`
- `backend/src/app/strategy_brain/agent.py`
- `backend/src/app/strategy_brain/assembly.py`
- `backend/src/app/strategy_brain/records.py`
- `backend/src/app/strategy_brain/service.py`
- `backend/src/app/strategy_brain/sfp_runtime/__init__.py`
- `backend/src/app/strategy_brain/sfp_runtime/assembly.py`
- `backend/src/app/strategy_brain/sfp_runtime/assessment.py`
- `backend/src/app/strategy_brain/sfp_runtime/records.py`
- `backend/src/app/watcher/fusion_evaluation.py`
- `backend/tests/test_sfp_strategy_brain_runtime.py`
- `docs/sfp_full_vertical_002.md`
