# AlphaTrade AI — Portfolio Demo Script

Reviewer-friendly walkthrough for the **paper-first MVP** (12 flows, ~15 minutes). Use staging or Docker Compose locally.

Operator checklist: [paper_first_mvp_demo_checklist.md](paper_first_mvp_demo_checklist.md)

| | |
|---|---|
| **Frontend** | https://alpha-trade-ai-eight.vercel.app |
| **Backend** | https://alphatrade-api-staging.onrender.com |
| **Bootstrap email** | `seed-bootstrap-1782212606@example.com` |
| **Bootstrap password** | Private — `STAGING_BOOTSTRAP_PASSWORD` (not in repo) |

> **Do not use** https://alpha-trade-ai.vercel.app (wrong placeholder).

Before presenting, confirm `/health` shows `execution_mode=paper` and `real_trading_enabled=false`.

Sidebar: use the **Paper-first workflow** group. **Legacy proposal flow** and **Exchange** are out of scope for this demo.

---

## Opening pitch (30 seconds)

AlphaTrade AI is a **human-in-the-loop AI trading copilot** for crypto. The paper-first MVP walks from setup review → manual paper validation → learning analytics → coaching → strategy quality — all **read-only study and human-initiated recording**, with no auto-trading.

It is **not** an auto-trading bot. The LLM explains and retrieves context; **code decides** risk posture and paper-only safety.

---

## Safety disclaimer (30 seconds)

| Control | Staging value | Meaning |
|---------|---------------|---------|
| `EXECUTION_MODE` | `paper` | Simulated / record-only |
| `ENABLE_REAL_TRADING` | `false` | Hard kill switch — no live orders |
| Worker / scanner automation | disabled | No background ticks or scans |
| Telegram / webhook | disabled | No external auto delivery |
| Run sessions | record-only | Human records observations/outcomes |

**Show:** Dashboard **PAPER mode**, **Real trading disabled**, **Simulated execution only**.

---

## Login (30 seconds)

1. Open https://alpha-trade-ai-eight.vercel.app/login
2. Sign in with bootstrap or demo credentials
3. Confirm dashboard loads; refresh — session persists

---

## 1. Dashboard (45 seconds)

Route: `/`

- Safety badges and **What to do next**
- Cards: Setup review, paper drafts, **Paper Validation Queue**, run plans, run sessions
- Validation priority, coaching, lessons pending
- Talking point: deterministic, tenant-scoped summary — no LLM, no broker orders

---

## 2. Setup review (45 seconds)

Route: `/alerts/review`

1. Review unreviewed setup alerts from the market watcher
2. Mark an alert reviewed / watching
3. **Create paper draft** from an alert
4. Emphasize: never sends Telegram or places orders

---

## 3. Paper drafts (30 seconds)

Route: `/paper-validation/drafts`

1. Show drafts created from setup review
2. Open a draft — non-executable ideas only
3. Mark ready for validation when appropriate

---

## 4. Paper Validation Queue (30 seconds)

Route: `/paper-validation/candidates`

1. Queued candidates from ready drafts
2. Queue only — no run started, no orders
3. Same label as dashboard **Paper Validation Queue** card

---

## 5. Run plans (30 seconds)

Route: `/paper-validation/run-plans`

1. Structured plans from reviewing candidates
2. Plan only — no session started yet

---

## 6. Run sessions (30 seconds)

Route: `/paper-validation/run-sessions`

1. Manually started observation sessions
2. Record only — no live runtime tick, no automation

---

## 7. Observations & outcomes (45 seconds)

Route: `/paper-validation/run-sessions/{sessionId}`

1. Record an **observation** (e.g. approached trigger)
2. Record an **outcome** (e.g. success, invalidated, no_trade)
3. Human study data feeds learning analytics — not trade execution

---

## 8. Learning analytics (45 seconds)

Route: `/learning-analytics`

1. Funnel: sessions → observations → outcomes
2. Setup performance by condition / timeframe
3. Read-only insights — no orders, no automation

---

## 9. Validation priority (30 seconds)

Route: `/validation-priority`

1. Ranked backlog of run plans and candidates
2. Human study aid — what to validate next

---

## 10. Coaching (45 seconds)

Route: `/coaching`

1. Deterministic behavior prompts from outcomes
2. Open explain on a prompt
3. Optional: save to lessons (audited, human-initiated)

---

## 11. Lessons (30 seconds)

Route: `/lessons`

1. Pending vs accepted vs rejected tabs
2. **From coaching** source filter
3. Pending observations are not accepted rules until reviewed

---

## 12. Strategy quality (30 seconds)

Route: `/strategy-quality`

1. Detector trust tiers and sample sizes
2. Low-sample detectors → needs more validation
3. Read-only verdicts — never trade recommendations

---

## Closing (30 seconds)

- End-to-end paper-first path is human-initiated at every step
- Production-style guardrails: RBAC, audit, quotas, provider fallbacks
- Legacy **Trade Proposals / Approvals / Exchange** routes remain for broader product — not this MVP demo

---

## Optional: AI Workspace safe prompts (2 minutes)

Route: `/workspace`

| Prompt | Expected behavior |
|--------|-------------------|
| Summarize my dashboard and what to focus on today. | Read-only; mentions paper mode |
| Can you place a real trade for BTC now? | **Refused** — real trading disabled |
| Turn on Telegram notifications. | **Refused or safely framed** — delivery disabled |

Full chat validation: `./scripts/validate-demo-chat-staging.sh`

---

## Operator validation (after deploy)

```bash
curl -s https://alphatrade-api-staging.onrender.com/health | python3 -m json.tool

BASE_URL=https://alphatrade-api-staging.onrender.com ./scripts/verify-safety.sh
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/validate-exchange-demo-staging.sh

BASE_URL=https://alphatrade-api-staging.onrender.com ./scripts/lessons-smoke.sh

export STAGING_BOOTSTRAP_PASSWORD='...'
./scripts/browser-smoke-lessons-staging.sh
```

See [paper_first_mvp_demo_checklist.md](paper_first_mvp_demo_checklist.md) for the full smoke script matrix.

---

## Legacy / extended routes (optional, not paper-first MVP)

| Section | Route | Note |
|---------|-------|------|
| Trade proposals & approvals | `/proposals`, `/approvals` | Legacy paper order flow |
| Strategy Lab paper tab | `/strategy-lab/{id}` | Slice 39 runtime — distinct from manual run sessions |
| Exchange diagnostics | `/exchange` | Read-only demo account when enabled |
| Market watcher / scanner | `/watcher`, `/market-watcher` | Automation disabled on staging |

Screenshots: [screenshots_checklist.md](screenshots_checklist.md) · Related: [architecture.md](architecture.md) · [security.md](security.md)
