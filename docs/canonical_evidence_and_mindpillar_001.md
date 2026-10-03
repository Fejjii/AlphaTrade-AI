# Canonical evidence diagnostics and MindPillar boundary

## Release scope and acceptance status

Base: `codex/release_consolidation_wave_003`, merged PR186 commit
`8673d8f69779ea516ca97456baea7b3064daf089`.
Branch: `codex/canonical_evidence_and_mindpillar_001`.

The confirmed code defect is diagnostic masking: the Watcher converted
`MarketContractError` failures from canonical assembly to
`canonical_evidence_unavailable`; its outer exception handler also exposed arbitrary
exception text. This change preserves the failed component and an allowlisted reason
through assembly, Watcher evaluation, and existing paper-quality counters. It also
bounds the scan-evidence cache to one scan.

**The underlying failure in the real staging scan has not been identified or
repaired. No staging deployment or acceptance scan was performed.** A fresh market
monitor does not establish historical trade coverage, CVD, derivative evidence or
manual resistance. The diagnostic masking repair must not be presented as proof
that staging market evidence is complete.

Staging scope supplied by the operator:

| Scope | Identifier |
| --- | --- |
| Organization | `ec61572a_7cdd_4074_b161_5b9f5731a465` |
| Approved AT068 version | `e8639afa_778f_4b4e_9270_dc0a5463b48a` |
| Compiled setup | `858026b7_1bac_45de_96e0_d5a67fd905e7` |

Render access is pending confirmation of the only listed workspace, `My Workspace`
(`tea-d7hn0fvavr4c73f62c70`). The connector requires confirmation before workspace
selection. This executor's managed HTTP policy does not allow `fapi.binance.com` or
`api.bybit.com`. Independent public HTTP probes were attempted with the supported
network capability; both failed at the managed proxy. No proxy bypass was attempted.

## Deterministic diagnostic contract

`EvidenceComponentDiagnosticV1` contains component, provider, symbol, optional
timeframe, status, finite reason code, freshness, source timestamp, evaluation time,
historical flag, failover-attempted flag, attempt (1–2), source family and instrument
identity. Providers and symbol syntax are allowlisted. At most 40 scalar diagnostic
records are retained for the latest assembly; no exception, tape or response payload
is retained in this collection.

Stages include instrument identity, 15m and 4h OHLCV, trigger/context, aggregate
trades, coverage proof, CVD, signed flow, freshness, current price, manual resistance,
OI, funding, 5m order flow, provider failover and the outer canonical contract.

Examples of Watcher reasons are `canonical_ohlcv_15m_rate_limited`,
`canonical_aggregate_trades_coverage_incomplete`, `canonical_open_interest_missing`
and `canonical_cvd_wrong_source`. Unknown exceptions produce
`canonical_contract_unexpected_error` with a static message. Invalid monitor results
produce `canonical_market_monitor_invalid_contract`.

Unavailable and source-switch diagnostics are logged as
`canonical_evidence_component`. Assembly exceptions preserve their original type;
the Watcher outcome carries their safe component diagnostics. Successful assembly
also carries diagnostics into the assessment outcome, including missing resistance.
Assessment state and Candidate authority remain controlled by the existing strategy
evaluator. Components not required by the selected policy are explicitly
`not_required`, and are not fetched as a new strategy requirement.

Freshness keeps the existing clocks: final historical OHLCV is marked historical
and reports its interval-end timestamp; its successful finality validation does not
prove a live quote. Trade/CVD freshness uses terminal exchange event time. Price,
OI and funding use their own source timestamps and existing freshness policies.
Historical evidence can remain valid while its wall-clock freshness is stale. A
suppressed historical quote remains unavailable in diagnostics; no quote is invented.

Coverage, identity, provenance, derivative validation, aggressor interpretation,
decimal arithmetic, reset policies and canonical hashes remain authoritative.
Diagnostics have no authority to satisfy any evidence role. A source switch discards
the partial first attempt and restarts under the secondary venue identity.

## Independent exchange verification

Use the read-only probe from `backend/`:

```sh
uv run python -m app.evidence_pipeline.probe --provider binance_usdm --output /tmp/binance-evidence.json
uv run python -m app.evidence_pipeline.probe --provider bybit_usdt_perpetual --output /tmp/bybit-evidence.json
```

The probe uses the existing exchange adapters and validators. It attempts independent
OHLCV, quote, OI, funding and 5m order-flow checks even when the canonical assembly
fails early. It records canonical coverage/CVD/signed-flow hashes when available,
with exact source metadata and individual freshness timestamps. It releases provider
symbol history afterward. It uses no database, Watcher lease, strategy activation,
Candidate or notification path. Its successful exit requires all requested market
components; `watcher_acceptance_verified` always remains false.

Results attempted on 2026-10-03 at approximately 13:41:20 UTC:

| Provider | Configured identity (not remotely verified) | Actual result |
| --- | --- | --- |
| Binance USD M | `binance:usdm_futures:perpetual:BTCUSDT`; `binance_usdm_futures_public`; `binance-usdm-perpetual/v1` | 15m/4h OHLCV and quote: `proxy_failure`; OI/funding/5m flow: `regional_failure` |
| Bybit USDT perpetual | `bybit:usdm_futures:perpetual:BTCUSDT`; `bybit_usdt_perpetual_public`; `bybit-usdt-perpetual/v1` | 15m/4h OHLCV and quote: `proxy_failure`; OI/funding/5m flow: `regional_failure` |

The derivative/flow acquisition contracts normalize transport failures into an
unavailable observation; their bounded diagnostics preserve the component and
regional-failure category. No remote market timestamp or fresh data was obtained;
freshness is `unknown`, proof maps are empty, and both probes exit 1. Trade coverage,
CVD and signed flow were not reached. These failures describe this executor's
network policy and must not be inferred to describe Render staging.

Deterministic mocked Binance evidence proves the complete supported market path,
including coverage hashes, CVD, signed flow, quote, OI, funding and 5m order flow.
Independent mocked Bybit tests prove supported OHLCV/quote/OI/funding/5m flow.
The controlled primary failure is an `httpx.MockTransport` 451 response; no real
connectivity is disrupted. Reassembly uses Bybit identity and final OHLCV, then
correctly rejects unproven historical aggregate-trade coverage.

Bybit's existing REST trade tail retains at most 15 minutes with bounded acquisition
and proof budgets. AT068's CVD baseline needs 32 preceding 15m bars plus its trigger
bar (8h15m). That tail cannot prove the full baseline on cold failover. This is a
reproduced support limit, not a diagnosis of the current staging failure. Supplying
short-window Bybit intelligence cannot substitute for the missing historical tape.

## MindPillar integration boundary

Repository configuration contains no existing MindPillar integration. Public
repository discovery did not identify official MindPillar API documentation, and
no official documentation URL or stable API contract could be verified. This is
an unverified API, not a claim that the provider has no API.

`SupplementalIntelligenceProvider` defines an optional consumer interface for:
cross-venue CVD, CVD divergence, OI context, funding context, order-flow context and
liquidation context. Observations carry provider time, source venue/market/instrument
provenance, freshness, availability, units and calculation method. CVD additionally
requires closed window bounds and explicit reset semantics; cross-venue CVD needs
at least two declared source venues. Consumers recheck freshness and requested
components. Collections and text fields are bounded.

`MindPillarLiveAdapter` makes no HTTP requests and returns `UNSUPPORTED` with
`api_contract_unverified` and no usable observations. The schema declares internal
consumer needs; it does not invent endpoints or provider payloads. It is not wired
into canonical assembly or strategy evidence. Its `supplemental` authority is a
literal and its objects cannot be validated as canonical public observations or
the canonical bundle. Binance and Bybit remain the canonical raw sources.

Before implementing a live adapter, obtain and verify all of:

1. Official provider-owned documentation URL, API base URL, version, stability
   policy, supported endpoints, and documented SDK (if any).
2. Authentication mechanism, scopes, sandbox, entitlement, quotas, rate limits,
   retry/backoff behavior and documented unavailable/error responses.
3. Exact request/response schemas and examples for each intelligence kind,
   numeric types, units and calculation methods.
4. Symbol and instrument mappings, venue coverage, spot/perpetual separation,
   contract multipliers, provenance and upstream source references.
5. Provider timestamps, event versus publication time, timezone, latency/freshness
   guarantees, revision behavior and stale/missing semantics.
6. CVD aggressor rules, quantity/quote units, aggregation, reset boundaries,
   windows and divergence calculation; flow and liquidation event definitions;
   OI sampling/units and funding settlement intervals.
7. History, pagination, retention and completeness guarantees, correction/gap
   handling, licensing and permitted data storage/use.
8. Recorded deterministic fixtures and contract tests for provenance, freshness,
   wrong instruments, availability, rate limits and failure behavior.

Any promotion of a specific MindPillar contract to canonical authority requires a
separate explicit architecture decision and independently verified guarantees.
Undocumented frontend endpoint scraping is excluded.

## Changed files

| File | Change |
| --- | --- |
| `backend/src/app/market_contracts/evidence_diagnostics.py` | Neutral bounded schema, safe reason mapping, stage recorder |
| `backend/src/app/evidence_pipeline/assembler.py` | Stage diagnostics, component-specific derivative/flow reasons |
| `backend/src/app/evidence_pipeline/watcher_port.py` | Exact failure propagation, one-scan cache, assessment diagnostics |
| `backend/src/app/evidence_pipeline/probe.py` | Independent read-only exchange verification CLI |
| `backend/src/app/evidence_pipeline/mindpillar.py` | Optional supplemental interface and unavailable live adapter |
| `backend/src/app/watcher/contracts.py` | Bounded diagnostics on evaluation outcomes |
| `backend/src/app/watcher/errors.py` | Safe diagnostic propagation through the existing error boundary |
| `backend/src/app/watcher/fusion_evaluation.py` | Safe unknown-error fallback and assessment diagnostics |
| `backend/src/app/paper_evaluation/metrics.py` | Preserve stale/provider counters for granular reasons |
| `backend/src/app/paper_evaluation/recorder.py` | Preserve stale data-quality classification |
| `backend/tests/test_canonical_component_diagnostics.py` | Component failures, redaction, assessment, bounded cache and failover |
| `backend/tests/test_independent_exchange_probe.py` | Complete Binance and independent supported Bybit checks |
| `backend/tests/test_mindpillar_boundary.py` | Unavailable adapter, provenance, freshness and source hierarchy |
| `backend/tests/test_paper_evaluation.py` | Granular reason measurement regression |
| `backend/tests/test_watcher_phase6_fusion_wiring.py` | Safe generic boundary reason regression |
| `docs/canonical_evidence_and_mindpillar_001.md` | Verification results, limits and API requirements |

The shared contract lives in `market_contracts` so importing Watcher contracts
does not initialize evidence services and persistence. Fresh-process disarmed
paper-worker boot tests verify that import boundary. Operational handoff/session
files stay local and are excluded from the PR.

## Validation and release decision

Focused acceptance: **527 passed**, including diagnostic/MindPillar/probe tests,
live evidence, aggregate-trade retrieval, OI/funding and flow provenance, Watcher
integration and tenant isolation, Bybit continuity, freshness clocks, paper memory,
paper quality metrics, configuration and deployment/exchange safety.
The no-strategy memory workload ran 40 five-market cycles with mocked GETs and
Telegram disarmed; growth after warmup was 2457.6 bytes per cycle and its existing
threshold assertions passed. Repeated evidence scans also prove old snapshots can
be collected and the scan cache remains at one entry.

Ruff and format checks pass. No-network post-deploy, canonical, live-market,
Watcher activation/rollback/health and controlled rollback self-checks pass.
Telegram preflight confirms network and send paths remain disabled. An initial
self-check needed `UV_CACHE_DIR=/workspace/.uv-cache` because the default uv cache
is outside writable roots. Initial TestClient runs stalled in the default network
sandbox; the supported per-command network capability resolves AnyIO wakeups.
Fresh-process worker boot and early-failure rerun: **77 passed, 2 skipped**.
The full-suite attempt exposed an import cycle introduced by the first placement
of the diagnostics module; moving it to the neutral market-contract layer repaired
that regression. A test clock fixture was also corrected. Both are covered by the
passing rerun.

The complete current backend corpus is **3824 cases: 3518 passed, 306 skipped**,
counting each case once across these completed runs:

| Run | Result |
| --- | --- |
| Full suite with four isolated workers, excluding the existing random-ID module | 3506 passed, 250 skipped (3756 collected), 435.49s |
| `test_agent_paper_execution_v4.py` separately | 6 passed, 56 skipped (62 collected), 0.38s |
| Six subsequently added OI/funding provenance cases, within the final diagnostic/intelligence rerun | 235 passed total, including all six additions, 18.91s |

The serial module generates a UUID in a parametrized test ID and cannot be collected
consistently by xdist; running that module separately preserves its full coverage.
Temporary local `pytest-xdist==3.8.0` installation did not change project dependencies
or the lockfile. Skips are conditional PostgreSQL/staging checks; no database or
staging credentials are configured in this executor. The main full run reports
240 warnings, principally dependency deprecations and existing test-fixture JWT
key lengths. Final collection confirms 3824 cases.

Actual commands, run from `backend/` with the supported per-command network
capability and the inherited managed proxy/CA configuration:

```sh
UV_CACHE_DIR=/workspace/.uv-cache PYTHONPATH=src .venv/bin/python /tmp/alphatrade-run-tests.py -n 4 --dist loadfile --ignore=tests/test_agent_paper_execution_v4.py --durations=12
UV_CACHE_DIR=/workspace/.uv-cache PYTHONPATH=src .venv/bin/python /tmp/alphatrade-run-tests.py tests/test_agent_paper_execution_v4.py
UV_CACHE_DIR=/workspace/.uv-cache PYTHONPATH=src .venv/bin/python /tmp/alphatrade-run-tests.py tests/test_canonical_component_diagnostics.py tests/test_market_intelligence_oi_funding.py tests/test_market_intelligence_cvd_orderflow.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

The local harness removes inherited application `Settings` environment bindings
so repository fixtures determine the safe test configuration. It preserves proxy,
CA, runtime authentication and outbound identity variables, and invokes
`python -m pytest -v` with the supplied arguments. Test commands exited 0. No
application environment or staging configuration was changed by the harness.

No Render deployment, flags, environment variables, strategy approval, leases,
manual levels or exchange connectivity were modified. Required invariants remain
`EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`, `EXCHANGE_MODE=paper_internal`,
with Telegram network disabled. This branch does not add an execution path.

**Keep the PR draft; staging acceptance is not established.** To complete release
verification, confirm the Render workspace and enable the two exchange hosts in
the managed policy. Inspect the scoped staging worker logs, stage this exact branch
under the existing paper gates, observe a BTCUSDT scan with the supplied AT068
identifiers, and fix the component cause shown by the new diagnostics. Capture the
source identities, timestamps and proof hashes from independent probes in the
staging network. A legitimately unavailable component must have an exact reason
and no Candidate; complete evidence must reach strategy assessment. Require CI
(including PostgreSQL checks) and a bounded staging memory run before merge.
