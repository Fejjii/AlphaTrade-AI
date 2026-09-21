# AT-072 / PR #121 — Independent adversarial review

**Reviewer:** Cursor Cloud agent (independent of the integration author)  
**Scope:** Review only. No implementation, merge, deploy, or Watcher activation.  
**Subject:** Draft PR [#121](https://github.com/Fejjii/AlphaTrade-AI/pull/121)  
**HEAD reviewed:** `69df737e211133786122ace76fec31eed1b237a0`  
**Branch reviewed:** `cursor/watcher_integration-b74b`  
**Base:** `main@b4244f0`  
**Review branch:** `cursor/watcher_final_review`  
**Date (UTC):** 2026-09-21

---

## FINAL VERDICT

# REMEDIATION REQUIRED

Do **not** merge PR #121.

Watcher, Telegram, and live trading remain disabled on this HEAD. That is necessary, not sufficient. The mint-authority fail-closed story largely holds in production-shaped code, but the PR’s merge claims about **freshness-clock honesty**, **monitoring projection of the mint pipeline**, and **single-worker fencing** do not survive adversarial review. Several tests that the PR cites as proving the pipeline are vacuous or fabricated.

This is not a finding that stale, wrong-tenant, expired, or in-memory policy can mint a Candidate on the wired production factory. Those refusals held. It is a finding that PR #121 is **not ready to merge as an honest, fenced, operator-truthful Watcher stack**.

---

## Review method

1. Treated AT-ADR-048…051 and the PR body as hypotheses, not facts.
2. Read the production wiring: monitor gate, assembler port, paper worker, orchestrator, fusion evaluation, Candidate lifecycle, Postgres fence, monitoring projection, frontend cards, deployment safety.
3. Attempted to falsify: approved strategy → live evidence → Watcher → `evaluate_canonical_strategy` → `CONFIRMED_SETUP` → persisted Candidate → monitoring.
4. Attempted to mint from stale evidence, replay-as-live, wrong tenant, wrong lineage, expired setup, and in-memory policy.
5. Re-ran focused pytest locally on this HEAD (129 passed). Did not re-run full backend, frontend, or E2E; GitHub Actions run [35631036137](https://github.com/Fejjii/AlphaTrade-AI/actions/runs/35631036137) is SUCCESS on the exact HEAD.

---

## Required remediations (merge-blocking)

### R1. Bind monitoring freshness clocks to the assembler clocks they claim to be

**Invariant claimed (AT-ADR-051 / PR body):** current quote, trade stream, closed-candle finality, historical evidence validity, and setup lifetime stay separate.

**Falsified.** `WatcherMonitoringService._market_freshness` maps operator clocks off the **monitor health DTO**, not `EvidenceClockReport`:

| Operator field | Actual binding | Assembler clock |
|---|---|---|
| `quote_fresh` | quote freshness ∈ {fresh, aging} | `usable_as_current_market_price` |
| `trade_stream_fresh` | reconnect continuous/recovered **and** gap none | stream FRESH/AGING (or coverage hash when not in the live window) |
| `closed_candle_final` | `ohlcv.available` | `trigger.finality is Finality.FINAL` |
| `historical_evidence_valid` | trade-stream `coverage.completeness == complete` | `closed_evidence_valid` / `historical_closed_evidence` |
| `stale_after_minutes` | always `market_watcher_stale_data_max_age_minutes` (**60**) | 10s last-trade policy |

`ohlcv.available` is true when **either** 15m **or** 4h series exists, including `PARTIAL` (`runtime.py` `_ohlcv_health`). The UI then prints “candle final” / “historical valid” (`WatcherMonitoringCard.tsx` freshness clocks). That is false labeling, and it ships on `GET /market-watcher/monitoring` even while Watcher is STOPPED, because `main.py` always constructs the monitor and monitoring depends on it.

**Fix:** project `quote_fresh`, `trade_stream_fresh`, `closed_candle_final`, and `historical_evidence_valid` from assembler `EvidenceClockReport` (or equivalent finality/usability fields). Do not publish a 60-minute stale threshold next to the 10s quote policy unless it is explicitly named as the **legacy scanner** threshold. Add tests that a PARTIAL/forming OHLCV snapshot cannot render as `closed_candle_final=true`.

### R2. Stop claiming an end-to-end mint → monitoring proof that the tests do not provide

**Invariant claimed (PR body):** integration tests prove approved strategy → gated evidence → Watcher scan → canonical SetupAssessment → `CONFIRMED_SETUP` → persisted Candidate → monitoring API/UI.

**Falsified.**

1. `_gated_world_factory` applies the real monitor gate, then loads an `EvaluatorWorld` fixture via `_WorldEvidencePort`. It never calls `FirstSliceEvidenceAssembler`. `_WorldEvidencePort` **claims** `ExecutablePolicyAuthority.PERSISTED_APPROVED_COMPILED` while injecting fixture evidence (`test_watcher_paper_runtime.py`). That bypasses the in-memory bind guard that exists specifically to prevent this.
2. Candidate persist in that suite uses `InMemoryCandidateRepository` with **no** Postgres `persistence_fence`.
3. `test_monitoring_projects_integrated_worker_candidate_and_replay_honesty` **INSERT**s `WatcherWorkerLeaseRow`, heartbeat, lineage, and attempt rows by hand after an in-memory cycle. It does not read what the worker wrote.
4. Monitoring then **invents** `SetupAssessmentState.CONFIRMED_SETUP` from Candidate rows (`watcher_monitoring_service.py` `_canonical_lineage`). There is no stored SetupAssessment read.
5. The operator card’s “Candidates detected” row renders **legacy** `scanner_candidates` (`summary.last_scan_candidate_count`), not `canonical_candidates`. A minted canonical Candidate can coexist with UI “None”. `limitations` (including replay-not-live-mark) are computed on the API and never rendered.

The PR already notes that assembler windows do not independently confirm. That limitation does not license a fabricated lease/attempt/assessment projection, nor a UI that points “Candidates detected” at the disabled scanner.

**Fix:**

- One test: `default_paper_evidence_factory` / `AssemblingWatcherScanEvidence` → `evaluate_canonical_strategy` → no Candidate unless state is `CONFIRMED_SETUP`. WATCH/NO_SETUP from real assembler output is an acceptable proven outcome; do not substitute a confirming world behind the gate and call it the assembler path.
- One test: paper worker with Postgres (or the same session-backed store the production runtime uses) writes lease + heartbeat; monitoring `RUNNING` is built from **those** rows.
- Operator UI must show canonical Candidate identity (or explicitly label scanner vs canonical). Render `limitations`.
- Retract or narrow the PR claim that the current integration tests prove the mint → monitoring pipeline.

### R3. Single-active-worker fencing is not exclusive for the default owner

**Invariant claimed:** one active worker per scan scope; stale-worker fencing.

**Cross-owner fencing holds.** `test_concurrent_workers_single_lease` uses `worker-left` vs `worker-right`. Steal-during-persist is covered in `test_stale_worker_steal_during_persist_cannot_mint_candidate`.

**Same-owner fencing fails.** `PostgresWatcherStore.claim_lease` (and the in-memory store) **renews** when `current.owner_id == owner_id` while the lease is still active. Default `watcher_paper_worker_id` is `"watcher-paper-1"`. Production composition allows **both**:

- FastAPI in-process autostart (`main.py` `_maybe_start_watcher_paper_runtime`) when `paper_runtime_enabled`
- dedicated `python -m app.workers.watcher_paper`

ADR-049 documents both. They share the default owner id, therefore share the fencing token, therefore both pass `fence_is_active` / `_enforce_bound_fence`. Candidate uniqueness may still converge; the lease is not a mutex.

Paper `session.commit()` after `_scan_target` is unconditional. Watcher store transactions are separate from the Candidate session unless joined. A persist that succeeds under a still-valid fence, followed by a later `REJECTED_STALE_FENCE` before publish, can leave a Candidate whose attempt is rejected. That is not an unauthorized mint of a non-confirmed setup, but it is not the “persist-after-lease-loss cannot mint” story either.

**Fix (pick one, then test it):**

- Do not autostart the in-process paper loop; dedicated process only; **or**
- Include a process/session identity in the fencing token so two processes with the same configured worker id cannot both be current; **or**
- Treat same-owner concurrent claim as `lease_held` unless the caller presents the current fencing token (restart recovery via explicit takeover after TTL).

Add a same-`worker_id` dual-process test. Add a steal-after-insert-before-publish test that states the intended Candidate durability.

### R4. Prove live/replay mode mismatch is `wrong_source`

**Invariant claimed:** replay monitor + live assembler (or the reverse) is `wrong_source`.

**Code exists** (`_reconcile_monitor_and_assembled`). **Zero tests** assert it. Production `default_paper_evidence_factory` closes over one source and one `replay` flag, so the default composition is consistent. The type still allows `AssemblingWatcherScanEvidence(monitor=None)` to skip both the gate and reconcile.

**Fix:** a unit test that a live monitor snapshot + `replay=True` assembler (and the reverse) raises `reason_code="wrong_source"`. Production composition should not accept `monitor=None` (fail closed, not optional).

---

## What held (failed falsifications)

These remain true on HEAD `69df737e` and should be preserved by any remediation.

### Live evidence integrity / replay vs live mark

- Gate refuses STALE and provider outage before `assemble` (`watcher_gate.py`). Spy-assembler tests show `assemble` is not called.
- Replay availability is forced; `usable_as_current_market_price` is false; presentation `replay_fixture` (`price.py`, monitor `_availability`).
- HTTP and `PerpetualMarketStatusCard` label replay and refuse “Live mark”.
- No spot substitution; empty/stale trade window returns `None` quote, not a fabricated mark.
- Shared 10s last-trade freshness policy is not widened on the evidence path.
- Default paper factory uses one source + one `replay` flag for monitor and assembler, then gates before assemble.

### Approved strategy / SetupAssessment / Candidate authority

- Targets come only from `resolve_executable_strategy_policy` (APPROVED/ACTIVE compiled). Drafts and missing compiles are skipped.
- Evidence load re-resolves via `resolve_watcher_scan_policy` when session+store are present.
- Sole mint call site: `WatcherFusionEvaluationService._maybe_create_candidate` → `CandidateLifecycleService.create_from_confirmed_setup`.
- Persist requires `CONFIRMED_SETUP`, `PERSISTED_APPROVED_COMPILED`, non-placeholder IDs, and evidence-hash identity. In-memory authority raises `CandidateCreationAuthorityError`.
- Lifecycle rejects EXPIRED / non-confirmed / elapsed `valid_until` (evaluation clock, not wall clock).
- `evaluate_canonical_strategy` is the only evaluator on the Watcher mint path. `PaperBotEngine` and `MarketWatcherBridgeService` do not mint Candidates. No API route calls `create_from_confirmed_setup`.
- `PERSIST_AND_NOTIFY` is blocked (`notify_disabled`). Orchestrator holds `side_effects` and never calls `submit_execution` / `send_telegram`.

### Tenant / lineage / stale / outage / in-memory (cannot mint)

Exercised by stack tests (fixture evidence **behind the real gate** for stale/outage; resolve path for tenant/lineage/in-memory):

| Attack | Result on this HEAD |
|---|---|
| Stale monitor | `stale_evidence`, no Candidate |
| Provider outage | `provider_outage`, no Candidate |
| Wrong tenant target | no Candidate (`missing_canonical_evidence` / `organization_mismatch` / `strategy_not_approved`) |
| Random/draft lineage | no Candidate |
| Expired subsequent bars (fixture world) | `EXPIRED`, no Candidate |
| In-memory policy authority | no Candidate |
| Replay labeled `live_mark` | not observed on monitor/assembler/HTTP/status card |
| Config flags alone → RUNNING | STOPPED or STALE; frontend uses `snapshot.watcher_status` only |

### Paper safety (still off)

- Defaults: `watcher_orchestration_enabled=false`, `market_watcher_enabled=false`, `execution_mode=paper`, `ENABLE_REAL_TRADING` cannot enable `real_trading_enabled` (always `False`).
- `paper_runtime_enabled` requires LOCAL + paper + orchestration + not real trading. Staging/production `validate_deployment_settings` rejects Watcher and Telegram enablement flags.
- `render.yaml` / staging / production / docker examples pin Watcher and Telegram false.
- Watcher HTTP status is read-only; it does not start scans.
- Kill switch is observational on the paper worker (ADR-049: does not block Candidate persist; must not invoke execution/Telegram). Tests encode “no orders”, not “no mint”. That is consistent with the ADR. Probe errors fail **open** to `kill_switch_is_active=False` in the worker and fail **closed** in monitoring — inconsistency, not an execution bypass.

### CI / local re-run

| Check | Result |
|---|---|
| GitHub Actions `69df737e` run 35631036137 | SUCCESS (backend, frontend, evaluation, e2e-smoke, deployment-safety, docker-build) |
| Local focused pytest (this review) | **129 passed** (stack 14, paper runtime 22, monitoring 14, monitoring state 14, live monitor 21, live monitor HTTP 4, deployment safety 40) |
| Alembic heads | single head `c8d9e0f1a2b3` |

Full backend 2464 / frontend 1193 / Chromium E2E were **not** re-executed here. UNKNOWN vs the PR’s local counts.

---

## Additional findings (not independently merge-blocking if R1–R4 are fixed)

| ID | Severity | Finding |
|---|---|---|
| A1 | P2 | Rate-limited DEGRADED may keep a usable `LIVE_MARK` while availability is degraded; the gate allows assembly if the quote is still FRESH/AGING. |
| A2 | P2 | Replay `_availability` short-circuits to `REPLAY` even if the underlying tick would have been an outage. Fine for fixtures; dangerous if `perpetual_evidence_source=replay` is mistaken for live. |
| A3 | P2 | On live OHLCV fetch failure, prior `_series_15m` / `latest_15m_close` can remain in the snapshot after the price mark is cleared. |
| A4 | P2 | Lineage idempotency overwrites paper `reason_code` with `"replay"` (`_report_from_cycle`). Tests assert this. Operators can confuse scan replay with market replay. |
| A5 | P2 | ADR-050 still allows RUNNING from legacy scanner+worker heartbeat **without** an orchestration lease. ADR-051 / PR body claim lease+heartbeat only. Code implements the OR. Harmless while legacy flags stay false; staging rejects them. |
| A6 | P2 | `evaluate_manual(..., PERSIST_EVIDENCE)` publishes with `require_fence=False`. Tests only; no API caller found. |
| A7 | P2 | Postgres fence `_enforce_bound_fence` no-ops when the writer is unbound. Correct for reads; fail-open if a writer forgets `bind_from_evaluation_command`. |
| A8 | P2 | Restart recovery tests reuse in-memory store+repo; durable lease+Candidate+lifetime restart together is not proven in the paper suite. Setup-lifetime Alembic `c8d9e0f1a2b3` exists. AT-068 is still listed IN_PROGRESS in `.ai/TASKS.md`. |
| A9 | P2 | `.env.example` pins `WATCHER_ORCHESTRATION_ENABLED=false` but omits explicit `MARKET_WATCHER_ENABLED` / Telegram flags (defaults are still false). |
| A10 | P2 | `ENVIRONMENT=local` on a hosted process skips deployment Watcher rejection. `render.yaml` pins `staging`. Config discipline, not a code pin. |
| A11 | P2 | Frontend monitoring fixture uses `next_scan_basis: "lease_ttl"`. Backend next-scan never returns `lease_ttl` (paper_poll / worker_interval / bridge_interval). |
| A12 | P2 | Kill-switch probe exception in the paper worker returns `False` (fail-open for the observational flag only). |

---

## Pipeline falsification summary

```text
persisted APPROVED/ACTIVE compiled strategy
  → resolve_executable_strategy_policy          HOLDS (production targets + re-resolve)
  → monitor gate + FirstSliceEvidenceAssembler  WIRED; mint tests do not use assembler
  → WatcherOrchestrator + fusion evaluate       HOLDS (sole evaluator)
  → SetupAssessment CONFIRMED_SETUP             HOLDS in code; stack proof uses fixture world
  → Candidate persist + fence                   HOLDS for cross-owner; same-owner not exclusive
  → monitoring projection                       FAILS honesty (clocks, fabricated leases,
                                                invented CONFIRMED_SETUP, scanner UI row)
```

Unauthorized mint from stale / replay-as-live / wrong tenant / wrong lineage / expired setup / in-memory policy: **not demonstrated** on the production factory.

Unauthorized **operator belief** (final candle, historical valid, RUNNING from hand-built rows, Candidates detected from the legacy scanner): **demonstrated**.

---

## Safety statement for this review

- No product code was changed.
- Watcher was not enabled.
- Telegram was not enabled.
- Live trading was not enabled.
- No deploy, no merge.

---

## Recommended next Cursor prompt

```text
BASE: PR121 HEAD 69df737e211133786122ace76fec31eed1b237a0
READ: docs/AT072_watcher_stack_independent_review.md
IMPLEMENT remediations R1–R4 only. Do not merge. Do not deploy. Do not enable Watcher, Telegram, or live trading.

R1 Bind monitoring freshness clocks to assembler EvidenceClockReport / finality / usability. Stop mapping closed_candle_final to ohlcv.available and historical_evidence_valid to trade coverage. Do not advertise 60 minutes as the Watcher quote stale threshold.

R2 Replace vacuous stack mint/monitoring proofs. Do not inject EvaluatorWorld behind the gate and call it the assembler path. Monitoring RUNNING must come from worker-persisted lease+heartbeat. Operator UI must not present legacy scanner_candidates as the canonical mint path. Render limitations.

R3 Make one process the exclusive fence holder. Same watcher_paper_worker_id must not renew as a second live worker. Cover dual in-process + dedicated process.

R4 Test live/replay mode mismatch → wrong_source. Production AssemblingWatcherScanEvidence must not skip the monitor gate.

Keep paper defaults. Staging/production Watcher flags stay rejected.
```
