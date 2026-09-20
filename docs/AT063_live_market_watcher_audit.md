# AT-063 — Live market data + Watcher audit (read-only)

**Status:** Audit complete. No runtime flags flipped. No Watcher activation. Paper only.  
**Base:** `main@20d2cac` (2026-09-20)  
**Branch:** `cursor/next_live_market_watcher_audit-7e05`  
**ADR:** AT-ADR-042  
**Runtime probe of live staging HTTP:** not performed (no deploy credentials in this session). Staging *configuration* is taken from checked-in `render.yaml` + code defaults. Claims about what a running staging instance currently returns are marked **UNKNOWN** unless they follow from those artifacts.

This document does not enable Watcher, live trading, Telegram, or any worker loop.

---

## 1. Why staging can display stale compatibility BTC prices

There is no single backend label `"stale compatibility"`. Staging can *compose* that UX from four independent systems that the canonical stack does not yet own.

### 1.1 Decision UI always stamps compatibility authority

`/decision/market` calls legacy `POST /market/analyze`, then `marketQualityFromAnalysis` hard-codes:

```93:93:frontend/src/lib/canonical-decision/compose.ts
    authority: "compatibility_projection",
```

That path is **not** `evaluate_setup` and **not** `SetupAssessment`. A FreshnessPill can still show **Stale** / **Fallback source** / **Live** from `meta.is_stale` / `meta.fallback_used` (`MarketQualityCard.tsx`). The card is compatibility even when Binance spot is actually live.

PVC-backed decision rows use the same authority (`compose.ts` `marketQualityFromCandidate`, `sourceKind: "compatibility_candidate"`). `/decision/candidates` mixes `GET /canonical/candidates` with paper-validation queue items and labels the latter compatibility-only.

### 1.2 Legacy market path may substitute a frozen mock BTC price

Staging Render env (`render.yaml`):

| Flag | Staging value |
|------|----------------|
| `PROVIDER_MODE` | `fallback` |
| `MARKET_DATA_ENABLED` | `true` |
| `MARKET_DATA_PROVIDER` | unset → code default `binance` |
| `PERPETUAL_EVIDENCE_SOURCE` | unset → code default **`replay`** |
| `DEMO_SEED_ENABLED` | `true` (API service) |

`PROVIDER_MODE=fallback` fail-closes **LLM / embeddings / Qdrant**. It does **not** fail-close market data.

`resolve_market_data_provider` still constructs `BinancePublicMarketDataProvider` with `MockMarketDataProvider` as fallback (`backend/src/app/providers/factory.py`). On timeout, HTTP error, or regional block, `get_ticker` / `get_ohlcv` return mock data (`backend/src/app/providers/market_data.py`).

Mock BTCUSDT last price is a **hash of the symbol string**, not a market:

```113:116:backend/src/app/providers/market_data.py
def _mock_price(symbol: str) -> Decimal:
    digest = hashlib.sha256(symbol.encode()).hexdigest()
    base = 20_000 + (int(digest[:8], 16) % 50_000)
```

Verified: **BTCUSDT = 47326**, ETHUSDT = 49086, SOLUSDT = 60446. Envelope: `source="mock"`, `is_live=False`, `fallback_used=True`, **`is_stale=False`**. The number sits in a plausible historical BTC range and does not move, so it reads as a stale live price unless the UI reads the envelope.

`/market` **does** warn (“Using mock fallback — prices are not live”). `/decision/market` shows a FreshnessPill but still titles the result as market quality under compatibility authority. PVC pages show `Latest price` with **no** live/fallback/stale badge.

Whether a given staging request currently hits Binance or mock is **UNKNOWN** without an authenticated probe. The fallback path is compiled in and is legal in staging.

### 1.3 Compatibility snapshots freeze `latest_price` and never refresh

Paper-validation drafts copy `metrics.latest_price` / `meta.latest_price` once (`paper_validation_draft_service.py`). Candidates and run-plans copy that float. UI:

```147:147:frontend/src/app/(app)/paper-validation/candidates/[candidateId]/page.tsx
            <p>Latest price: {formatPrice(candidate.latest_price)}</p>
```

Those metrics originate from the **legacy** Market Watcher scanner / setup detectors (`market_watcher_scanner.py`, `market_watcher_setup_detectors.py`) using **spot** OHLCV closes — not USD-M perpetual evidence, not CVD, not 10s freshness.

Staging locks Watcher **off** (`MARKET_WATCHER_ENABLED=false`, `WATCHER_ORCHESTRATION_ENABLED=false`, `WORKER_ENABLED=false`). Nothing in the authorized runtime refreshes those rows. They age in Postgres indefinitely.

### 1.4 Demo seed writes frozen mock BTC = 65000

`DEMO_SEED_ENABLED=true` on the staging API service. Demo seed writes:

- paper signal / open paper trade **BTCUSDT @ 65000**, exchange `"mock"`
- Market Watcher observations **BTCUSDT @ 65000**, `data_freshness="demo_seed"`, exchange `"mock"`
- ETH observation explicitly **STALE**

Those values are synthetic compatibility fixtures, not live marks. If seed has run against the staging DB (UNKNOWN without a data probe), journal / watcher / paper-validation surfaces can show 65000 next to live or mock 47326.

### 1.5 Canonical perpetual evidence is not the UI ticker

Phase 5 default is **replay fixtures** frozen at trigger `2026-01-15T16:00Z` (`market_contracts/first_slice.py`). Replay is registered for `/providers/status` only. It is **not** wired to `/market/ticker`, `/market/analyze`, or the decision market page.

So staging can show:

1. live Binance **spot** last price on `/market` (if the public REST call succeeds),
2. mock **47326** on the same APIs (if it fails),
3. demo / PVC **65000** (or other scan-time closes) on compatibility pages,
4. empty canonical Candidates (Watcher off; no mint HTTP),

none of which are live USD-M perpetual evidence with 10s trade freshness.

### 1.6 Cache can preserve a degraded envelope

Ticker cache TTL is **15s** and returns the stored payload **without re-evaluating age** (`market_data_service.py`). A mock fallback payload can be served as “fresh cache” while remaining non-live. Successful live tickers stamp `timestamp=now`, so they are never `is_stale` under the 60s ticker rule; OHLCV can still mark the snapshot stale when the last candle is older than `2 × timeframe`.

---

## 2. Capability inventory

Legend: **CLOSED** = implemented, tested, and on the runtime path that staging would use today (including “disabled but correctly locked”). **REUSABLE** = implemented + tested as a library/port, not the live loop or not the UI ticker. **MISSING** = not present. **BLOCKED** = cannot proceed without a human/safety/ops decision.

### 2.1 CLOSED

| Area | What exists | Evidence |
|------|-------------|----------|
| Paper / Mode D lock | `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`; staging/production refuse Watcher + Telegram flags | `config.py`, `deployment_safety.py:41–67`, `render.yaml` |
| Spot REST ingestion | On-demand Binance public `ticker/24hr`, `klines`, `depth`; optional USD-M `premiumIndex` / `openInterest` (legacy only) | `providers/market_data.py` |
| Spot BTC + alt tickers | Any normalized spot symbol via `/market/ticker\|ohlcv\|snapshots` | `api/routes/market.py` |
| Legacy OHLCV + analyze | Cache, indicators, `StrategyService` / `analyze()` | `market_data_service.py` |
| Legacy freshness envelope | `is_live`, `is_stale`, `fallback_used`, `source`, `retrieved_at` on `/market/*` | `MarketDataEnvelope`; `/market` badges |
| Watcher flags + `/health` | Both watcher flags default false; surfaced on liveness | `health.py:34–36` |
| Canonical Candidate authority | `CandidateLifecycleService` only; PVC cannot mint | `signal_fusion/lifecycle.py` |
| Canonical Candidate Postgres | `PostgresCandidateRepository` + worker fence bind | `persistence/candidate_postgres.py` |
| Canonical reads HTTP | `GET /canonical/candidates` (no mint) | `api/routes/canonical.py:1` |
| `evaluate_setup` | First-slice Bearish Liquidity Sweep / CVD / aggressive sell imbalance, BTCUSDT perp 15m/4h | `signal_fusion/evaluator.py`, `market_contracts/first_slice.py` |
| Fusion Watcher boundary | `WatcherFusionEvaluationService`: evidence → window → setup → Candidate only on `CONFIRMED_SETUP` + `PERSIST_EVIDENCE` | `watcher/fusion_evaluation.py:349–377` |
| Orchestrator contracts | `evaluate` shared by manual/worker; `run_worker` claims lease; stale fence cannot publish | `watcher/orchestrator.py` |
| Postgres Watcher store | Leases, heartbeats, lineage, attempts, health | `persistence/watcher_postgres.py`, Alembic watcher tables |
| Slice-59 worker process | Render worker service defined; `WORKER_ENABLED=false`; never starts Watcher | `workers/entrypoint.py:43–44`, `render.yaml:109–129` |
| Paper scheduler | `ENABLE_PAPER_SCHEDULER=false`; manual tick only | `paper_scheduler_service.py` |
| Network safety of USD-M adapter | GET-only, host allowlist `fapi.binance.com`, no keys, no orders | `market_contracts/adapters/http.py`, docs |

### 2.2 REUSABLE (do not reinvent)

| Area | What exists | Gap to runtime |
|------|-------------|----------------|
| Phase 5 USD-M adapter | `BinanceUsdmPerpetualSource.fetch_closed_ohlcv` + `fetch_ordered_trades` | Not called by Watcher, worker, or `/market/*`. Staging source = replay |
| Replay perpetual source | Deterministic fixture; default `PERPETUAL_EVIDENCE_SOURCE=replay` | Explicit mock; must not be treated as live |
| CVD | Unrounded quote-volume CVD, T−32 window, coverage proof | Library + tests only |
| Aggressive / signed flow | `signed_quote_delta / total_quote_volume`; sell imbalance helper | Library + evaluator only |
| Phase 5 freshness | `first-slice-btc-usdt-usdm-freshness/v1`, trade max age **10s**, `valid_until` fail-closed | Not applied to UI tickers |
| `PublicMarketObservation` | Typed envelope, no tenant IDs | Not persisted; no HTTP |
| `WatcherScanEvidencePort` | Load already-normalized `FirstSliceEvidenceBundle` | Only `InMemoryWatcherScanEvidence.bind` in tests |
| `build_postgres_watcher_orchestrator` | Explicit builder | Defaults to `ScriptedEvaluationBoundary`, `enabled=False`; not in FastAPI/worker |
| `build_fusion_evaluation_service` | Fusion evaluator composition | Defaults to **in-memory** Candidate repo |
| Watcher observability events | Structured logs + store `append_event` | Not Prometheus; not HTTP |
| Legacy Market Watcher HTTP | `/market-watcher/*` mounted | Flag off; uses **spot** OHLCV + `analyze()`, not fusion |
| BloFin demo market data | Read-only exchange-demo | Not `/market/*` |
| Decision FreshnessPill | Works when analyze meta is present | Compatibility authority; no Phase 5 10s clock |
| Canonical paper runtime | Worker/API attach Candidate/Eligibility/TradePlan Postgres | “Never starts Watcher” |

### 2.3 MISSING

| Area | Missing piece |
|------|----------------|
| Real-time streams | No market websocket; no aggTrade user stream; REST on demand only |
| Continuous canonical scan loop | No caller of `WatcherOrchestrator.run_worker` in `workers/` or `main.py` |
| Live evidence assembler | No production port: USD-M fetch → CVD/flow → `FirstSliceEvidenceBundle` → `AssessmentCommand` for *current* closed 15m bar (fixture clock is 2026-01-15) |
| Persistence of public observations | No table/HTTP for `PublicMarketObservation` |
| Perp marks in UI | No USD-M last/mark on Market Monitor or decision |
| Altcoin perpetual contracts | First slice is **BTCUSDT only**. Legacy scanner symbols include ETHUSDT/SOLUSDT **spot** only |
| Watcher → worker wiring | Worker scanner writes `SetupDetectionRecord` via `analyze()`; does not mint Candidates |
| Canonical mint HTTP | `/canonical/*` is read-only by design |
| Watcher Prometheus metrics | No series in `observability/metrics.py` |
| Public Watcher health API | Orchestration health snapshots are store-only |
| PVC / demo price provenance | `latest_price` has no `is_live` / `fallback_used` / `retrieved_at` |
| Staging market-data fail-closed | Spot path still mock-falls-back (AT-007 still open) |
| Forming vs final in UI | `/market` serves forming-capable spot klines; Phase 5 rejects forming |

### 2.4 BLOCKED (human / safety / ops — do not bypass)

| Blocker | Why |
|---------|-----|
| `WATCHER_ORCHESTRATION_ENABLED=true` in staging/production | `deployment_safety.py:60–61` refuses process start. Flip is a **separately authorized** enablement, not an ordinary impl task |
| `MARKET_WATCHER_ENABLED` / bridge / auto-tick in staging | Same file, lines 54–59 |
| `WORKER_ENABLED=true` on Render | Operator env change; current blueprint pins false |
| `PERPETUAL_EVIDENCE_SOURCE=binance_usdm` on staging | Ops/config; live USD-M may be region-blocked; **must not** fall back to spot/mock |
| Telegram / `PERSIST_AND_NOTIFY` | Notify stays blocked; Telegram disabled |
| Mode D / real execution | Separate program (AT-020+) |
| Expanding first slice to alts | No identity/CVD/freshness contracts beyond BTCUSDT USD-M |
| Treating PVC as Candidate | Forbidden by AT-ADR-026/027 |

**Mismatch (not a blocker, but do not document as a gate):** `docs/market_watcher.md` says disabled Watcher returns a no-side-effect result. `MarketWatcherService.scan` does **not** check `market_watcher_enabled`; it checks paper mode, real-trading, confirm phrases, and symbol lists. Bridge **does** check its flag. Staging still cannot *enable* the flag.

---

## 3. Architecture as it actually is

```
UI /market and /decision/market
  → GET/POST /market/*  (spot, on-demand, 15s cache)
  → BinancePublicMarketDataProvider
       → success: lastPrice from api.binance.com (spot)
       → error: MockMarketDataProvider (_mock_price; BTCUSDT=47326)
  → StrategyService / analyze()     ← NOT evaluate_setup

Phase 5 registry status only (default replay)
  → ReplayPerpetualSource | BinanceUsdmPerpetualSource
  → NOT used for last_price, Watcher, or Candidate mint

Canonical paper runtime (API + worker composition)
  → Postgres Candidate / Eligibility / TradePlan
  → GET /canonical/* reads
  → POST /execution/paper-plan (human)
  → Watcher loops: not started

Watcher library (disabled)
  → WatcherOrchestrator.evaluate / run_worker
  → WatcherFusionEvaluationService
  → InMemoryWatcherScanEvidence (tests)  ← no live assembler
  → CandidateLifecycleService (+ optional Postgres fence)
```

Two worker locks exist and must not be conflated:

1. Slice-59 `WorkerLock` (Redis `SET NX`) around legacy OHLCV `analyze()` cycles.  
2. Watcher `claim_lease` on `watcher_worker_leases (organization_id, scan_scope)` with fencing token + Candidate persist `SELECT … FOR UPDATE`.

Three evaluators exist; only fusion may mint canonical Candidates:

1. `app.analysis.analyze` / `StrategyService` — legacy (worker, `/market/analyze`, Market Watcher scanner).  
2. Slice-72 condition detectors — alerts / PVC metrics.  
3. `evaluate_setup` — first-slice setup truth.

---

## 4. Technical risks

1. **False market truth.** Mock 47326 / demo 65000 / frozen PVC closes can be read as BTC. Compatibility labeling is easy to miss next to a large number.
2. **Spot ≠ perpetual.** Using `/market/analyze` or legacy Watcher OHLCV as setup evidence would violate AT-ADR-021 (no spot fallback).
3. **10s freshness vs 15s/60s/2×TF freshness.** Mixing policies will confirm setups on stale flow.
4. **Fixture clock.** First-slice replay evaluated_at is `2026-01-15T16:15:05Z`. A live assembler must bind the *last closed* 15m bar, not the golden fixture interval.
5. **Enabling Watcher without the assembler** would mint from empty/in-memory evidence or scripted outcomes (`ScriptedEvaluationBoundary` is the Postgres builder default).
6. **Enabling the Slice-59 worker** would write legacy `SetupDetectionRecord`s, not Candidates — a second detection authority.
7. **Regional USD-M failure.** Live adapter fail-closes (good). UI spot path mock-falls-back (bad if operators assume one health signal).
8. **Lease/fence dual-write.** Candidate persist fence is implemented; Watcher store is not in the worker. Wiring must keep one transaction rule (AT-ADR-031).
9. **Notify / Telegram.** `PERSIST_AND_NOTIFY` must stay blocked.
10. **Cache honesty.** Cached mock envelopes can look freshly retrieved.
11. **AT-007 still TODO.** Conservative fail-closed on degraded market data is not complete for the spot path.
12. **Alt expansion.** ETH/SOL on the legacy scanner are not first-slice instruments; do not feed them to `evaluate_setup`.

---

## 5. Smallest safe path (design only)

Goal: live **read-only** USD-M evidence → continuous **paper** Watcher evaluation → canonical Candidates → freshness visible in UI → paper monitoring.

**Non-goals for this path:** Mode D, Telegram, auto TradePlan, auto paper execution, websockets, alt perpetuals, enabling Watcher in this audit.

Ordered slices (each must keep `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`, Telegram off, default Watcher **false** until the safety-lock slice + human flip):

### Slice A — AT-064 Live first-slice evidence assembler (Watcher stays off)

Reuse `BinanceUsdmPerpetualSource` + CVD/flow/freshness. Add one production `WatcherScanEvidencePort` that, for BTCUSDT USD-M:

1. Resolves last **final** 15m trigger and required 4h context (100 / 30).  
2. Fetches aggTrades for the CVD window with existing pagination policy.  
3. Builds coverage proof, CVD, signed flow, `FirstSliceEvidenceBundle`, `AssessmentCommand`, `CanonicalEvidenceWindowV1`.  
4. Fail-closed on forming bars, gaps, regional errors, `fallback_used`, spot, mock.  
5. Default config remains `PERPETUAL_EVIDENCE_SOURCE=replay`. Live mode is opt-in.  
6. Optional **read-only** HTTP for evidence + freshness (no Candidate mint).  
7. Tests: replay golden hash parity; recorded USD-M fixture; refuse spot/mock.

### Slice B — AT-065 Compatibility price honesty (parallel, no Watcher)

UI/API honesty so staging cannot present 47326 / 65000 / frozen PVC closes as live BTC:

1. Every displayed price carries `source`, `is_live`, `fallback_used`, `is_stale`, `retrieved_at` (or `snapshot_at` + age).  
2. PVC / demo seed / mock numbers labeled **compatibility snapshot** or **mock**, never Live.  
3. `/decision/market` must not imply canonical `SetupAssessment`.  
4. Optional staging fail-closed for spot mock fallback (overlaps AT-007) — **do not** silently invent prices; show unavailable.

### Slice C — AT-066 Paper Watcher safety-lock amendment (human-gated)

Change `deployment_safety` **only** if explicitly authorized:

- Allow `WATCHER_ORCHESTRATION_ENABLED=true` in **staging** iff paper + real trading false + Telegram false + notify blocked + USD-M evidence fail-closed.  
- Keep production false until a later task.  
- Keep `MARKET_WATCHER_ENABLED` (legacy scanner) false — do not revive spot Watcher as canonical.  
- Do **not** flip `render.yaml` in the same PR unless the human task says so. Default remains false.

### Slice D — AT-067 Watcher worker wiring (flag default false)

After A:

1. Worker cycle calls `WatcherOrchestrator.run_worker` with fusion evaluator + Postgres store + Candidate fence + live evidence port.  
2. Manual `evaluate` parity.  
3. Mint Candidate only on `CONFIRMED_SETUP` + `PERSIST_EVIDENCE`.  
4. Do not call `analyze()` as a second authority.  
5. Do not create TradePlans, alerts, or paper orders.  
6. Loop runs only when **both** `WORKER_ENABLED` and `WATCHER_ORCHESTRATION_ENABLED` are true.

### Slice E — AT-068 Paper monitoring UI + observability

1. Decision/candidates: canonical rows from Watcher; PVC remain compatibility.  
2. Freshness from Phase 5 policy (10s trade clock), not spot 60s.  
3. Empty/disabled Watcher state is explicit.  
4. Prometheus + `/health` (or ready) for perpetual source, lease, last successful scan age. `METRICS_ENABLED` stays false until ops.

---

## 6. Recommended parallel ownership

| Lane | Owns | Must not touch |
|------|------|----------------|
| **A — Evidence** (Grok 4.6 Extra High) | AT-064 assembler, fail-closed USD-M, read-only evidence HTTP | Watcher enablement, UI chrome, `deployment_safety` |
| **B — Honesty UI** (frontend-capable) | AT-065 labels, PVC provenance, decision market copy | Evaluator predicates, leases |
| **C — Safety lock** (safety review) | AT-066 `deployment_safety` + ADR + Render notes | Flipping flags on staging |
| **D — Watcher runtime** (Grok 4.6 Extra High) | AT-067 composition into worker | Legacy `MarketWatcherService` expansion, Telegram |
| **E — Monitoring** | AT-068 UI + metrics | Execution, eligibility predicates |

**Serial constraints:** D requires A. Enabling D in staging requires C + human. E can start UI empty-states in parallel with A; live Candidate rows need D.

Do **not** run a parallel agent that “just turns on” `MARKET_WATCHER_ENABLED` or the Slice-59 scanner as a shortcut.

---

## 7. Execution-ready next prompts

Copy one prompt per agent. Base every prompt on latest `main` after this audit merges (or `main@20d2cac` plus this branch).

### Prompt A — evidence assembler

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
CREATE: cursor/live-usdm-evidence-assembler
TASK: AT-064
OBJECTIVE: Implement a production WatcherScanEvidencePort that assembles
canonical first-slice BTCUSDT USD-M evidence from BinanceUsdmPerpetualSource
(closed 15m/4h OHLCV, aggTrades, CVD, signed quote flow, 10s freshness,
CanonicalEvidenceWindowV1, FirstSliceEvidenceBundle, AssessmentCommand).
Reuse app.market_contracts and evaluate_setup contracts. Do not change
evaluator predicates.
CONSTRAINTS: Paper only. Do not enable Watcher, Telegram, or real trading.
Default PERPETUAL_EVIDENCE_SOURCE remains replay. Live binance_usdm is
opt-in and must fail closed (no spot, no mock). No Candidate mint HTTP.
No render.yaml flag flips.
VALIDATION: replay golden hash parity; recorded USD-M fixture; refuse
forming/gap/regional/spot/mock; ruff; mypy --strict on new modules;
focused + full backend pytest.
```

### Prompt B — UI honesty

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
CREATE: cursor/compatibility-price-honesty
TASK: AT-065
OBJECTIVE: Make every user-visible BTC/alt price honest about source and
freshness. PVC latest_price, demo seed 65000, and mock hash 47326 must
never appear as Live. /decision/market must remain labeled compatibility
and must not claim canonical SetupAssessment. Surface is_live,
fallback_used, is_stale, source, retrieved_at or snapshot age.
CONSTRAINTS: Paper only. No Watcher enablement. No live-trading copy.
Do not wire evaluate_setup in this slice unless evidence HTTP already
exists on main.
VALIDATION: frontend unit tests for mock/demo/PVC labels; lint; typecheck;
relevant e2e.
```

### Prompt C — safety lock (review first)

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
CREATE: cursor/paper-watcher-safety-lock
TASK: AT-066
OBJECTIVE: Design+implement the smallest deployment_safety change so
staging MAY set WATCHER_ORCHESTRATION_ENABLED=true only when
execution_mode=paper, real trading false, Telegram false, and notify
blocked. Production stays false. Legacy MARKET_WATCHER_ENABLED stays
false. Do not flip render.yaml unless the task comment explicitly
authorizes the env change. Stop at REVIEW_REQUIRED before any staging
enablement.
CONSTRAINTS: Do not activate Watcher. Do not enable Telegram. Do not
weaken real-trading pins.
VALIDATION: deployment_safety tests for allowed staging combo and all
refusals; /health flags; ruff; pytest for those tests.
```

### Prompt D — Watcher worker wiring

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main with AT-064 merged
CREATE: cursor/watcher-worker-fusion-runtime
TASK: AT-067
OBJECTIVE: Wire WatcherOrchestrator.run_worker into the existing worker
loop using WatcherFusionEvaluationService, PostgresWatcherStore,
PostgresCandidateRepository fence, and the live/replay evidence port.
Manual and worker evaluate must converge. Candidate mint only on
CONFIRMED_SETUP + PERSIST_EVIDENCE. Default flags remain false.
CONSTRAINTS: Do not enable flags. Do not start Telegram. Do not create
TradePlans or paper orders. Do not use ScriptedEvaluationBoundary or
legacy analyze() as setup truth. Do not change fusion predicates.
VALIDATION: fencing/lease/idempotency tests; crash/retry; tenant
isolation; full backend pytest; ruff; mypy --strict on watcher +
persistence composition.
```

### Prompt E — paper monitoring UI

```text
MODEL: Grok 4.6 Extra High
CHAT: new Cursor Cloud Agent
BASE: latest main
CREATE: cursor/paper-watcher-monitoring-ui
TASK: AT-068
OBJECTIVE: Show canonical Watcher Candidates and Phase 5 freshness in
/decision and related monitoring. Empty/disabled Watcher must be
explicit. PVC remains compatibility. Do not add execute buttons.
CONSTRAINTS: Paper only. No Watcher flag flip. Bind only existing
canonical GET APIs plus any AT-064 evidence read API if present.
VALIDATION: frontend tests; lint; typecheck; build.
```

---

## 8. What this audit did not do

- No application behavior change.  
- No flag activation.  
- No staging HTTP probe (credentials absent).  
- No Mode D design refresh.  
- Did not mark historical AT-042…AT-051 TASKS rows DONE; their **code is on `main@20d2cac`** even where TASKS still says IN_PROGRESS.

## 9. UNKNOWN

- Whether the currently deployed staging process SHA equals `20d2cac`.  
- Whether Binance spot REST from Render Frankfurt currently succeeds or mock-falls-back.  
- Whether `seed_demo` has been applied to the staging database.  
- Whether operators already set `PERPETUAL_EVIDENCE_SOURCE` in the Render dashboard (checked-in blueprint does not).  
- Live USD-M reachability from staging (adapter reports regional 401/403/418/451 as unavailable).
