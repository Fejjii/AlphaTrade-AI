# Runtime stability and CI memory 001

Base: PR176 head `5f4f0a467ce8f68f9c7a82d3b32307d559a9f092`.
Branch: `codex/runtime_stability_ci_memory_001`.

## SFP root cause and correction

This is a production clock propagation defect, not a stale market fixture.
The exact base's two daily-risk SFP cases fail on October 2, 2026. Both pass
on that same unchanged base when **only** daily risk accounting's wall clock
is frozen to October 1, 2026 (the fixture's injected evaluation day).

The actual failed report has `confirmed_setup`, a canonical Candidate, and
`eligibility_state=eligible`, followed by `sfp_execution_plan_not_authorized`.
It does not fail before Candidate creation in this reproduction. The Candidate
and quote acquisition work; daily risk selects the wrong day.

`AutomatedPaperLoop._eligibility_command` already receives `now` from Watcher's
`BoundEvaluationClock`. It constructed `DailyRiskAccounting` without that clock.
`resolve_day` used `datetime.now(UTC)` and, on its fallback, `date.today()`.
Consequently it synchronized an unlocked row for CI's current day, ignoring
the authoritative locked row for the injected evaluation day. The release
validation ran on the synthetic date and masked this defect.

`DailyRiskAccounting` now accepts an optional clock. Both eligibility and
equity reads in the automated paper loop supply their canonical evaluation
time. The user's timezone still defines the daily boundary; the UTC fallback
uses the same injected instant. Existing callers without a clock keep the
UTC wall-clock default. Lock preservation and enforcement are unchanged.

The original SFP assertions remain. The tests additionally require exactly
one Candidate and one locked daily-risk row for the injected date. They cover
both directions on leap day, the release date, a midnight crossing, and a
future year. Independent clock tests cover Berlin/New York date boundaries,
the Berlin DST transition, and invalid timezone fallback. The older automated
paper-loop risk fixture now derives its locked day from its existing
`EVALUATED_AT`, rather than wall time.

OHLCV `recorded_at` still represents recording wall time. SFP availability uses
`max(observed_at, receive_time)`; semantic hashes exclude recording/transport
clocks. It is not the cause of these failures and was not changed. Freshness
tolerances, market facts, receipt preservation and risk reasons were not changed.

## Final PR184 Nested fixture correction

The remaining CI failure was a stale test fixture. `nested_runtime_world`
still seeded `DailyRiskState.day` from `datetime.now(UTC).date()`, although
its Watcher evaluates at the existing synthetic `now` derived from the last
candle. With canonical daily-risk clock propagation, that wall-clock row
does not lock the fixture's evaluation day. The unchanged test reproduced
`paper_loop_reason=open_journal` on October 2, 2026.

The fixture now uses `day=now.date()`. Production risk semantics and all test
expectations are unchanged: the confirmed Nested setup creates its canonical
Candidate, the existing lock records `BLOCKED_BY_RISK` and `blocked_daily_loss`,
and the paper loop is blocked with `risk_block`. No TradePlan, fill or Journal
trade is produced.

Final focused validation: **21 passed, zero skipped** on disposable PostgreSQL
17.11: the Nested daily-risk test, all eight SFP daily-risk clock matrix cases,
all six Automated Paper Loop tests (including daily-risk and kill-switch
blocking), and six daily-risk clock cases. Ruff lint/format and whitespace
checks pass. No full repository suite was run.

```sh
.venv/bin/pytest tests/test_strategy_brain_nested.py::test_existing_daily_risk_lock_blocks_nested_paper_execution tests/test_sfp_strategy_brain_runtime.py::test_existing_daily_risk_lock_is_authoritative_for_sfp tests/test_automated_paper_loop.py tests/test_daily_risk_clock.py
```

## Memory findings

The Render restart is evidence of exceeding that container's limit. The CI
RSS figures, `811757568` current and `813613056` peak bytes, are evidence about
the backend test process, which imports the application and many fixtures.
They do not establish worker steady-state RSS or a retained-growth leak.
No supplied staging time series or heap profile identifies the retained owner.

The exact release already includes the September 28 remediation
`e38e58cd73b9d6e6e1dd15280cd1bf9bdc0f2ad9` (AT-ADR-073), plus five-market
history budgeting and later Bybit continuity bounds. This investigation found
no concrete additional unbounded runtime owner requiring a retention fix.
The memory code changes add opt-in instrumentation, not altered evidence
retention, allocation limits, execution behavior, or a tier increase.

| Owner/path inspected | Lifetime and bound on the release base |
| --- | --- |
| Watcher symbol history | `SymbolHistoryBudget` permits one in-flight history; completed deque has at most five symbols. Both strategy scans and no-strategy probes release in `finally`, including failures. |
| Symbol market composition | `SymbolMarketFactory` keeps at most five sources/catalogs/monitors. Replacing a symbol closes evicted clients and removes read counters. Discovery caches at most ten symbol/venue verdicts and one latest Binance contract payload. |
| Binance print history | Streaming reduction produces `ReleasedTradeTape`, preserving coverage, hashes and sums with `trades=[]`. Raw cache admits at most 4096 rows per entry by default, at most eight entries; reduced caches also have an entry/TTL bound. Symbol cleanup drops raw/reduced entries and idle key locks. |
| Bybit prints and execution ranks | At most three lineage proofs per source; each has a ten-page/15-minute bulk bound, reduced by cleanup to one 1000-print page. Rank/signature ledgers are pruned against retained proofs and the latest provider page. Evicted evidence fails closed. |
| Monitor trades/CVD | Keeps the latest window's scalar CVD/coverage facts and the final timestamp bucket for overlap continuity; reconnect clears prior state. It retains latest M15/H4 series, not successive series. A same-timestamp bucket has a time/response bound rather than a fixed print count. |
| Five-minute flow and bounded CVD | Five-minute flow and ten-minute CVD reuse verified print reduction. Their bundles are local to the scan/read. Venue changes discard earlier facts and reset the bounded CVD baseline. |
| OI/funding | Provider reads produce the current typed observations, with bounded response requests. Assembly holds the current tuple; no append-only OI/funding runtime history was found. |
| Evidence bundles | `AssemblingWatcherScanEvidence` is constructed per scan. Its `_load_cache` and `_last_assembly` live for evaluation/persist/continuation and then lose the runtime owner. The last report contains semantic references, assessment and Candidate, not a raw trade tape. |
| Candidate/Strategy Brain | Canonical Candidates and Brain events/receipts persist in SQL. Historical receipt reads have an explicit horizon and row limit. Worker status retains only the latest bounded cycle's reports. Fencing-token maps have a capacity derived from lease/poll/scopes. Test in-memory stores are not production history authority. |
| Sessions and identity maps | Scan and tenant-publication sessions close per cycle; canonical adapters close their own sessions in `finally`. Thread-local session/fence binds restore prior values. Staging activation stores a runtime and a separate bounded probe monitor, not a long-lived ORM Session. |
| Telegram | Durable PostgreSQL outbox/cursor; delivery reads ten rows and polling twenty updates per pass. Attempts/batches are local. Notification hooks persist through short sessions; no in-process append-only delivery queue was found. |
| Replay/global caches | Production provider selection does not build replay fixtures when using real sources. Replay mode intentionally retains fixture trades. Shared Binance evidence pools are keyed by process configuration; static worker configuration gives one key. Different test configurations can retain more pools in the test process. Settings use a bounded `lru_cache`; request metrics are scalar counters. |
| Threads/allocator | Supervisor owns one Watcher and one Telegram thread and prevents duplicate starts. HTTP heartbeat helpers signal stop and join in `finally`. Supervisor already calls GC and glibc `malloc_trim` after each component cycle. RSS can retain Python/native allocator arenas despite no live-object growth. |

Remaining plausible contributors to a staging limit breach are startup imports,
one high-volume scan's transient allocations, the monitor's at-most-ten-minute
catch-up request, multiple simultaneous component allocations, and allocator
arenas. These are hypotheses to measure, not proven leaks. The staging activation
probe monitor is separate from the five market compositions and must be included
when profiling the whole process.

`render.yaml` configures `alphatrade-paper-worker-staging` on `plan: starter`.
That tier is ordinarily 512 MiB. The actual Render service tier/limit is not
verified here; Blueprint configuration need not match an existing service.
Use the container limit and Render dashboard for the capacity decision.

## Instrumentation and separately authorized staging acceptance

`PAPER_WORKER_MEMORY_DIAGNOSTICS_ENABLED=true` enables diagnostics only. It does
not arm Watcher, Telegram, or execution. It defaults false and no deployment or
staging setting has been changed by this task.

The new records are:

- `paper_worker_memory_startup`: process RSS/high-water mark after runtime
  construction, thread count, container memory usage and cgroup limit.
- `paper_worker_memory_cycle`: component/cycle number, RSS at entry, sampled
  peak, RSS before cleanup, RSS after existing GC/allocator cleanup, and rolling
  endpoint growth per cycle/hour (at most 32 numerical samples per component).
- `watcher_paper_memory_structures`: history/fence/report/Candidate/evidence
  reference counts; closed cycle-session identity-map/new/dirty counts; provider
  compositions, monitor trades/candles, raw/reduced cache entries/rows/locks,
  Bybit lineage/proven-print/rank counts.

Peak sampling uses a temporary 250 ms sampler, stopped and joined before cleanup
on success and failure. The sampled peak is a **lower bound**: short spikes can
be missed. `rss_peak_bytes` is a process-lifetime high-water mark, not that
cycle's peak. RSS and cgroup usage include overlapping Telegram/probe/other
component work; component labels are timing boundaries, not ownership accounting.
Do not interpret a single positive endpoint slope as a leak.

In a separately approved staging verification window:

1. Record the image/commit, real Render tier/cgroup limit, process count,
   five-market configuration, poll interval and approved strategy scopes.
   Preserve paper-only authority, Risk and ActionEligibility. Keep Telegram
   network disarmed throughout this procedure.
2. Enable only the diagnostic setting in that approved window and capture the
   startup record before the first cycle. Separate startup and warmed baseline.
   Use Render's container memory graph and OOM/restart events alongside logs.
3. Capture one actual scan's sampled peak, process high-water mark and immediate
   cleanup RSS. Correlate symbol/scope scan logs with the cycle. Capture quiet
   no-strategy monitoring separately from active strategy/CVD/flow scans; include
   a busy symbol, a provider error and a reconnect/catch-up cycle. Use genuine
   provider evidence without widening coverage or freshness gates.
4. Collect at least 100 cycles and then a 6–24 hour observation at representative
   load. Discard the first ten cycles when assessing growth. Fit post-cleanup RSS
   versus elapsed time and compare median RSS in successive windows. Compare
   provider/report/fence counts and thread counts with the same windows. Keep
   the raw time series externally; the in-process diagnostic retains only 32
   samples. Record minimum/median/95th percentile cleanup RSS and peak RSS.
5. Healthy acceptance requires bounded owner counts, no extra worker/sampler/
   heartbeat threads retained between cycles, and warmed cleanup RSS stabilizing
   across successive windows. Investigate persistent positive growth before
   increasing the tier. A rising lifetime peak alone does not prove retention.
6. If counts grow, profile that owner. If RSS rises with stable counts, use a
   separately approved short `tracemalloc` profile started before runtime
   construction: compare snapshots after warm-up and after repeated cleanup,
   grouped by traceback. Inspect assembler/flow/receipt/report/session/global
   pool allocations first. `tracemalloc` misses native allocations and adds
   overhead; compare RSS separately and avoid forcing it on the constrained
   worker during an OOM incident. External profiling must include the activation
   probe monitor, database driver, HTTP clients and both component threads.
7. Increase the tier only if measured normal-load warmed RSS or genuine transient
   peaks leave inadequate headroom under the **actual** limit after correcting
   any identified growth. Reserve explicit operational headroom (for example
   20–30%) and repeat the same workload after a separately approved tier change.
   An 812 MB backend pytest process is not sufficient evidence for that change.

## Local validation evidence

No full repository suite was run. PostgreSQL 17.11 was initialized under `/tmp`
on loopback port 55432; only disposable task databases were reset by fixtures.
Provider traffic in tests uses scripted sources or mocked GET transports;
Telegram network, live trading and deployment remain disabled.

**282 distinct focused cases passed, zero skipped**, counting each case's latest
result once. The repeated eight-case SFP matrices are included in that total
once. The stopped broader invocation is not claimed as a completed suite.

Representative focused commands (from `backend`, with `PHASE1_POSTGRES_URL`
pointing to a disposable task database):

```sh
.venv/bin/pytest tests/test_sfp_strategy_brain_runtime.py::test_existing_daily_risk_lock_is_authoritative_for_sfp
.venv/bin/pytest tests/test_daily_risk_clock.py tests/test_automated_paper_loop.py tests/test_watcher_freshness_clocks.py
.venv/bin/pytest tests/test_process_memory.py tests/test_paper_worker_memory.py tests/test_watcher_five_symbol_watchlist.py
.venv/bin/pytest tests/test_worker_memory_diagnostics.py tests/test_watcher_bybit_continuity.py
.venv/bin/pytest tests/test_watcher_tenant_watchlist.py::test_repeated_worker_cycles_release_history_and_keep_compositions_bounded
```

- Exact base: two original SFP risk-lock cases fail on October 2; both pass
  with risk accounting wall time frozen to October 1.
- Fixed SFP matrix: eight cases pass, repeated in focused risk validation and
  with risk wall time forced to December 31, 2035. Canonical injected dates
  still select the locked row and record `BLOCKED_BY_RISK`/`blocked_daily_loss`,
  with no plan or fill.
- Focused risk/SFP/freshness group: 85 passed, zero skipped.
- Focused Watcher runtime/orchestration/fusion and supervisor group: 96 passed,
  zero skipped. Memory/history-budget group: 36 passed. Tenant lifecycle subset:
  25 passed. A broader Watcher module run stalled at its API integration case
  and was stopped; its focused lifecycle subset completed independently.
- Forty real Watcher no-strategy cycles over five symbols, SQL watchlist/status
  persistence and mocked provider GETs: inspected structure bounds held.
  Final focused run: warmed cleanup RSS moved from 225472512 to 225583104
  bytes over the last 30 cycles (about 3.7 KB/cycle). This small change does not
  establish a long-term plateau or staging strategy-scan capacity.
- Isolated reducer stress: eight cycles × 25000 prints, final RSS from 110923776 to
  110940160 bytes, growth 16384 bytes (the earlier run grew 24576 bytes).
  Released and retained evidence hashes/
  CVD/flow equivalence, cache admission bounds and Bybit cleanup/fail-closed
  coverage are covered by focused tests.
- Separate Python process importing the paper worker with disarmed callbacks:
  startup RSS 103346176 bytes. This excludes live provider clients, strategy
  scans and staging preflight; it is not a staging baseline prediction.
- Diagnostic lifecycle/cgroup tests and Bybit diagnostic bounds: 39 passed.
- Ruff checks/formatting pass. Scoped mypy reports the same 16 pre-existing
  diagnostics in three existing modules as the exact base; the new diagnostics
  and daily-risk clock module add none. Full dependency typing was not a release
  acceptance claim.

Remaining staging work is the measured acceptance window above. Neither a new
leak fix nor a Render tier change is justified by the current repository/local
evidence alone.
