# Physical iPhone Safari validation pack (staging)

**Audience:** Sofien (physical iPhone, Safari)  
**Purpose:** Collect honest pass/fail evidence after staging is redeployed to current `main`, so PR #41 staging/iPhone sections can be completed.  
**Scope:** Documentation and manual execution only. No production-code changes, no deploy, no merge, no live-trading enablement.

**Related sources (read-only context for this pack):**

| Source | Role |
|---|---|
| PR #41 audit — `docs/product/at040_final_polish_and_readiness_audit.md` (§4 staging, §5 physical iPhone) | Why this pack exists; historical staging lag notes; physical iPhone still required |
| `docs/testing/at041_pr4_readiness_checklist.md` §B / §C | Automated vs pending physical separation |
| Mobile nav (`MobileBottomNavigation`, `MobileMenuSheet`, `navigation-config`) | Bottom bar + Menu sheet destinations |
| Paper close (`/positions`, `PositionCard`) | Explicit exit-price close flow (FP2-001) |
| Command menu (`CommandMenu`, `TopBar`) | Navigation palette — touch affordance note below |
| Kill switch (`KillSwitchButton`) | In-app confirm dialog + BLOCK chrome |
| Deep links (`?signal=`, `?entry=`, `?document=`, `?tab=`) | Messages → Safari contract |
| Portfolio `/portfolio` · Analytics `/analytics` | Scrolling, tabs, filters, charts |

---

## Honesty rules (non-negotiable)

1. **Browser emulation is not physical validation.** Chromium at 390×844, Playwright, or Responsive Design Mode must never be marked as iPhone Safari pass.
2. **No profitability claim.** Passing this pack does not imply returns, edge, or readiness for live capital.
3. **No live-trading enablement.** Keep `EXECUTION_MODE=paper` and `ENABLE_REAL_TRADING=false`. Do not change exchange credentials, leverage, withdrawals, or real order paths.
4. **Failures must not be silently marked passed.** If a step cannot be completed, mark **FAIL** or **BLOCKED** with evidence. Partial results stay partial.
5. **Do not modify PR #41 content during this pack’s creation/execution session** except via the documented completion procedure in §6 after evidence exists.

---

## 1. Before starting

**Expected duration:** approximately **15–25 minutes** once staging is on current `main` and a paper position (or seed path) is available.

### 1.1 Staging frontend URL

Use the production staging alias (fill if your org uses a different alias after redeploy):

| Field | Value |
|---|---|
| Staging frontend URL | `https://alpha-trade-ai-eight.vercel.app` *(placeholder / confirmed staging alias — replace if redeploy published a different production URL)* |
| Staging backend health | `https://alphatrade-api-staging.onrender.com/health` |
| Do **not** use | `https://alpha-trade-ai.vercel.app` (wrong app) · legacy `alphatrade-ai.vercel.app` |

Record the URL you actually opened:

```
FRONTEND_URL_USED: ________________________________
```

### 1.2 Confirm backend and frontend revisions

**Backend** — open health (Safari or laptop) and record:

```
GET https://alphatrade-api-staging.onrender.com/health
```

Expected fields (names may vary slightly; record exact JSON keys you see):

| Check | Expected | Actual |
|---|---|---|
| `status` | `ok` | |
| `environment` | `staging` | |
| `execution_mode` | `paper` | |
| `real_trading_enabled` | `false` | |
| `git_sha` (or equivalent) | Matches the **latest approved `main` SHA at the time of this staging redeploy** (record that SHA; it is not a permanent fixed target) | |

**Frontend** — Vercel may not expose a build-commit header. Record:

| Check | Actual |
|---|---|
| Deploy time / Vercel deployment note (if known) | |
| Intended `main` SHA for this redeploy (from deploy notes / `origin/main` at deploy time) | |
| UI shows paper posture chips after login | yes / no |
| `NEXT_PUBLIC` posture consistent with paper (StatusStrip / settings) | yes / no / unknown |

**Target revision:** Validate whatever **latest approved `main` commit** was selected for the staging redeploy you are testing. Do **not** treat any older SHA (including `d0f724a…`) as a permanent forever-target.

**Historical evidence only (PR #41 audit, not a live target):** a read-only staging health check once reported backend `git_sha=62d3856…`, which was then 26 commits behind the then-current `main` at `d0f724a…`. That mismatch justified halting staging validation at that time. After a new redeploy, compare against the **new** approved `main` SHA, not that historical pair.

**Gate:** If backend `git_sha` is still behind the intended redeploy `main` SHA, **stop**. Do not invent a pass. Redeploy is a human/pipeline action outside this pack.

### 1.3 Confirm paper mode and real trading disabled

| Check | How | Pass? |
|---|---|---|
| Backend paper | Health: `execution_mode=paper` | ☐ |
| Real trading off | Health: `real_trading_enabled=false` | ☐ |
| UI paper chrome | After login: PAPER / “Real trading disabled” (or equivalent) visible on shell | ☐ |
| No live-enable UI used | You did not toggle any live-trading or exchange-live control | ☐ |

### 1.4 Test account / data preparation

Prepare before the timer starts:

| Prep | Notes | Done |
|---|---|---|
| Staging account | Existing login **or** register a new org/user (password ≥ 12 chars; organization required) | ☐ |
| Owner role | Kill-switch activate/deactivate requires **owner**; use an owner account or skip kill-switch with explicit BLOCKED note | ☐ |
| Open paper position | At least one open paper position on `/positions` for the close drill (seed via normal paper cycle: proposal → approval → paper execution if none exists) | ☐ |
| Deep-link IDs | Copy one real `signal` id, one journal `entry` id (and optionally knowledge `document` id) from the UI after login | ☐ |
| Evidence folder | Photos/Files album or Notes ready for screenshots / screen recordings | ☐ |
| Device info | Model, iOS version, Safari version (Settings → General → About; Safari version from Settings → Apps → Safari or About) | ☐ |

### 1.5 Device identity (fill once)

| Field | Value |
|---|---|
| Device model | |
| iOS version | |
| Safari version | |
| Tester | Sofien |
| Date (local) | |
| Intended redeploy `main` SHA (at deploy time) | |
| Staging backend `git_sha` | |
| Frontend URL used | |

---

## 2. Step-by-step iPhone Safari checklist

For **every** step, fill a row in §3 (evidence log). Mark **PASS** / **FAIL** / **BLOCKED** / **N/A** only with evidence.

**Mobile navigation map (current product):**

| Surface | Destinations |
|---|---|
| Bottom bar | Dashboard `/` · Signals `/tradingview-signals` · Plan `/workspace` · Portfolio `/portfolio` · **Menu** (sheet) |
| Menu sheet | Validate `/paper-validation` · Journal `/journal` · Analytics `/analytics` · Settings `/settings` |

### Step A — Registration / login

| # | Action | Expected | Result |
|---|---|---|---|
| A1 | Open `{FRONTEND}/login` or `/register` in **Safari** (not Chrome emulation) | Auth form loads; paper-only copy visible on login | |
| A2 | Register **or** log in; complete any verify-email path if required | Lands in app shell without error loop | |
| A3 | Confirm autofill offers email/password on auth fields | Safari Password AutoFill suggestions appear (or system Keychain prompt) | |
| A4 | Confirm posture chips | PAPER / real trading disabled (or equivalent) legible | |

### Step B — Dashboard

| # | Action | Expected | Result |
|---|---|---|---|
| B1 | Open Dashboard via bottom nav (`/`) | Single clear page title; no raw crash text; usable at phone width | |
| B2 | Scroll full page | No content trapped under bottom nav / home indicator | |

### Step C — Signals

| # | Action | Expected | Result |
|---|---|---|---|
| C1 | Bottom nav → **Signals** (`/tradingview-signals`) | Inbox loads or honest empty/error state (not a false “all clear” if load failed) | |
| C2 | If signals exist, open one | Detail/selection works with touch | |

### Step D — Plan

| # | Action | Expected | Result |
|---|---|---|---|
| D1 | Bottom nav → **Plan** (`/workspace`) | Plan workspace loads; kill-switch control reachable from shell/page | |
| D2 | Spot-check touch targets | Primary actions comfortably tappable | |

### Step E — Validate

| # | Action | Expected | Result |
|---|---|---|---|
| E1 | Menu → **Validate** (`/paper-validation`) | Page loads; tables/panels scroll horizontally inside wrappers if wide | |
| E2 | Return via Menu or browser back | Navigation remains coherent | |

### Step F — Journal

| # | Action | Expected | Result |
|---|---|---|---|
| F1 | Menu → **Journal** (`/journal`) | Journal loads | |
| F2 | Open quick-entry / focus a text field | On-screen keyboard does **not** permanently hide the focused field or sticky save/submit | |
| F3 | Dismiss keyboard; scroll list | Entries readable; no clipped controls under home indicator | |

### Step G — Mobile bottom navigation

| # | Action | Expected | Result |
|---|---|---|---|
| G1 | Tap each bottom item: Dashboard, Signals, Plan, Portfolio | Correct route each time; active state sensible | |
| G2 | Confirm bar clears home indicator | Icons/labels not obscured by safe-area | |

### Step H — Menu sheet

| # | Action | Expected | Result |
|---|---|---|---|
| H1 | Tap **Menu** (`mobile-menu-button`) | Sheet opens (`More destinations`); backdrop dims | |
| H2 | Tap outside / backdrop to dismiss | Sheet closes; focus returns sensibly | |
| H3 | Re-open; navigate to Validate, Journal, Analytics, Settings | Each destination works; sheet closes on navigate | |

### Step I — Safe-area and landscape

| # | Action | Expected | Result |
|---|---|---|---|
| I1 | Portrait: sticky headers / bottom nav / Menu sheet | Clear of notch and home indicator | |
| I2 | Rotate to landscape briefly on Dashboard + one dense page (Portfolio or Analytics) | No permanent clip under notch/status; usable enough to dismiss landscape | |
| I3 | Return to portrait | Layout recovers without broken overlay | |

### Step J — Keyboard and form visibility

| # | Action | Expected | Result |
|---|---|---|---|
| J1 | Login/register fields (if re-test needed) | Focused field remains visible above keyboard | |
| J2 | Journal entry fields | Same; sticky actions remain reachable (scroll if needed) | |
| J3 | Paper-close exit price field (also Step M) | Decimal pad / text field usable; review/confirm not hidden | |

### Step K — Autofill

| # | Action | Expected | Result |
|---|---|---|---|
| K1 | Auth email field | Autofill / Keychain suggestion appears (or document OS restriction) | |
| K2 | Auth password field | Password autofill works without breaking submit | |

*If iCloud Keychain is off, mark **N/A** with note — do not mark PASS.*

### Step L — Pinch zoom and text readability

| # | Action | Expected | Result |
|---|---|---|---|
| L1 | Pinch-zoom in on Dashboard body text | Zoom allowed (viewport must not block pinch) | |
| L2 | Zoom out; check Analytics tab labels + Portfolio metrics | Text remains readable without relying on hover | |

### Step M — Paper-position close with explicit exit price

**Route:** `/positions` (Portfolio bottom tab → secondary nav **Positions**).

| # | Action | Expected | Result |
|---|---|---|---|
| M1 | Open an **open** paper position card | Card shows entry; **Close paper position** available | |
| M2 | Start close → enter an **arbitrary explicit** exit price (e.g. `50123.45` or another non-entry value) | Panel accepts typed price; copy indicates exit is recorded as typed | |
| M3 | Review → Confirm paper close | Confirmation summary shows **your** exit price, not a fabricated/entry default | |
| M4 | After success | Position closed / list updates; realized figures consistent with typed exit; on failure, honest error and position remains open | |

**Seed if needed:** proposal → approval → paper execution → then close. Still paper-only.

### Step N — Command menu using touch

**Known product fact (verify, do not assume fixed):** the TopBar **Search ⌘K** control is `hidden` below the `md` breakpoint, and the desktop sidebar command button is not shown on phone. ⌘K has no iPhone equivalent without a hardware keyboard.

| # | Action | Expected | Result |
|---|---|---|---|
| N1 | Look for any on-screen Search / command-menu control in TopBar, Menu sheet, or elsewhere | If **none** is visible: mark **FAIL** (missing touch affordance) — not PASS | |
| N2 | If a control exists, open command menu with touch | Menu (`command-menu`) opens; destinations tappable | |
| N3 | Navigate via an entry; dismiss | Closes cleanly; lands on correct route | |
| N4 | Optional: hardware keyboard Cmd/Ctrl+K | Only if available; does **not** replace touch evidence | |

### Step O — Kill-switch activate / deactivate dialog

**Control:** TopBar **Kill switch** (`kill-switch-button`) — not Settings, not command menu. **Owner** role required.

| # | Action | Expected | Result |
|---|---|---|---|
| O1 | Tap Kill switch | In-app dialog (`kill-switch-confirm`) — **not** a native `window.confirm` | |
| O2 | Try confirm with empty/short reason | Blocked until reason ≥ ~3 characters | |
| O3 | Enter reason → Activate | Button shows ON; StatusStrip risk critical / blocked; Portfolio/Positions show **BLOCKED** / kill-switch reason chrome | |
| O4 | Spot-check Plan/workspace messaging | Kill-switch active messaging if applicable | |
| O5 | Deactivate via same dialog + reason | Returns to inactive; BLOCK chrome clears; paper workflow usable again | |
| O6 | Cancel path | Cancel dismisses without changing state | |

If non-owner: record API/UI error (*owner role required*) as **BLOCKED** for this step, not PASS.

### Step P — Messages deep links

Send yourself HTTPS links via **Messages (iMessage)**, then tap from the thread (not only paste into Safari).

Suggested templates (replace IDs and host):

```
{FRONTEND}/tradingview-signals?signal=<SIGNAL_ID>
{FRONTEND}/journal?entry=<ENTRY_ID>
{FRONTEND}/knowledge?document=<DOCUMENT_ID>   # optional
{FRONTEND}/analytics?tab=validation
```

| # | Action | Expected | Result |
|---|---|---|---|
| P1 | Tap Signals `?signal=` from Messages | Opens correct signal **or** explicit “not found” — never a silent wrong signal | |
| P2 | Tap Journal `?entry=` from Messages | Highlights correct entry **or** stale-entry honesty (“not found in most recent N”) — never unrelated entry | |
| P3 | Analytics `?tab=` | Correct tab selected (`aria-selected` / visible) | |
| P4 | Browser back/forward after deep link | Does not open a wrong record | |
| P5 | Auth edge | If session expired: login with `?next=` then return to intended link without loop | |

### Step Q — Portfolio scrolling

| # | Action | Expected | Result |
|---|---|---|---|
| Q1 | Open `/portfolio` | Overview metrics reachable; paper safety honesty visible | |
| Q2 | Scroll full page (charts, closed positions, sections) | Vertical scroll works; wide tables scroll inside wrappers; bottom nav does not hide last content permanently | |
| Q3 | Secondary nav to Positions / Risk | Horizontal secondary nav usable | |

### Step R — Analytics tabs, charts, and filters

**Route:** Menu → **Analytics** → `/analytics`  
**Tabs:** `overview` · `performance` · `setups` · `behaviour` · `validation` · `comparison`

| # | Action | Expected | Result |
|---|---|---|---|
| R1 | Open Overview + at least one other tab (e.g. Performance or Comparison) | Tab switch works; URL `?tab=` updates; no jump that loses context badly | |
| R2 | Charts | Render or honest empty/degraded state; no blank crash | |
| R3 | Filters | Mobile disclosure **Show filters** / **Hide filters** works; controls tappable | |
| R4 | Pinch/readability | Labels and values readable | |

---

## 3. Evidence requirements

Copy one block **per step** (or keep a spreadsheet with the same columns). Incomplete evidence ⇒ step cannot be claimed PASS.

### Evidence log template (repeat)

```
STEP ID:           (e.g. M3)
RESULT:            PASS | FAIL | BLOCKED | N/A
ROUTE:             (e.g. /positions)
EXACT TIME:        YYYY-MM-DD HH:MM:SS TZ
DEVICE MODEL:      …
iOS VERSION:       …
SAFARI VERSION:    …
SCREENSHOT / VIDEO: (filename or Photos album note)
VISIBLE ERROR:     (exact UI text, or None)
REPRO STEPS:       1) … 2) … 3) …
NOTES:             …
RELATED FP2 ID:    (if known, else None)
```

### Minimum evidence set

| Area | Minimum capture |
|---|---|
| Auth + posture | Screenshot of login/register + post-login PAPER / real-trading-disabled chrome |
| Bottom nav + Menu | Screen recording or photos of bar + open sheet |
| Paper close | Screenshots of typed exit price, review, and post-close result |
| Kill switch | Activate dialog, BLOCK on Portfolio, deactivate result |
| Deep links | Photo of Messages thread link + resulting Safari record/state |
| Portfolio / Analytics | Scroll position showing charts/tabs; filters open once |
| Failures | Screenshot of exact error + repro notes |

---

## 4. Bug-report template

Use one report per distinct defect.

```markdown
### Bug: <short title>

- **Severity:** P0 (blocks paper evaluation) | P1 | P2 | P3
- **Expected behaviour:**
- **Actual behaviour:**
- **Route:**
- **Device details:** model / iOS / Safari
- **Exact time:**
- **Reproduction steps:**
  1.
  2.
  3.
- **Screenshot / video reference:**
- **Visible error text:**
- **Blocks paper evaluation?** yes / no
- **Related FP2 ID:** (e.g. FP2-001, FP2-109) or unknown
- **Intended redeploy `main` SHA:**
- **Staging backend git_sha:**
- **Frontend URL:**
```

**Severity guidance:**

| Severity | Examples |
|---|---|
| P0 | Fabricated exit price; false-empty hiding errors; kill switch fails to block; live-trading implication; data loss |
| P1 | Deep link opens wrong record; keyboard permanently hides confirm; BLOCK chrome missing when kill switch on |
| P2 | Menu sheet animation glitch; landscape clutter; filter disclosure awkward |
| P3 | Cosmetic label mismatch |

---

## 5. Final validation summary

Fill after the session. One page.

| Metric | Count / value |
|---|---|
| Total steps executed | |
| Total **passed** | |
| Total **failed** | |
| Total **blocked** / N/A | |
| Blocking defects (P0 / paper-eval blockers) | |
| Non-blocking defects | |
| Paper posture verified | yes / no |
| Paper close verified (explicit exit price) | yes / no |
| Kill switch verified (activate + BLOCK + deactivate) | yes / no |
| Deep links verified (from Messages) | yes / no |
| Safe-area / keyboard / autofill acceptable | yes / no / partial |
| Command menu touch usable | yes / no / fail-missing-affordance |
| Portfolio scroll OK | yes / no |
| Analytics tabs/charts/filters OK | yes / no |
| **Recommendation** | **ready** / **blocked** |

**Recommendation rules:**

- **ready** — no P0; paper posture, paper close, kill switch, and Messages deep links all **passed** with evidence; remaining issues are explicitly non-blocking.
- **blocked** — any P0, any of the four critical drills failed/blocked, staging not on intended revision, or evidence missing for a claimed pass.

```
SUMMARY NOTES:
____________________________________________________________________
____________________________________________________________________
```

---

## 6. PR #41 completion procedure

After iPhone evidence is collected (this pack), complete PR #41 as follows. **Do not merge PR #41 from this documentation PR.**

1. **Send evidence to ChatGPT**  
   Package: filled §3 logs, §4 bug reports (if any), §5 summary table, screenshots/recordings index, device/iOS/Safari, staging `git_sha`, frontend URL, recommendation ready/blocked.

2. **Resume the same PR #41 Cursor agent when available**  
   Stable references only (do not depend on a temporary agent-session URL):
   - PR: https://github.com/Fejjii/AlphaTrade-AI/pull/41  
   - Branch: `docs/at040-final-polish-readiness-audit`  
   Resume the **same** PR #41 Cursor agent session if it is still available; otherwise start a successor agent on that branch/PR with the same instructions. This pack must remain usable after any prior session expires.  
   Instruct the agent to update **only** the audit document’s staging (§4) and physical iPhone (§5) sections from the supplied evidence — no production code, no deploy, no drive-by refactors.

3. **Update staging / iPhone sections in the audit**  
   Record honest outcomes: redeploy SHA confirmation (latest approved `main` at deploy time), each checklist item pass/fail with evidence references. Never mark physical items passed from browser emulation or viewport simulation.

4. **Rerun exact-head CI**  
   On the updated PR #41 HEAD, confirm the full GitHub Actions workflow is green at that exact SHA (all jobs). Documentation-only changes should still get a clean exact-head run recorded in the PR body.

5. **Independent review**  
   Separate human/agent review of the updated audit claims vs attached evidence.

6. **Merge PR #41 only after both gates are complete**  
   Gates: (a) staging validation honestly recorded against redeployed revision; (b) physical iPhone evidence recorded. If recommendation is **blocked**, keep PR #41 open and fix or waive with explicit human decision — do not merge on silent gaps.

---

## 7. Out of scope / reminders

- This pack does **not** authorize deployment, merge, live trading, or edits to production application code.
- Automated readiness scripts (`scripts/readiness-browser-validation.sh`, Playwright) remain useful pre-checks; they do **not** close §5 physical validation.
- If staging redeploy is still pending, execute only against the redeployed environment — or stop and report **BLOCKED** with the behind-SHA evidence.

---

## Appendix A — Quick route cheat sheet

| Label | Path |
|---|---|
| Login | `/login` |
| Register | `/register` |
| Dashboard | `/` |
| Signals | `/tradingview-signals` |
| Plan | `/workspace` |
| Validate | `/paper-validation` |
| Journal | `/journal` |
| Portfolio | `/portfolio` |
| Positions (paper close) | `/positions` |
| Risk | `/risk` |
| Analytics | `/analytics` |
| Knowledge | `/knowledge` |
| Settings | `/settings` |

## Appendix B — Suggested Messages deep-link scratchpad

```
SIGNAL_ID=
ENTRY_ID=
DOCUMENT_ID=
FRONTEND=https://alpha-trade-ai-eight.vercel.app

Signals:   $FRONTEND/tradingview-signals?signal=$SIGNAL_ID
Journal:   $FRONTEND/journal?entry=$ENTRY_ID
Knowledge: $FRONTEND/knowledge?document=$DOCUMENT_ID
Analytics: $FRONTEND/analytics?tab=performance
```
