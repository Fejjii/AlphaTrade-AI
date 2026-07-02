# Paper-First MVP Demo Checklist (Slice 90)

Quick operator checklist for staging or local demos. Baseline: **1b707e0+**, paper-only, automation disabled.

| | |
|---|---|
| **Frontend** | https://alpha-trade-ai-eight.vercel.app |
| **Backend** | https://alphatrade-api-staging.onrender.com |
| **Bootstrap email** | `seed-bootstrap-1782212606@example.com` |
| **Bootstrap password** | Private — `STAGING_BOOTSTRAP_PASSWORD` (not in repo) |

Before demo: confirm `/health` shows `execution_mode=paper` and `real_trading_enabled=false`.

Narrative walkthrough: [demo_script.md](demo_script.md)

---

## Safety invariants (state aloud)

| Control | Expected |
|---------|----------|
| `execution_mode` | `paper` |
| `real_trading_enabled` | `false` |
| Worker / scanner automation | disabled |
| Telegram / webhook delivery | disabled on staging |
| Paper validation run sessions | record-only (no live runtime tick) |

Show dashboard badges: **PAPER mode**, **Real trading disabled**, **Simulated execution only**.

Sidebar: demo from **Paper-first workflow** section. Skip **Legacy proposal flow** and **Exchange** unless explaining broader product scope.

---

## Main flow checklist (12 steps)

| # | Flow | Route | Nav label | Staging smoke |
|---|------|-------|-----------|---------------|
| 1 | Dashboard | `/` | Dashboard | `staging-smoke.sh`, `staging-live-smoke.sh` |
| 2 | Setup review | `/alerts/review` | Setup Review | `browser-smoke-setup-review-staging.sh`, `browser-smoke-setup-alert-draft-staging.sh` |
| 3 | Paper drafts | `/paper-validation/drafts` | Paper Drafts | via setup-alert-draft browser smoke |
| 4 | Paper Validation Queue | `/paper-validation/candidates` | Paper Validation Queue | `paper-validation-smoke.sh` |
| 5 | Run plans | `/paper-validation/run-plans` | Run Plans | `validate-validation-priority-staging.sh` |
| 6 | Run sessions | `/paper-validation/run-sessions` | Run Sessions | `validate-run-sessions-staging.sh`, `browser-smoke-run-sessions-staging.sh` |
| 7 | Observations & outcomes | `/paper-validation/run-sessions/{id}` | (session detail) | `validate-session-observations-staging.sh`, `browser-smoke-session-observations-staging.sh` |
| 8 | Learning analytics | `/learning-analytics` | Learning Analytics | `validate-learning-analytics-staging.sh`, `browser-smoke-learning-analytics-staging.sh` |
| 9 | Validation priority | `/validation-priority` | Validation Priority | `validate-validation-priority-staging.sh`, `browser-smoke-validation-priority-staging.sh` |
| 10 | Coaching | `/coaching` | Coaching | `validate-coaching-staging.sh`, `browser-smoke-coaching-staging.sh` |
| 11 | Lessons | `/lessons` | Lessons | `lessons-smoke.sh`, `browser-smoke-lessons-staging.sh` |
| 12 | Strategy quality | `/strategy-quality` | Strategy Quality | `strategy-quality-smoke.sh`, `browser-smoke-strategy-quality-staging.sh` |

Label alignment: dashboard card, page title, nav, and links all use **Paper Validation Queue** for `/paper-validation/candidates`.

---

## End-to-end paper-first path (recommended demo order)

1. **Dashboard** — confirm paper posture and open setup review card.
2. **Setup review** → mark alert → **create draft**.
3. **Paper draft detail** → mark ready → **queue candidate**.
4. **Paper Validation Queue** → open candidate → create **run plan**.
5. **Run plan detail** → start **run session** (record-only).
6. **Session detail** → record **observation** and **outcome**.
7. **Learning analytics** — show funnel moved by new outcomes.
8. **Validation priority** — show item surfaced from backlog.
9. **Coaching** — open explain prompt; optional save to lessons.
10. **Lessons** — use **From coaching** filter; accept or reject candidate.
11. **Strategy quality** — show detector sample size / trust tier / read-only verdict.

Talking point: every step is human-initiated study — no auto-trading, no Telegram sends, no exchange orders.

---

## Pages outside the paper-first demo path

| Route | Sidebar section | Note |
|-------|-----------------|------|
| `/proposals`, `/approvals`, `/positions` | Legacy proposal flow | Paper-only but not the MVP demo chain |
| `/exchange` | Platform | Demo account read-only diagnostics when enabled |
| `/watcher`, `/market-watcher` | Market & tools | Scanner tooling; automation disabled on staging |
| `/strategy-lab` Paper Validation tab | Strategy & journal | Legacy Slice 39 runtime — distinct from manual run sessions |

Do not demo Telegram preview buttons unless explaining they are **disabled by default**.

---

## Post-demo operator validation

```bash
# Safety
BASE_URL=https://alphatrade-api-staging.onrender.com ./scripts/verify-safety.sh

# Exchange demo read-only posture
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/validate-exchange-demo-staging.sh

# Lessons read-only API smoke
BASE_URL=https://alphatrade-api-staging.onrender.com ./scripts/lessons-smoke.sh

# Optional bundled staging smoke
INCLUDE_ANALYTICS=true INCLUDE_STRATEGY_QUALITY=true \
  BASE_URL=https://alphatrade-api-staging.onrender.com \
  ./scripts/staging-smoke.sh

# Browser smokes (require STAGING_BOOTSTRAP_PASSWORD)
export STAGING_BOOTSTRAP_PASSWORD='...'
./scripts/browser-smoke-lessons-staging.sh
```

---

## Remaining polish (non-blocking)

- Legacy workflow stepper (Strategy Lab backtest path) coexists with manual paper validation chain.
- Mobile uses **More** menu with grouped sections for long nav.
- Duplicate icons in Platform section (cosmetic only).

Related: [limitations_roadmap.md](limitations_roadmap.md) · [paper_validation.md](paper_validation.md)
