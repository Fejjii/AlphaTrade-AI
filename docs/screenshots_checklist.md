# Screenshot Checklist

Recommended captures for **GitHub README**, **portfolio**, and **technical interviews**.
Save files under `docs/screenshots/` using the filenames below.

> Do not use screenshots that show real API keys, JWT secrets, or production credentials.
> Demo with mock providers or blur sensitive fields.

---

## Required captures (12)

| # | Screen | Route / source | Suggested filename | What to show |
|---|--------|----------------|-------------------|--------------|
| 1 | **Dashboard** | `/` | `dashboard.png` | Paper mode banner, provider cards, navigation |
| 2 | **AI Trading Workspace** | `/workspace` | `workspace.png` | Chat input, structured analysis, risk badge |
| 3 | **Market Monitor** | `/market` | `market.png` | Ticker/OHLCV, live vs mock labels |
| 4 | **Proposal detail** | `/proposals` (detail panel) | `proposal.png` | Entry/stop/targets, risk rules, confidence |
| 5 | **Approval detail** | `/approvals` | `approval.png` | Pending approval, action buttons, linked proposal |
| 6 | **Paper position** | `/positions` | `position.png` | Simulated position, P&amp;L, paper-only messaging |
| 7 | **Journal** | `/journal` | `journal.png` | Entry form or list with lessons/tags |
| 8 | **Knowledge search** | `/knowledge` | `knowledge.png` | Search results, citations, source types |
| 9 | **Usage & quota** | `/usage` | `usage.png` | Token counts, cost_source labels, quota panel |
| 10 | **Audit events** | `/audit` | `audit.png` | Proposal → approval → paper order chain |
| 11 | **Provider status** | `/` or API docs | `providers.png` | Exchange paper-only, LLM/embeddings status |
| 12 | **Login or settings** | `/login` or `/settings` | `auth-settings.png` | Auth flow or email verification status |

---

## Optional captures

| Screen | Route | Suggested filename | When useful |
|--------|-------|-------------------|-------------|
| Watchlist | `/watchlist` | `watchlist.png` | Showing symbol monitoring |
| Risk overview | `/risk` | `risk.png` | Explaining risk engine rules |
| Billing (mock) | `/billing` | `billing.png` | Discussing monetization scaffold |
| Invitations | `/invitations` | `invitations.png` | Team/onboarding story |
| Mobile layout | any (narrow viewport) | `mobile-dashboard.png` | Responsive PWA demo |
| API docs | `/docs` | `openapi.png` | Backend/API depth for engineers |

---

## Capture tips

1. **Use Docker Compose** for the cleanest demo (cookie auth, all providers reachable).
2. **Window size:** 1440×900 or 1280×800 for README; 390×844 for mobile optional.
3. **Theme:** Consistent light mode unless branding specifies dark.
4. **Data:** Use demo org/user names (e.g. `demo@alphatrade.local`), not personal email.
5. **Annotations:** Optional arrows in Figma/Preview for interview decks — keep repo PNGs unannotated.

---

## README integration

After capturing, reference in root `README.md`:

```markdown
![Dashboard](docs/screenshots/dashboard.png)
```

Create the directory if missing:

```bash
mkdir -p docs/screenshots
```

---

## Demo script alignment

Capture order matching [demo_script.md](demo_script.md):

Dashboard → Market → Workspace → Proposals → Approvals → Paper order → Positions → Journal → Knowledge → Usage → Audit → Auth/Settings

---

## Pre-capture checklist

- [ ] `EXECUTION_MODE=paper` confirmed on `/health`
- [ ] `real_trading_enabled: false` on `/health`
- [ ] Paper banner visible on dashboard
- [ ] At least one completed proposal → approval → paper position flow
- [ ] Journal entry synced to knowledge (search returns hit)
- [ ] No secrets visible in browser or screenshots
