# AlphaTrade SFP replay adapter 001

Repository: `Fejjii/AlphaTrade-AI`.
Branch: `codex/sfp_replay_adapter_001`.
Exact parent: `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092` (PR176).
Draft review target: `codex/release_consolidation_wave_002`.

SFP research now runs through PR173's existing deterministic replay jobs, frozen
datasets/configuration, worker/background execution, results, cancellation,
verification, comparisons, tenant/RBAC fences and audit authority. Detection,
structural proof/knowability, setup lifecycle and quality components come from the
canonical SFP modules consolidated in PR176.

Explicit canonical historical candle proofs preserve actual receipt clocks.
Historical rows alone cannot establish SFP knowability. Missing, forming, stale
and late proofs remain visible evidence gaps; later evidence cannot repair an
earlier gap retrospectively. HTF context, volume, native CVD/five-minute flow,
OI/funding, missing/stale evidence, target space and every canonical lifecycle
event remain observable. Window samples and research buckets expose symbol,
timeframe, direction, level type, exact version, measured-component coverage and
directional-efficiency bands.

**No SFP execution plan is authorized.** Trade metrics are null; trade lists are
empty; entry, stop, execution targets, R and PnL are not inferred. Structurally
confirmed setups do not imply Candidate or ActionEligibility approval. RiskEngine
is not invoked without an authorized plan and sizing. No Candidates, paper
trades, journals, operational Brain episodes or account/risk state are written.
Available target space is descriptive structure, not a trade target. Existing
Nested simulation/risk behavior continues unchanged.

Baseline/proposed comparisons require identical candle/evidence inputs and
receipt clocks. Both immutable versions' lifecycle counts and buckets are
returned. SFP net-PnL difference stays null and `improvement_claim=false`.
Insufficient samples and missing evidence remain explicit.

Frozen hashes bind versions, parameters, adapter, every evidence clock, freshness,
dataset, trace, counts and buckets. Verification checks recomputed immutable
strategy content and stored output identity. Restart tests use a fresh Session,
database reload and altered Decimal arithmetic contexts. An independent replay
against the exact base reproduced the unchanged Nested result hash:
`b31440f48ac0382386a34610fb427add41a253d94dd377daa4a3ac4447555761`.

## Validation

**462 distinct focused backend cases passed, zero skipped.** The combined suite
passed 459 cases. Final replay checks passed 54 cases (27 SFP, 27 Nested), including
three additional future-evidence, API and malformed-result tamper cases.
Relevant commands from `backend/`:

```sh
.venv/bin/pytest tests/test_sfp_replay_adapter_001.py tests/test_strategy_replay_001.py tests/test_sfp_detector.py tests/test_market_intelligence_oi_funding.py tests/test_market_intelligence_cvd_orderflow.py tests/test_at034_engine.py tests/test_at034_integration.py tests/test_at034_api.py tests/test_phase3_strategy_immutability.py tests/test_deployment_safety.py -q
.venv/bin/pytest tests/test_sfp_replay_adapter_001.py tests/test_strategy_replay_001.py -q
```

Coverage includes both directions, exact canonical event projection, future
pivots/context/optional evidence, delayed receipts, required-proof gaps, native
evidence freshness, failed reclaims, invalidations, expiry, version forks, hash
tampering, restarts, cancellation, idempotency, background execution, null metrics,
empty persisted trade/Candidate/journal tables and tenant/Trader API access.

Scoped Ruff lint/format passed for the nine affected Python files. Targeted mypy
passed for the eight affected source modules. **Six frontend cases passed** for
the backtest detail page, including completed/cancelled SFP research with null
metrics; full frontend `npm run typecheck` passed. Diff whitespace checks passed.
TestClient requires the execution tool's network-enabled sandbox for its local
AnyIO wakeup sockets; providers remain mocked and no venue is contacted.

No full repository suite or PostgreSQL-only runtime persistence suite was run.
No migration/dependency/lockfile change is present; Alembic remains `a3release002`.
No live trading, market acquisition, deployment, worker/Telegram activation,
strategy promotion, main merge or CI wait occurred.

## Research limits and review entry points

Trigger detector histories are independent across windows and required-evidence
gaps. Expiries/invalidation counts are observed canonical events; no missing price
path is interpolated. Optional native evidence is descriptive and leaves canonical
SFP confirmation/policy unchanged. Quality buckets count measured components, not
confidence or performance; efficiency bands are not a validated regime classifier.
The minimum sample threshold counts unique observed SFP episodes. Meeting it is
descriptive only. This task supplies no real historical performance experiment.

Adapter: `backend/src/app/services/sfp_replay_adapter.py`.
Shared engine/service/contracts: existing `strategy_replay_*` modules.
Regression coverage: `backend/tests/test_sfp_replay_adapter_001.py`.
API, evidence contract and count semantics: `docs/sfp_replay_adapter_001.md`.
Prior release provenance remains in `docs/release_consolidation_wave_002.md`.

Delivery is a pushed draft for review on the branch above; the task's final
handoff links its PR and commit. Leave CI to run; STOP after handoff.
