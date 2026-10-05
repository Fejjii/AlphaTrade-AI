# Stale setup lifetime pin recovery

Base: `codex/release_consolidation_wave_003` at
`7e39996778378d3bdf2a86d898c007ed8ba0e7a7`.
Branch: `codex/setup_lifetime_stale_pin_fix_001`.

## Exact blocker and corrected behavior

The operator verified that the AT068 BTCUSDT pin for organization
`ec61572a_7cdd_4074_b161_5b9f5731a465`, strategy version
`e8639afa_778f_4b4e_9270_dc0a5463b48a`, compiled setup
`858026b7_1bac_45de_96e0_d5a67fd905e7`, still had
`trigger_end=2026-09-26T10:15:00Z` and `expired=false` on October 3.
The missing historical trigger produced `trigger_context/forming_candle` before
current canonical evidence could be evaluated.

Before this change both pin stores also returned a trigger from an already
expired pin. After this change `active_trigger_end` returns `None` for expired
pins, while `get` still exposes the tombstone. Existing convergence rules continue
to reject attempts to reactivate the same or an older trigger.

When the requested pin is missing from validated closed 15m evidence, recovery
requires the latest final interval end to be at or after:

`trigger_end + interval_timedelta(Timeframe.M15) * FIRST_SLICE_EXPIRY_BARS`.

The authorized limit remains two 15m bars. One microsecond before the boundary
does not prove expiry; the boundary itself and later closed intervals do. A future
series endpoint cannot prove expiry at an earlier evaluation time. Pins present
in the series retain the existing subsequent-final-bar expiry behavior.

A missing pin past that boundary is expired in its own semantic scope, recorded
as `trigger_context/stale`, and trigger selection retries once over the already
validated closed series without the old pin. An explicit historical request cannot
expire a different current pin. Missing pins inside the lifetime, unavailable
OHLCV, and genuinely current forming candles still fail closed. All current
coverage, CVD, flow, freshness, provenance and assessment checks still run.

The SQL store flushes expiry in the caller's existing unit of work; the caller
continues to own commit/rollback. If a subsequent evidence component is unavailable,
committing the failed scan preserves expiry and the following scan is unpinned.
When current evidence completes, normal existing pin convergence can advance the
mutable cursor to its independently verified later trigger.

## History and isolation

Recovery never calls `clear` or deletes a pin. Before a retired cursor can advance,
the SQL store appends an expiry record to the existing `audit_logs` table with the
original trigger timestamp, bar hash, lineage hash, compiled identity and expired
state. This also preserves legacy already-expired pins when a later trigger replaces
them. Row locks serialize mutation, and repeated expiry/advancement does not append
duplicate records for the same retired lineage. No migration is required.

Prior canonical evidence and hashes are not rewritten. Recovered current evidence
has the same canonical hash as an independent normal unpinned scan. The repair
does not authorize a Candidate; strategy assessment and persistence gates remain
responsible for that decision. Tenant and strategy-version keys remain isolated.

## Changed files

- `backend/src/app/evidence_pipeline/setup_lifetime.py`
- `backend/src/app/evidence_pipeline/assembler.py`
- `backend/src/app/persistence/setup_lifetime.py`
- `backend/tests/test_setup_lifetime_stale_pin.py`
- `backend/tests/test_setup_lifetime_postgres.py`
- `docs/setup_lifetime_stale_pin_fix_001.md`

## Validation and staging suitability

Focused suite: **262 passed, zero skips**, including memory and real disposable
PostgreSQL lifetime tests, canonical evidence/hash/expiry tests, PR187 component
diagnostics, Watcher runtime/integration/tenant/ownership/freshness tests, paper
evaluation, controlled paper activation and its PostgreSQL rehearsal, and Watcher
paper activation. Initial lifetime-first run: 34 passed. Final strengthened
Candidate persistence check: 2 passed. Fresh-process disarmed worker boot: 1 passed.
Ruff passes; format check reports 1069
formatted backend files. The only focused-suite warning is an existing TestClient
dependency deprecation.

The local test harness provisions an owned temporary PostgreSQL instance with
database `alphatrade_test`, sets only disposable test DSNs, and removes inherited
application settings from the test subprocess while preserving managed proxy,
CA and runtime authorization configuration. Tests run sequentially because their
existing factories reset the disposable schema. Commands and result logs are
retained locally under `/tmp/alphatrade-stale-pin-*`.

The focused command was run from `backend/` through
`PYTHONPATH=src .venv/bin/python /tmp/alphatrade-stale-pin-tests.py`, passing these
test modules in order:

```text
tests/test_setup_lifetime_stale_pin.py
tests/test_setup_lifetime_postgres.py
tests/test_live_hash_stability_and_expiry.py
tests/test_intelligence_p1_remediation.py
tests/test_live_evidence_pipeline.py
tests/test_canonical_evidence_http.py
tests/test_canonical_component_diagnostics.py
tests/test_watcher_paper_runtime.py
tests/test_watcher_stack_integration.py
tests/test_watcher_phase6_fusion_wiring.py
tests/test_watcher_tenant_watchlist.py
tests/test_watcher_freshness_clocks.py
tests/test_watcher_worker_ownership.py
tests/test_paper_evaluation.py
tests/test_controlled_paper_activation.py
tests/test_controlled_paper_activation_rehearsal.py
tests/test_watcher_paper_activation.py
```

Each completed run exited 0. The added Candidate-persistence assertion was verified
with a targeted rerun of `test_recovery_alone_does_not_mint_candidate` for both
memory and PostgreSQL. Checks were `.venv/bin/ruff check .` and
`.venv/bin/ruff format --check .`, also exiting 0.

The full backend suite was intentionally not run; GitHub CI supplies the broad
repository gate. The branch is suitable for paper-only staging validation once CI
is green. Actual Render acceptance is unverified because deployment is explicitly
out of scope. No merge, deployment, vendor configuration or safety flag changes
are part of this PR. Telegram, TradingView, BloFin, MindPillar and real trading
remain untouched.
