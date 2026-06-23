# Screenshot Checklist

Recommended captures for **GitHub README**, **portfolio**, and **technical interviews**.
Save files under `docs/screenshots/` using the filenames below.

> Do not commit screenshots that show API keys, JWT secrets, demo passwords, or production credentials.
> Use the staging demo tenant or Docker Compose with mock providers.

---

## Portfolio demo set (staging — Slice 55)

Capture from https://alpha-trade-ai-eight.vercel.app after seeding (`DEMO_SEED_USE_SERVER_PASSWORD=true ./scripts/seed-demo.sh --api`).

| # | Screen | Route | Suggested filename | What to show |
|---|--------|-------|-------------------|--------------|
| 1 | **Dashboard** | `/` | `dashboard_staging.png` | Paper mode banner, **Real trading disabled**, workflow stepper, discipline card |
| 2 | **Strategy Lab** | `/strategy-lab` | `strategy_lab_staging.png` | Three seeded strategies (BTC, ETH, SOL) |
| 3 | **Paper Validation** | Strategy detail → Paper tab | `paper_validation_staging.png` | Active run, scan results, simulated trades |
| 4 | **Alerts** | `/alerts` | `alerts_staging.png` | Severity, source, suggested action; delivery disabled |
| 5 | **Lessons** | `/lessons` | `lessons_staging.png` | Pending vs accepted lesson candidates |
| 6 | **Risk Settings** | `/risk` | `risk_settings_staging.png` | Daily limits, max trades, guard toggles |
| 7 | **AI Workspace safety** | `/workspace` | `ai_workspace_safety_staging.png` | Real-trading refusal or mutation confirmation prompt |
| 8 | **Provider / health** | `/` developer details or `/docs` | `provider_status_staging.png` | Redis healthy, Qdrant degraded fallback, exchange paper-only — **no URLs or secrets** |

Use these for portfolio decks; keep existing `docs/screenshots/*.png` for README unless you regenerate the full set.

---

## Required captures — local Docker (12)

| # | Screen | Route / source | Suggested filename | What to show |
|---|--------|----------------|-------------------|--------------|
| 1 | **Dashboard** | `/` | `dashboard.png` | Paper mode banner, provider cards, navigation |
| 2 | **AI Trading Workspace** | `/workspace` | `ai_workspace.png` | Chat input, structured analysis, risk badge |
| 3 | **Market Monitor** | `/market` | `market_monitor.png` | Ticker/OHLCV, live vs mock labels |
| 4 | **Proposal detail** | `/proposals` (detail panel) | `proposal_detail.png` | Entry/stop/targets, risk rules, confidence |
| 5 | **Approval detail** | `/approvals` | `approval_detail.png` | Pending approval, action buttons, linked proposal |
| 6 | **Paper position** | `/positions` | `paper_position.png` | Simulated position, P&amp;L, paper-only messaging |
| 7 | **Journal** | `/journal` | `journal.png` | Entry form or list with lessons/tags |
| 8 | **Knowledge search** | `/knowledge` | `knowledge_search.png` | Search results, citations, source types |
| 9 | **Usage & quota** | `/usage` | `usage_dashboard.png` | Token counts, cost_source labels, quota panel |
| 10 | **Audit events** | `/audit` | `audit_events.png` | Proposal → approval → paper order chain |
| 11 | **Provider status** | `/` or API docs | `provider_status.png` | Exchange paper-only, LLM/embeddings status |
| 12 | **Login or settings** | `/login` or `/settings` | `settings.png` | Auth flow or notification preferences |

---

## Optional captures

| Screen | Route | Suggested filename | When useful |
|--------|-------|-------------------|-------------|
| Market Watcher | `/market-watcher` | `market_watcher_staging.png` | Read-only observation story |
| Watchlist | `/watchlist` | `watchlist.png` | Symbol monitoring |
| Billing (mock) | `/billing` | `billing.png` | Monetization scaffold |
| Mobile layout | any (narrow viewport) | `mobile-dashboard.png` | Responsive PWA demo |
| API docs | `/docs` | `openapi.png` | Backend depth for engineers |

---

## Capture tips

1. **Staging:** Reseed demo data before capture; confirm `/health` shows paper mode.
2. **Window size:** 1440×900 or 1280×800 for README; 390×844 for mobile optional.
3. **Theme:** Consistent light mode unless branding specifies dark.
4. **Data:** Use `demo@alphatrade.ai` — never personal email or passwords in frame.
5. **Secrets:** Blur or crop provider panels if any connection URL appears before redeploy.
6. **Annotations:** Optional arrows in Figma for interview decks — keep repo PNGs unannotated.

Automated capture (local Docker):

```bash
cd frontend && npm run capture:screenshots
```

---

## Pre-capture checklist

- [ ] `EXECUTION_MODE=paper` on `/health`
- [ ] `real_trading_enabled: false` on `/health`
- [ ] Paper banner visible on dashboard
- [ ] Demo seeded: 3 strategies, paper validation, 4 alerts, 5 lessons
- [ ] No passwords, tokens, or connection URLs visible
- [ ] External notifications shown as disabled in settings

---

## Demo script alignment

Portfolio order (5–8 min): [demo_script.md](demo_script.md)

Dashboard → Strategy Lab → Paper Validation → Alerts → Lessons → Risk → Market Watcher → AI Workspace (safety prompts) → Settings (notifications)

Extended local order:

Dashboard → Market → Workspace → Proposals → Approvals → Paper order → Positions → Journal → Knowledge → Usage → Audit → Auth/Settings
