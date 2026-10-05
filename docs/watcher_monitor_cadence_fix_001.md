# Staging AT068 monitor cadence blocker

Base: `381b25ddd40aeb0df111ca68704bb05d740f07d4` on
`codex/release_consolidation_wave_003`.
Branch: `codex/watcher_monitor_cadence_fix_001`.

## Read-only staging evidence, 2026-10-04 UTC

Render's live paper worker deployment `dep-db12o5k9v7es73dljoag` runs the base
commit. Queries were scoped to organization
`ec61572a-7cdd-4074-b161-5b9f5731a465`, policy
`8ccdde72-e72b-5ac6-ab5c-209ac3628974`, and BTCUSDT.

| Attempt started | Finished | Outcome |
| --- | --- | --- |
| 10:38:40.234111 | 10:40:02.917518 | succeeded / no_setup |
| 10:45:12.857102 | 10:46:34.144614 | succeeded / watch |
| 11:00:11.421312 | 11:00:14.222690 | failed / canonical_evidence_unavailable |
| 11:00:32.225575 | 11:00:34.220983 | failed / canonical_evidence_unavailable |

The same failure continued through the 17:04 UTC observations. The persisted
error is `Canonical scan evidence is unavailable.` Health is `degraded` with a
current heartbeat. Logs show zero Candidates, paper-only execution and an inactive
kill switch. The monitor retained one terminal trade before the 11:00 attempt and
zero trades after it; its OHLCV count remained 130. Recent failed scans contain no
assembler component diagnostics because the monitor gate refuses first.

Both `manual_chart_levels` and `manual_level_revisions` contain **zero rows** for
this organization. Missing manual resistance diagnostics also occur during the
successful 10:38 and 10:45 evaluations. This input absence does not cause the
recurring monitor-gate failure.

## Root cause and minimal correction

`WatcherPaperRuntime` replays a successful evaluation until the next 15m bar.
Those replay cycles do not call the evidence port's `load`, which was the only
tick of its persistent live monitor. `SymbolMonitorRuntime._window` bounds trade
lookback to ten minutes while its cursor still requires continuity from the old
terminal trade. A fifteen-minute interval clips out the required boundary. The
cursor detects a sequence gap and enters reconnect; retries still clip the
watermark and cannot prove recovery. The gate correctly refuses the unhealthy
stream, but the worker's scheduling integration created the missing interval.

A deterministic regression using available, contiguous test trades reproduces
`watch`, intervening successful replays, then `canonical_evidence_unavailable`
at the next 15m evaluation on the unmodified release. A separate direct monitor
reproduction returns `GapDetectedError` then `CursorRecoveryError`. The worker's
private monitor snapshot is not exposed in staging logs; its detailed gap state
was reconstructed from the release path and these reproductions.

The correction polls the existing live monitor on each eligible first-slice
worker cycle before evaluation idempotency can replay. It respects the monitor's
poll/backoff settings and existing ten-minute bound. The canonical gate still
forces a fresh snapshot when an evaluation runs. Replay sources and the separate
OHLCV strategy families do not gain this polling. Strategy evaluation, Candidate
authority, source identity, coverage checks and trading safety are unchanged.

## Missing resistance and operational next step

An operator obtains a real chart resistance through the tenant's Manual Levels
page or authenticated `POST /manual-levels`: BTCUSDT, Binance/Binance USD-M,
resistance, 4h, enabled, with an actual observed price or zone. The service appends
an immutable revision and Watcher loads it by tenant and symbol. Eligibility also
requires its effective time to precede the trigger and the evaluator's existing
market identity and distance rules. Nothing in this fix supplies a resistance.

Until eligible resistance exists, healthy acquisition permits a legitimate
`watch` / `no_setup` assessment with zero Candidates. It does not imply that a
setup should exist. Review and deploy the fix through the normal approval path,
then observe two successive real 15m evaluations. This task did not merge,
deploy, change staging data, alter safety flags or claim repaired staging health.

## Focused validation

The added cadence regression fails on the unmodified release. Fixed-source
regressions also cover a genuine sequence gap, provider outage, replay isolation,
bounded terminal-trade retention, the kill switch, and unchanged Nested/SFP scope.
**91 distinct focused tests pass:** 88 passed in the four-module run; three added
scope tests initially had a missing fixture argument and pass in their targeted
rerun after that test-only correction. No production change followed the
four-module run. Ruff, format and whitespace checks pass. One existing
Starlette TestClient deprecation warning remains.

The test subprocess removes inherited application Settings variables while
preserving managed proxy, trust and authentication context. The network-enabled
execution sandbox is needed for TestClient's local event-loop IPC; without it
the existing HTTP test stalls entering its portal. All market source data in
these tests is explicitly mocked. The test selectors/checks, from `backend/`:

```sh
.venv/bin/pytest tests/test_watcher_paper_runtime.py tests/test_live_market_monitor.py tests/test_watcher_source_gate.py tests/test_watcher_bybit_continuity.py --show-capture=no
.venv/bin/pytest tests/test_watcher_paper_runtime.py::test_monitor_upkeep_respects_existing_safety_and_strategy_gates --show-capture=no
.venv/bin/ruff check src/app/workers/watcher_market.py src/app/workers/watcher_paper.py tests/test_watcher_paper_runtime.py
.venv/bin/ruff format --check src/app/workers/watcher_market.py src/app/workers/watcher_paper.py tests/test_watcher_paper_runtime.py
git diff --check
```
