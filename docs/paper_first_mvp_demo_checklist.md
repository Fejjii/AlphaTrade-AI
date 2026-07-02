# Paper-First MVP Demo Checklist (Slice 90)

Quick operator checklist for staging or local demos. Baseline: **f732063+**, paper-only, automation disabled.

| | |
|---|---|
| **Frontend** | https://alpha-trade-ai-eight.vercel.app |
| **Backend** | https://alphatrade-api-staging.onrender.com |
| **Bootstrap email** | `seed-bootstrap-1782212606@example.com` |
| **Bootstrap password** | Private — `STAGING_BOOTSTRAP_PASSWORD` (not in repo) |

Before demo: confirm `/health` shows `execution_mode=paper` and `real_trading_enabled=false`.

Longer narrative walkthrough: [demo_script.md](demo_script.md)

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

---

## Main flow checklist (12 steps)

Use dashboard cards as the home base; sidebar now includes paper-first routes.

| # | Flow | Route | What to show | Staging smoke |
|---|------|-------|--------------|---------------|
| 1 | Dashboard | `/` | Safety badges, workflow stepper, paper cards, next action | `staging-smoke.sh`, `staging-live-smoke.sh` |
| 2 | Setup review | `/alerts/review` | Review setup alerts; create draft from alert | `browser-smoke-setup-review-staging.sh`, `browser-smoke-setup-alert-draft-staging.sh` |
| 3 | Paper drafts | `/paper-validation/drafts` | Non-executable drafts from reviewed alerts | via setup-alert-draft browser smoke |
| 4 | Validation candidates | `/paper-validation/candidates` | Queued candidates (no run started) | `paper-validation-smoke.sh` (legacy runtime path) |
| 5 | Run plans | `/paper-validation/run-plans` | Planned sessions from candidates | `validate-validation-priority-staging.sh` |
| 6 | Run sessions | `/paper-validation/run-sessions` | Manual record-only sessions | `validate-run-sessions-staging.sh`, `browser-smoke-run-sessions-staging.sh` |
| 7 | Observations & outcomes | `/paper-validation/run-sessions/{id}` | Record observation + outcome on session detail | `validate-session-observations-staging.sh`, `browser-smoke-session-observations-staging.sh` |
| 8 | Learning analytics | `/learning-analytics` | Funnel, setup performance, discipline | `validate-learning-analytics-staging.sh`, `browser-smoke-learning-analytics-staging.sh`, `analytics-smoke.sh` |
| 9 | Validation priority | `/validation-priority` | Read-only ranking of what to validate next | `validate-validation-priority-staging.sh`, `browser-smoke-validation-priority-staging.sh` |
| 10 | Coaching | `/coaching` | Behavior prompts from outcomes | `validate-coaching-staging.sh`, `browser-smoke-coaching-staging.sh` |
| 11 | Lessons | `/lessons` | Pending / accepted / rejected candidates | `strategy-smoke.sh`, `validate-demo-staging.sh` |
| 12 | Strategy quality | `/strategy-quality` | Detector trust tiers, calibration | `strategy-quality-smoke.sh`, `browser-smoke-strategy-quality-staging.sh` |

---

## End-to-end paper-first path (recommended demo order)

1. **Dashboard** — confirm paper posture and open setup review card.
2. **Setup review** → mark alert → **create draft**.
3. **Paper draft detail** → mark ready → **queue candidate**.
4. **Candidate detail** → create **run plan**.
5. **Run plan detail** → start **run session** (record-only).
6. **Session detail** → record **observation** and **outcome**.
7. **Learning analytics** — show funnel moved by new outcomes.
8. **Validation priority** — show item surfaced from backlog.
9. **Coaching** — open explain prompt; optional save to lessons.
10. **Lessons** — accept or reject candidate.
11. **Strategy quality** — show detector sample size / trust tier / read-only verdict.

Talking point: every step is human-initiated study — no auto-trading, no Telegram sends, no exchange orders.

---

## Pages to avoid implying live trading

These routes exist for the broader product but are **not** the paper-first MVP demo path:

| Route | Note |
|-------|------|
| `/proposals`, `/approvals` | Legacy proposal → approval → paper order flow (still paper-only) |
| `/exchange` | Demo account read-only diagnostics when enabled |
| `/watcher`, `/market-watcher` | Scanner tooling; automation disabled on staging |
| `/strategy-lab` Paper Validation tab | Legacy Slice 39 runtime panel (scan/tick) — distinct from manual run sessions |

Do not demo Telegram preview buttons unless explaining they are **disabled by default**.

---

## Post-demo operator validation

```bash
# Safety
BASE_URL=https://alphatrade-api-staging.onrender.com ./scripts/verify-safety.sh

# Exchange demo read-only posture
BACKEND_URL=https://alphatrade-api-staging.onrender.com ./scripts/validate-exchange-demo-staging.sh

# Optional bundled staging smoke (set flags for analytics / strategy quality)
INCLUDE_ANALYTICS=true INCLUDE_STRATEGY_QUALITY=true \
  BASE_URL=https://alphatrade-api-staging.onrender.com \
  ./scripts/staging-smoke.sh
```

---

## Known MVP gaps (document, do not fix in demo)

- Sidebar is long; mobile uses **More** menu for most paper-first routes.
- Dashboard card **Paper Validation Queue** vs nav **Validation Queue** — same `/paper-validation/candidates` route.
- Legacy workflow stepper (Strategy Lab backtest path) coexists with manual paper validation chain.
- `demo_script.md` extended section still references older Strategy Lab paper validation tab — use this checklist for slices 84–89 flows.

Related: [limitations_roadmap.md](limitations_roadmap.md) · [paper_validation.md](paper_validation.md)
