# AT-010 — Real-money safety architecture roadmap

**Date:** 2026-07-21 · **Status:** Design only  
**Non-negotiable:** No live trading implementation, no real exchange writes, no real credentials, no weakening of paper defaults, no worker/scanner automation for live paths, no deployment of live-execution code in this task.

Companion docs: `docs/AT010_readiness_audit.md`, `docs/AT010_risk_register.md`.

---

## 1. Architecture diagram (target Mode D — future)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         Operator / Human                                 │
│  UI (paper banners) · Approval console · Kill switch · Incident runbook  │
└───────────────┬───────────────────────────────┬──────────────────────────┘
                │ approve / reject / kill       │ monitor / rollback
                ▼                               ▼
┌──────────────────────────────┐   ┌───────────────────────────────────────┐
│  Control plane (AlphaTrade)  │   │  Observability & audit                │
│  - AuthN/Z + org RBAC        │──▶│  - Immutable audit log                │
│  - Proposal service          │   │  - Metrics / alerts / traces          │
│  - Risk engine (deterministic│   │  - Reconciliation reports             │
│    BLOCK final)              │   └───────────────────────────────────────┘
│  - Limits: daily loss, size, │
│    leverage, exposure        │
│  - Kill switch (server)      │
│  - Approval workflow FSM     │
│  - Idempotency store         │
└───────────────┬──────────────┘
                │ OrderIntent (validated)
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                 Exchange execution abstraction (port)                    │
│  place / cancel / amend* / get / list · never withdraw/transfer/leverage │
│  *amend only if venue-supported and risk-revalidated                     │
└───────┬─────────────────────────────┬────────────────────────────────────┘
        │                             │
        ▼                             ▼
┌───────────────────┐       ┌────────────────────────┐
│ Sandbox adapter   │       │ Real adapter (isolated)│
│ (testnet/demo)    │       │ Separate process/module│
│ Mode C            │       │ Separate credentials   │
│ Allowlisted hosts │       │ Feature-flagged Mode D │
└───────────────────┘       │ Disabled by default    │
                            └───────────┬────────────┘
                                        │ TLS + signed requests
                                        ▼
                            ┌────────────────────────┐
                            │ Exchange venue         │
                            │ Orders / fills / pos   │
                            └────────────────────────┘

Market data plane (parallel):
  Public/read feeds → Freshness gate (is_live, age, fallback_used, sanity)
                    → Risk + sizing + stop enforcement (fail closed if stale)
```

### Component contracts (future)

| Component | Responsibility | Fail-closed rule |
|-----------|----------------|------------------|
| Risk engine | Deterministic limits + freshness + kill | Any uncertainty → BLOCK |
| Approval FSM | Human gate for Mode D intents | No approval → no adapter call |
| Execution port | Venue-agnostic order API | Unknown state → reconcile before retry |
| Sandbox adapter | Testnet/demo only | Host allowlist; no prod hosts |
| Real adapter | Isolated binary/module | Cannot load unless Mode D program flag + secrets present |
| Reconciler | Compare local vs venue | Drift → halt new orders |
| Kill switch | Global/org halt | Overrides approvals |

---

## 2. Capability map (25 required areas)

| # | Area | Phase introduced | Notes |
|---|------|------------------|-------|
| 1 | Exchange execution abstraction | 0–1 | Port + null/paper adapters first |
| 2 | Sandbox/testnet adapter | 1 | Mode C only |
| 3 | Real exchange adapter isolation | 0, 3 | Spec in 0; code behind hard flag in 3; separate package/process |
| 4 | Order lifecycle state machine | 0–1 | Intent→submitted→acked→partial→filled/canceled/rejected |
| 5 | Idempotency / duplicate prevention | 1 | Client key + venue clientOrderId + DB unique |
| 6 | Human approval workflow | 2 | Dual control for size/notional thresholds |
| 7 | Kill switch | 1–2 | Server-side; UI wired; paper path first (AT-014) |
| 8 | Maximum daily loss | 0–1 | From `DailyRiskState`; hard BLOCK |
| 9 | Maximum position size | 0–1 | Per symbol + portfolio |
| 10 | Maximum leverage | 0–1 | Cap + refuse venue leverage mutations |
| 11 | Exposure limits | 0–1 | Gross/net, correlation buckets |
| 12 | Stop-loss enforcement | 1–2 | Exchange SL where available + local monitor |
| 13 | Slippage and liquidity checks | 1 | Pre-trade spread/depth gates |
| 14 | Data freshness requirements | 0–1 | Hard thresholds; ties to AT-007 |
| 15 | Price sanity checks | 1 | Bands vs mid/mark; reject outliers |
| 16 | Partial fills | 1 | State machine + avg price accounting |
| 17 | Reconciliation | 1–2 | Periodic + post-incident |
| 18 | Retry and timeout policy | 1 | Idempotent retries only; budgeted |
| 19 | Circuit breakers | 2 | Error-rate / reject-rate / data-quality |
| 20 | Credential isolation and rotation | 0–1 | Secret manager; trade-only scopes; no withdraw |
| 21 | Audit logging | 0–1 | Every intent/decision/adapter call |
| 22 | Monitoring and alerts | 2 | In-app first; external delivery optional later |
| 23 | Rollback and recovery | 0, 2 | Deploy + position flatten runbooks |
| 24 | Incident handling | 0, 2 | Severity, halt, communicate, postmortem |
| 25 | Paper-to-live promotion gates | 0, 4 | Written checklist; no auto-promote |

---

## 3. Branch strategy

- Keep **`main` stable and paper-first**.
- Use **short-lived feature branches** per slice (days–week), merge only after CI + paper safety checks.
- **Do not** create a long-lived `live-trading` branch.
- **Do not** merge anything that weakens paper-only defaults (`EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`).
- Live-adapter code, if ever introduced, must live behind compile/runtime gates and land in tiny PRs with explicit Mode D authorization — never as drive-by hardening.

### Recommended branch names

| Branch | Purpose |
|--------|---------|
| `feat/at-011-authz-tools-risk` | Close unauth compute surfaces |
| `feat/at-012-paper-risk-at-execution` | Fresh risk + eligibility + size bind |
| `feat/at-013-rag-fail-closed` | Embeddings/Qdrant fail-closed |
| `feat/at-014-server-kill-switch` | Persist + enforce kill switch |
| `feat/at-007-data-freshness-gates` | Conservative stale/degraded mode |
| `feat/at-015-provider-mode-quotas` | Honor PROVIDER_MODE; narrative quota |
| `feat/at-016-audit-uow-metrics` | Audit UoW + metrics baseline |
| `feat/at-017-frontend-auth-headers` | Middleware + CSP |
| `feat/at-018-rate-limit-proxy-trust` | Redis-required + proxy trust |
| `feat/at-019-backup-restore-runbook` | Backup/restore drill docs |
| `docs/at-020-live-safety-spec` | Phase 0 specification only |
| `feat/at-021-execution-port-sandbox` | Phase 1 port + sandbox (no real) |

---

## 4. Phased roadmap

### Phase 0 — Architecture and safety specification

| Field | Content |
|-------|---------|
| **Goal** | Freeze Mode D requirements, state machines, limits, promotion gates — **documents + ADRs only** |
| **Scope** | Specs for items 1–25; threat model; RPO/RTO; credential matrix; order FSM; reconciliation design; incident SEV definitions |
| **Dependencies** | AT-010 audit (this doc); paper posture remains default |
| **Safety gates** | No application live-execution code; no credential provisioning for real trading; ADRs accepted |
| **Tests** | Spec review checklist; threat-model review notes |
| **Exit criteria** | Signed-off ADR set; open Critical paper findings closed or explicitly scheduled; promotion checklist drafted |
| **Estimated complexity** | M |
| **Recommended Cursor model** | Grok 4.5 / Opus 4.8 |
| **Task ID** | AT-020 |

### Phase 1 — Sandbox execution

| Field | Content |
|-------|---------|
| **Goal** | Venue-agnostic execution **port** + **sandbox/testnet** adapter; paper remains default |
| **Scope** | Order FSM; idempotency; retries/timeouts; partial fills accounting; slippage/liquidity/price sanity; freshness hard gates; daily loss / size / leverage / exposure BLOCK; stop-loss monitor for sandbox; audit every call; reconcilation job (sandbox) |
| **Dependencies** | Phase 0; AT-011…AT-014 paper hardening; AT-007 |
| **Safety gates** | Host allowlist only; no prod hosts; `ENABLE_REAL_TRADING=false`; no withdraw/transfer/leverage-change APIs; Redis-required; kill switch blocks sandbox place |
| **Tests** | Contract tests vs recorded sandbox fixtures; chaos: timeout, duplicate key, partial fill, stale data BLOCK |
| **Exit criteria** | Sandbox place/cancel/reconcile green for 14 consecutive days paper-equivalent soak; zero Critical defects |
| **Estimated complexity** | H |
| **Recommended Cursor model** | Grok 4.5 / Opus 4.8 |
| **Task ID** | AT-021 (+ follow-ons) |

### Phase 2 — Approval-gated execution

| Field | Content |
|-------|---------|
| **Goal** | Human approval workflow with dual control, circuit breakers, monitoring — still **sandbox capital only** |
| **Scope** | Approval FSM thresholds; dual approver for large notional; circuit breakers; alerts; incident runbooks; rollback drills; org-wide audit views |
| **Dependencies** | Phase 1 exit; AT-008 E2E approval paths |
| **Safety gates** | No approval bypass; rubber-stamp detection metrics; kill switch drills monthly |
| **Tests** | E2E approval/refusal; breaker trips; alert routing (in-app) |
| **Exit criteria** | Documented dual-control drills passed; breaker + kill drills recorded |
| **Estimated complexity** | H |
| **Recommended Cursor model** | Opus 4.8 |
| **Task IDs** | AT-022 |

### Phase 3 — Tiny-capital pilot

| Field | Content |
|-------|---------|
| **Goal** | Isolated real adapter with **tiny** notional, separate credentials, explicit human authorization program |
| **Scope** | Real adapter in isolated module/process; trade-only keys; max notional pennies–low hundreds; hard daily loss; continuous reconciliation; 24/7 halt criteria |
| **Dependencies** | Phase 2; legal/compliance review (human); credential vault; separate authorized task (not ordinary impl) |
| **Safety gates** | Separate task + written approval to touch Mode D flags; production still defaults paper elsewhere; canary env; time-boxed pilot |
| **Tests** | Shadow compare sandbox vs tiny real; reconcilation diffs = 0 material; kill switch proven on real cancel |
| **Exit criteria** | N successful tiny round-trips; zero unexplained drift; postmortem template filled even if clean |
| **Estimated complexity** | VH |
| **Recommended Cursor model** | Opus 4.8 (safety-critical) |
| **Task IDs** | AT-023 (authorization-gated) |

### Phase 4 — Controlled scale-up

| Field | Content |
|-------|---------|
| **Goal** | Raise limits only via promotion gates with evidence |
| **Scope** | Limit ladder; promotion checklist automation (evidence attach); exposure buckets; ongoing eval gates (AT-003) |
| **Dependencies** | Phase 3 success window; paper strategy quality thresholds |
| **Safety gates** | No auto-promote; each ladder step is a REVIEW_REQUIRED change |
| **Tests** | Limit ladder property tests; soak under load; backup restore drill current |
| **Exit criteria** | Written scale policy; consecutive promotion steps with zero SEV-1 |
| **Estimated complexity** | H |
| **Recommended Cursor model** | Opus 4.8 |
| **Task IDs** | AT-024 (authorization-gated) |

---

## 5. Paper-to-live promotion gates (checklist draft)

A strategy or system may **not** advance toward Mode D unless **all** are true:

1. Paper defaults unchanged on `main`.
2. All Critical findings from AT-010 closed (or formally accepted with compensating control).
3. AT-007 freshness/degrade fail-closed proven in tests.
4. Server kill switch proven (paper + sandbox).
5. Risk re-check at execution proven.
6. Idempotency + reconciliation proven under chaos.
7. Human approval dual-control proven for threshold sizes.
8. Credentials: trade-only, no withdraw, rotation runbook tested.
9. Backup/restore drill within last 90 days.
10. Evaluation/evidence pack attached (paper metrics, not marketing claims).
11. Separate **authorized** Mode D task exists — ordinary feature tasks cannot flip flags.
12. Rollback: previous deploy + flatten/cancel procedure rehearsed.

---

## 6. Recommended next implementation slice (immediate)

**Do not start Phase 1 sandbox yet.** Close paper Critical/High first:

1. **AT-011** — Authz for `/tools`, `/risk/*`, strategy evaluate; gate `/docs` outside local.  
   Branch: `feat/at-011-authz-tools-risk` · Model: **Composer 2.5** (impl) + Grok 4.5 review  
2. Then **AT-012** — Fresh risk + eligibility at paper place; bind size/price; fail-closed zero stop.  
   Branch: `feat/at-012-paper-risk-at-execution` · Model: **Grok 4.5**  
3. Parallelizable: **AT-013** RAG fail-closed; **AT-014** server kill switch; **AT-007** freshness.

Phase 0 (AT-020) may proceed as docs-only in parallel once AT-011 is merged.

---

## 7. Explicit non-goals for near-term slices

- Enabling `ENABLE_REAL_TRADING`
- Changing `EXECUTION_MODE` away from `paper`
- Real exchange writes / withdrawals / transfers / leverage changes
- Long-lived live-trading branch
- Autonomous worker that places live orders
- Claiming profitability or guaranteed outcomes
