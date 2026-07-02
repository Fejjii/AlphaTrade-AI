# Paper-First MVP — Completion Note

**Status:** Complete — **98% readiness** (demo-ready, portfolio-ready)  
**Baseline commit:** `57e35a5`  
**CI:** Green  
**Real trading:** Disabled  
**Automation:** Disabled (worker, scanner, Telegram delivery)

AlphaTrade AI is a **human-in-the-loop AI trading copilot** for crypto. The paper-first MVP delivers a full study-and-learning workflow: from setup review through manual paper validation, analytics, coaching, and strategy quality — all **record-only**, with no auto-trading.

This is a **decision-support and education platform**, not an auto-trading bot.

Related: [demo_script.md](demo_script.md) · [paper_first_mvp_demo_checklist.md](paper_first_mvp_demo_checklist.md) · [releases/v0.1.0-paper-mvp.md](releases/v0.1.0-paper-mvp.md)

---

## 1. What the paper-first MVP includes

| Area | Scope |
|------|--------|
| **Core workflow** | 12-flow paper-first chain: dashboard → setup review → drafts → validation queue → run plans → run sessions → observations/outcomes → learning analytics → validation priority → coaching → lessons → strategy quality |
| **AI workspace** | LangGraph agent with guardrails, RAG context, schema-validated responses; LLM explains — **code decides** |
| **Risk & safety** | Deterministic risk engine (15 rules); `BLOCK` is final authority; paper-only execution |
| **Auth & tenancy** | JWT sessions, RBAC (OWNER / TRADER / VIEWER), optional httpOnly refresh cookies |
| **Observability** | Audit events, usage metering, organization quotas, provider status dashboard |
| **Knowledge loop** | Journal → RAG sync; coaching → lesson candidates → human accept/reject |
| **Platform extras (out of demo path)** | Legacy proposal/approval flow, Strategy Lab backtest, exchange read-only diagnostics, market watcher tooling |

Every MVP step is **human-initiated study** — no background ticks, no Telegram sends, no exchange orders.

---

## 2. Validated workflow

End-to-end paper-first path (validated on staging with smoke scripts and unit tests):

| # | Step | Route |
|---|------|-------|
| 1 | Dashboard — paper posture, next actions | `/` |
| 2 | Setup review — mark alerts, create draft | `/alerts/review` |
| 3 | Paper drafts — mark ready for validation | `/paper-validation/drafts` |
| 4 | Paper Validation Queue — queue candidates | `/paper-validation/candidates` |
| 5 | Run plans — structured study plans | `/paper-validation/run-plans` |
| 6 | Run sessions — manually started, record-only | `/paper-validation/run-sessions` |
| 7 | Observations & outcomes — human-recorded study data | `/paper-validation/run-sessions/{id}` |
| 8 | Learning analytics — funnel and setup performance | `/learning-analytics` |
| 9 | Validation priority — ranked backlog | `/validation-priority` |
| 10 | Coaching — deterministic prompts from outcomes | `/coaching` |
| 11 | Lessons — pending / accepted / rejected; coaching filter | `/lessons` |
| 12 | Strategy quality — detector trust tiers, read-only verdicts | `/strategy-quality` |

**Navigation:** Sidebar **Paper-first workflow** group. Skip **Legacy proposal flow** and **Exchange** for MVP demos.

---

## 3. Safety guarantees

| Control | Staging / default | Meaning |
|---------|-------------------|---------|
| `EXECUTION_MODE` | `paper` | Simulated / record-only execution |
| `ENABLE_REAL_TRADING` | `false` | Hard kill switch — no live orders |
| Worker / scanner automation | disabled | No background ticks or scans |
| Telegram / webhook delivery | disabled on staging | No external auto delivery |
| Run sessions (MVP path) | record-only | Human records observations/outcomes; no live runtime tick |
| Risk `BLOCK` | final | Blocks paper execution even if mistakenly approved |
| Market data | Binance public REST or mock | Read-only; no trading API keys |
| LLM | optional narrative layer | Never overrides risk, approval, or safety posture |

**Dashboard badges to confirm:** **PAPER mode**, **Real trading disabled**, **Simulated execution only**.

Pre-demo check:

```bash
curl -s https://alphatrade-api-staging.onrender.com/health | python3 -m json.tool
# Expect: execution_mode=paper, real_trading_enabled=false
```

---

## 4. Staging URLs

| Service | URL | Notes |
|---------|-----|-------|
| **Frontend (use this)** | https://alpha-trade-ai-eight.vercel.app | Production alias for demos |
| **Frontend (git-main)** | https://alpha-trade-ai-git-main-alphatrade-ai.vercel.app | Same deployment family |
| **Backend API** | https://alphatrade-api-staging.onrender.com | `environment=staging`, paper mode |
| **Blocked — do not use** | https://alpha-trade-ai.vercel.app | Unrelated Vercel placeholder |
| **Blocked — do not use** | https://alphatrade-ai.vercel.app | Unrelated static app |

**Bootstrap email:** `seed-bootstrap-1782212606@example.com`  
**Bootstrap password:** Private — `STAGING_BOOTSTRAP_PASSWORD` (not in repo)

---

## 5. Key smoke scripts

### Safety (run first)

```bash
BASE_URL=https://alphatrade-api-staging.onrender.com ./scripts/verify-safety.sh
```

### Bundled API smoke

```bash
FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
  BASE_URL=https://alphatrade-api-staging.onrender.com \
  ./scripts/staging-smoke.sh

# Extended live QA (CORS, login, dashboard, notifications, watcher)
FRONTEND_URL=https://alpha-trade-ai-eight.vercel.app \
  BACKEND_URL=https://alphatrade-api-staging.onrender.com \
  ./scripts/staging-live-smoke.sh
```

### Per-flow API smokes

| Flow | Script |
|------|--------|
| Paper validation queue | `paper-validation-smoke.sh` |
| Run plans / validation priority | `validate-validation-priority-staging.sh` |
| Run sessions | `validate-run-sessions-staging.sh` |
| Session observations | `validate-session-observations-staging.sh` |
| Learning analytics | `validate-learning-analytics-staging.sh` |
| Coaching | `validate-coaching-staging.sh` |
| Lessons | `lessons-smoke.sh` |
| Strategy quality | `strategy-quality-smoke.sh` |
| Exchange demo posture | `validate-exchange-demo-staging.sh` |

### Browser smokes (require `STAGING_BOOTSTRAP_PASSWORD`)

| Flow | Script |
|------|--------|
| Setup review | `browser-smoke-setup-review-staging.sh` |
| Setup → draft | `browser-smoke-setup-alert-draft-staging.sh` |
| Run sessions | `browser-smoke-run-sessions-staging.sh` |
| Session observations | `browser-smoke-session-observations-staging.sh` |
| Learning analytics | `browser-smoke-learning-analytics-staging.sh` |
| Validation priority | `browser-smoke-validation-priority-staging.sh` |
| Coaching | `browser-smoke-coaching-staging.sh` |
| Lessons | `browser-smoke-lessons-staging.sh` |
| Strategy quality | `browser-smoke-strategy-quality-staging.sh` |

Optional bundled run with analytics and strategy quality:

```bash
INCLUDE_ANALYTICS=true INCLUDE_STRATEGY_QUALITY=true \
  BASE_URL=https://alphatrade-api-staging.onrender.com \
  ./scripts/staging-smoke.sh
```

Full matrix: [paper_first_mvp_demo_checklist.md](paper_first_mvp_demo_checklist.md)

---

## 6. Remaining non-MVP work

These items are **documented and intentionally deferred** — they do not block the paper-first MVP.

| Category | Items |
|----------|-------|
| **Trading & execution** | Live exchange integration; real broker connectivity; approval-gated live orders |
| **Automation** | Worker / scanner always-on loops; Telegram / webhook auto delivery; paper validation scheduler background tick |
| **Billing** | Production Stripe wiring (Checkout, Portal, entitlements) |
| **UX polish (cosmetic)** | Duplicate sidebar icons; legacy Strategy Lab stepper coexisting with manual chain; mobile relies on **More** menu for long nav |
| **Product consolidation** | Legacy proposal flow vs manual paper validation UX unification |
| **Quality & ops** | LangSmith traces at scale; invite signup; managed deployment hardening |

Full roadmap: [limitations_roadmap.md](limitations_roadmap.md)

---

## 7. Demo checklist (short)

Before presenting (~2 minutes):

- [ ] `/health` shows `execution_mode=paper` and `real_trading_enabled=false`
- [ ] Run `verify-safety.sh` against staging
- [ ] Log in at https://alpha-trade-ai-eight.vercel.app/login
- [ ] Confirm dashboard badges: **PAPER mode**, **Real trading disabled**
- [ ] Sidebar: use **Paper-first workflow** section only

During demo (~15 minutes, 12 flows):

- [ ] Walk setup review → draft → queue → run plan → session → observation/outcome
- [ ] Show learning analytics funnel moved by new data
- [ ] Show validation priority surfacing backlog items
- [ ] Open coaching explain prompt; optional save to lessons
- [ ] Filter lessons by **From coaching**; show accept/reject workflow
- [ ] Show strategy quality trust tiers (read-only, not trade recommendations)
- [ ] State aloud: every step is human-initiated — no auto-trading

After demo:

- [ ] Re-run `verify-safety.sh`
- [ ] Optional: `lessons-smoke.sh` and one browser smoke for regression spot-check

Narrative script: [demo_script.md](demo_script.md)

---

## 8. Daily use checklist (short)

For operators using staging or local Docker day-to-day:

**Morning**

- [ ] Confirm `/health` — paper mode, real trading disabled
- [ ] Run `verify-safety.sh` (or `staging-smoke.sh` for full API check)
- [ ] Review dashboard **What to do next** and validation priority

**During study session**

- [ ] Process setup review alerts → create drafts as needed
- [ ] Queue ready drafts; create run plans for candidates worth studying
- [ ] Start run sessions manually; record observations and outcomes
- [ ] Review coaching prompts; accept or reject lesson candidates deliberately

**End of day**

- [ ] Check learning analytics for funnel movement
- [ ] Review strategy quality sample sizes before trusting detector tiers
- [ ] Do **not** enable automation, Telegram delivery, or real trading env vars

**Weekly**

- [ ] Run bundled staging smoke with `INCLUDE_ANALYTICS=true INCLUDE_STRATEGY_QUALITY=true`
- [ ] Spot-check one browser smoke per major flow if UI changed
- [ ] Review [limitations_roadmap.md](limitations_roadmap.md) before enabling any new flags

---

## Completion summary

| Item | Value |
|------|-------|
| Readiness | **98%** — all 12 flows verified; smoke scripts green; labels aligned |
| Remaining 2% | Cosmetic nav icons, legacy stepper coexistence, mobile **More** menu grouping |
| Product behavior | Unchanged by this document |
| Real trading | **Disabled** — not wired in this release |
| Automation | **Disabled** on staging by default |

*Document created at MVP completion baseline `57e35a5`.*
