# AT-040 — Final Cross-Product, Premium UI, Mobile and Paper-Readiness Audit

Status: **FINAL AUDIT — based on the fully merged product.** All Portfolio/Risk, Knowledge,
and Analytics workstreams (PRs #36, #37, #38, #42–#49) are merged; every finding below was
verified against merged `main` and, where marked *(runtime)*, against the rendered
production build. No PROVISIONAL or BLUEPRINT items remain.

| Field | Value |
|---|---|
| Workstream | Final Cross-Product, Premium UI, Mobile and Paper-Readiness Audit |
| Audit branch | `docs/at040-final-polish-readiness-audit` (PR #41) |
| Audited base | `main` @ `2a5615ed0709f7aebea39de95758fadd1b12abb1` |
| Method | Source verification of every claim **plus** rendered inspection of the production build (`next build` + `next start` against the local paper backend) at 390 px, 768 px, and 1280 px |
| Scope of this PR | This document only. No production code changes. |

Environment for the rendered inspection: production frontend build, FastAPI backend in
paper posture (`GET /health` returned `execution_mode="paper"`,
`real_trading_enabled=false`), seeded with a real paper cycle (registration → chat proposal
→ approval → paper execution → close → journal entry). 26 routes × 3 viewports were
screenshotted and measured (overflow, heading structure, request counts, console/HTTP
errors); key flows were exercised interactively.

---

## 1. Executive verdict

The merged product is close to a professional paper-first launch. The rendered inspection
confirms a genuinely strong baseline: **zero horizontal page overflow on all 26 audited
routes at all three viewports**, exactly one `h1` per page (one exception), no console
errors or failed requests anywhere, honest empty/loading/error/insufficient states across
the new Analytics hub and Portfolio command centre, verified paper posture on every screen,
56 px bottom-navigation touch targets, and question-led section titles that make each
surface's purpose clear.

Three findings block launch quality (P0):

1. **Paper close fabricates the exit price.** `/positions` closes paper trades at
   `entry_price ?? "1"` with no user input, writing false realized PnL into the same stored
   data that Portfolio and Analytics report (`frontend/src/app/(app)/positions/page.tsx`
   L39–42).
2. **`/positions` renders "No positions" while loading and after failed loads** — the exact
   false-empty class already fixed on `/audit` and `/invitations` in PR #44, still present
   on this route (L26–52).
3. **The Dashboard's market-watcher summary source is broken by default**: the backend
   calls `MarketWatcherService.get_status()` without the required `user_id`
   (`backend/src/app/services/dashboard_summary_service.py` L173, L411), so every user sees
   a raw Python error string on the Dashboard and Portfolio, and Dashboard shell freshness
   is pinned to "Unavailable" *(runtime-verified)*.

Below P0, the material themes are: a missing product-wide number/currency formatting policy
(raw `10,004.96448` metrics reach the UI), developer-voice copy on premium surfaces
(`GET /journal/statistics · group_by setup buckets`, raw ISO microsecond timestamps,
env-var instructions, snake_case config text), triple-stacked paper-posture chips and
duplicate section navigation that add cognitive load, a handful of known honesty gaps on
older pages (dashboard fallback zeros, unverified billing badge, silent journal/lesson
mutation failures), mobile clipping of audit identifiers, and accessibility polish (skip
link, pinch-zoom, live regions, chart alternatives).

Everything is addressable in four focused PRs without reopening architecture. Trading
safety is intact: risk BLOCK precedence is now correct and tested even when the discipline
source fails (fixed since the previous audit revision), the kill switch is visible and
authoritative, and no path places real orders.

## 2. Resolved since the previous audit revision

Recorded for traceability; these are **closed** and excluded from the register.

| Previous ID | Resolution |
|---|---|
| FPA-001 `/settings/audit` false-empty | Fixed in PR #44 with page tests (`audit/page.tsx` now gates empty state on successful load) |
| FPA-002 `/settings/team` false-empty | Fixed in PR #44 (`invitations/page.tsx` explicit `loading/loaded/failed` state, tested) |
| FPA-107 kill-switch BLOCK hidden when discipline unavailable | Fixed in commit `0ab6069`: all three early-return branches keep `showRiskBlock: true` when the kill switch reports blocked; unit + page tests cover blocked × (absent/failed/missing-snapshot) discipline (`buildRiskPosture.ts` L135–161) |
| `/analytics` stale-data-beside-error | Superseded: the hub was rewritten with per-source slots, request-key isolation, and stale-request guards (`useAnalyticsSources.ts`, `useBehaviourSources.ts`); the remaining instance on `/learning-analytics` is FP2-101 |
| Analytics client missing date params | Fixed: `api.analytics.*` accept `start_date`/`end_date` (`lib/api/index.ts` L478–485) |
| Journal import table overflow | Fixed: wrapper is now `overflow-auto` (`journal/import/page.tsx` L65) |
| Blueprint `format.ts` | Exists as `frontend/src/components/analytics/format.ts` (analytics-local; product-wide policy is FP2-115) |

## 3. Current product readiness estimate

Engineering judgment from this audit; percentages are estimates, not measurements.

| Area | Estimate | Basis |
|---|---|---|
| Analytics hub (6 tabs) | ~90 % | Strong URL/tab/filter architecture, honest source states, extensive tests; gaps are gating polish (FP2-126/127/128) and a11y/tap-target P2s |
| Portfolio & Risk command centre | ~85 % | Excellent honesty design, correct BLOCK precedence; mobile length/order (FP2-124), formatting (FP2-115), chart a11y (FP2-117) |
| Core journey (Dashboard, Signals, Plan, Validate, Journal, Lessons, Knowledge) | ~85 % | Solid states and tests; dashboard backend defect (FP2-003), fallback zeros (FP2-102), deep-link windows (FP2-109) |
| `/positions` | ~50 % | Both P0s live here; no page test; no hub chrome |
| Settings / Billing / Team / Audit | ~75 % | PR #44 closed the two worst defects; remaining: billing badge, dual h1, `$`, build-config posture, audit mobile clipping |
| Shell, navigation, auth | ~85 % | Clean structure, tested; posture lifecycle (FP2-105), skip link/zoom/live region, label drift |
| Test/CI safety net | ~80 % | 41 of 54 routes tested; CI runs six jobs; core gaps: positions/proposals/approvals/market/strategy-lab detail |

**Overall: paper evaluation can begin once PR 1 (P0s + honesty cluster) lands.** PRs 2–4
bring the product to the premium, dependable standard during the evaluation window.

## 4. Rendered inspection results (visual and interaction)

Headline measurements from the production build (26 routes × 390/768/1280 px):

- **Layout integrity:** `document.scrollWidth == clientWidth` on every route at every
  viewport — no page-level horizontal overflow anywhere. The only leaf elements wider than
  the viewport were audit-card identifier spans (FP2-121), two billing `h3`s, and
  performance-chart captions, all clipped or contained.
- **Headings:** exactly one `h1` per page everywhere except `/settings/billing` (two —
  FP2-120).
- **Errors:** zero console errors, zero failed/4xx+ requests across all 78 page loads.
- **Requests:** `/health` is fetched twice on every navigation (AuthContext + AppContext —
  FP2-105); Dashboard makes 19 API calls (FP2-215); `/settings/billing` fetches
  `/usage/quota` twice (FP2-120); Analytics tabs stay in a healthy 7–11 range but always
  include the shared journal+portfolio pair even on Behaviour/Validation/Comparison
  deep links (FP2-127).
- **Touch targets:** bottom navigation 78×56 px (all five slots) — comfortably above 44 px.
  Analytics metric toggles and preset buttons measure below 44 px (FP2-216).
- **Page lengths at 390 px:** Portfolio 6 940 px (~8 screens), Validate 5 175 px,
  Settings/Billing 4 346 px, Settings/Audit 3 823 px, Knowledge 3 628 px, Journal 3 495 px.
  Portfolio's order (posture → risk banner → six "Available" source cards → filters →
  data) pushes account data ~2 screens down (FP2-124).
- **Interaction:** mobile menu sheet opens with dimmed backdrop, four large targets, and
  restores correctly; register → dashboard, plan-trade cycle, paper execution, close, and
  journal capture all completed through the UI against the paper backend; deep links to all
  six Analytics tabs resolve with correct tab state.
- **Posture honesty:** every route displayed verified paper posture; kill-switch state and
  "Real trading disabled" were consistent across shell and pages.

## 5. Route-by-route quality matrix

Ratings: **S** strong · **A** adequate · **W** weak. Columns: Clarity / States & honesty /
Responsive / Accessibility / Tests. *(runtime)* = confirmed in the rendered build.

| Route | Cl | St | Re | A11y | Te | Notes |
|---|---|---|---|---|---|---|
| Auth `(public)` | A | A | A | W | A | Clean *(runtime)*; missing `autocomplete`/error association (FP2-112) |
| `/` Dashboard | S | W | S | A | S | Raw backend error string + permanently failed source *(runtime)* (FP2-003); fallback zeros (FP2-102); 19 calls |
| `/tradingview-signals` | S | S | S | S | S | Exemplary deep-link handling; duplicate shortcut rows *(runtime)* (FP2-125) |
| `/workspace` Plan | A | S | A | A | S | Silent invalid deep-link params (FP2-111) |
| `/paper-validation` | A | S | S | S | S | Best honesty model; ~6 screens tall at 390 px (FP2-212) |
| `/journal` | S | A | S | S | S | Silent mutation failures, unconfirmed delete *(runtime-visible)* (FP2-107) |
| `/lessons` | S | A | S | S | S | Fabricated default rule summary (FP2-108) |
| `/knowledge` | S | S | S | S | S | Deep link limited to loaded window (FP2-109) |
| `/analytics` — all 6 tabs | S | S | S | A | S | Premium architecture *(runtime)*; developer-voice provenance (FP2-122), gating gaps (FP2-126/128), tab heading skip |
| `/journal/statistics`, `/journal/comparison`, `/learning-analytics`, `/strategy-quality` | A | A | A | A | A | Kept as drill-downs; LA stale-beside-error (FP2-101); duplicated formatters (FP2-115) |
| `/portfolio` | S | S | A | A | S | Honest coverage model; raw decimals, ~8 screens at 390 px, duplicated nav+posture chrome *(runtime)* (FP2-115/123/124/125) |
| `/risk` | S | A | A | A | W | Clear config-only role *(runtime)*; zinc styling; no save/reset tests (FP2-213) |
| `/positions` | W | **W (P0×2)** | A | A | — | Fabricated close price + false-empty (FP2-001/002); raw metadata chips *(runtime)*; no test, no chrome |
| `/settings` | A | W | A | A | W | Build config under "Runtime configuration" heading (FP2-104) |
| `/settings/billing` | A | W | A | W | A | Two h1 + double quota fetch *(runtime)*; unverified mock badge; `$`; env-var copy (FP2-103/106/120/122) |
| `/settings/team`, `/settings/audit` | A | S | A→W | A | A | Honesty fixed (PR #44); audit identifiers/JSON clip at 390 px *(runtime)* (FP2-121) |
| `/settings/exchange` | S | S | A | A | A | Correct states; diagnostic chips readable *(runtime)* |
| Shell (nav, top bar, status strip) | S | A | S | A | S | "0 mock" fail-soft (FP2-110); posture lifecycle (FP2-105); skip link/zoom/live region (FP2-113/114); label drift *(runtime)* (FP2-119) |

## 6. Issue register

Every entry: **ID · priority · route · viewport · user impact · evidence · files ·
correction · acceptance criteria · required tests · conflict risk · user input**.

### P0 — blocks safe or truthful use

**FP2-001 — Paper close fabricates the exit price and writes false PnL**
- Route `/positions` · all viewports *(runtime-verified: seeded position closed at its own
  entry price; audit trail recorded `"exit_price": "50637.87", "requested_exit_price":
  "50637.87", "realized_pnl": "4.9644…"` derived from the fabricated price)*
- User impact: closing a paper trade from this UI silently records `exit_price =
  entry_price` (or the literal `"1"` when entry price is missing) with reason "Closed from
  UI". Realized PnL, equity history, Portfolio metrics, and Analytics Performance are then
  built from fabricated numbers — the core honesty guarantee of the paper evaluation is
  broken by a supported UI action. The `try…finally` has no catch, so failures are silent
  too.
- Evidence: `frontend/src/app/(app)/positions/page.tsx` L35–47 (`exit_price:
  current?.entry_price ?? "1"`).
- Files: `positions/page.tsx`, `frontend/src/components/PositionCard.tsx`.
- Correction: require an explicit, validated exit price (numeric input with current entry
  shown), a confirmation step, visible error surfacing, and an honest reason; never default
  to `"1"`.
- Acceptance: close is impossible without a valid user-entered exit price; failed close
  shows an error; the recorded exit price equals the entered value; no fallback literals.
- Tests: new `positions/page.test.tsx` covering validation, confirm, success, API failure.
- Conflict risk: none (no other open work touches this file).
- User input: **No** (objective bug).

**FP2-002 — `/positions` shows "No positions" while loading and after failure**
- Route `/positions` · all viewports
- User impact: on load and on any fetch failure the page asserts an empty account — the
  same false-empty defect class the repo already fixed on `/audit` and `/invitations` in
  PR #44; applying the repo's own standard makes this P0.
- Evidence: `positions/page.tsx` L26–52 (`data?.items.length ? … : <EmptyState title="No
  positions" …/>` renders whenever `data` is null, alongside `LoadingState`/`ErrorState`).
- Files: `positions/page.tsx`.
- Correction: gate list/empty rendering on a successful load (mirror the fixed
  `audit/page.tsx` pattern).
- Acceptance: loading shows only the loading state; failure shows only the error state;
  "No positions" appears only after a successful empty response.
- Tests: loading/error/empty/list cases in the new page test (shared with FP2-001).
- Conflict risk: none. User input: **No**.

**FP2-003 — Dashboard market-watcher source is broken by default; raw Python error reaches the UI**
- Routes `/` and `/portfolio` · all viewports *(runtime-verified: "market_watcher
  unavailable: MarketWatcherService.get_status() missing 1 required keyword-only argument:
  'user_id'" rendered on both pages; Dashboard shell freshness pinned "Unavailable")*
- User impact: a guaranteed `TypeError` on every dashboard-summary request means the
  market-watcher slice of the daily decision loop never works for any user, an internal
  Python signature error is displayed as product copy, and Dashboard freshness reads
  "Unavailable" permanently. The UI stays honest about unavailability, but a
  broken-by-default core source with leaked internals fails any commercial launch bar.
- Evidence: `backend/src/app/services/dashboard_summary_service.py` L173 and L411 call
  `self._market_watcher.get_status(organization_id=…)`;
  `backend/src/app/services/market_watcher_service.py` L107–112 requires keyword-only
  `user_id`. The raw `str(exc)` flows into summary limitations shown by the frontend.
- Files: `backend/src/app/services/dashboard_summary_service.py` (+ its tests); optional
  frontend hardening: sanitize limitation strings before display.
- Correction: pass the requesting `user_id` at both call sites (the route layer has it);
  add a regression test that the market-watcher slice populates; optionally map unexpected
  exception text to a generic "source unavailable" message before it reaches users.
- Acceptance: dashboard summary includes market-watcher status for a seeded user; no raw
  exception text in any UI string; Dashboard freshness reflects real source timestamps.
- Tests: backend unit/integration test for `_market_watcher_status` with a real user;
  existing frontend tests unchanged.
- Conflict risk: none (isolated backend service file). This is the only backend change in
  the programme and is called out explicitly in PR 1.
- User input: **No**.

### P1 — materially harms usability, mobile operation or trust

Format: **ID (was) — title** · route/viewport · impact → correction · acceptance/tests ·
conflict · user input. Viewport is "all" unless stated.

**FP2-101 (FPA-101) — Stale data kept after failed reload; shown unmarked on Learning Analytics**
`/learning-analytics` + shared hook. `useAsyncData` never clears `data` on error
(`frontend/src/hooks/useAsyncData.ts` L14–16); `learning-analytics/page.tsx` L57–59 renders
`ErrorState` and old metrics side by side. → Clear (or explicitly mark stale) on error;
update consumers. Acceptance: no unmarked stale metrics beside an error; hook unit test +
LA page test. Conflict: hook is widely consumed — audit consumer tests in the same PR.
User input: No.

**FP2-102 (FPA-102) — Dashboard discipline fallback invents zeros**
`/`. Fallback seeds `paper_trades_opened_today: 0` etc. (`app/(app)/page.tsx` L239–264)
rendered as "Trades today: 0"/clear badges (`TodaysDisciplineCard.tsx` L66–67) when the
summary source fails. → Per-metric "unavailable" (Validate's `countOrNull` pattern).
Acceptance: unmeasured fields never render as 0/clear; extend `page.fallback.test.tsx`.
Conflict: none. User input: No (objective honesty defect; presentation follows the repo's
established pattern).

**FP2-103 (FPA-103) — "Mock billing mode" asserted before status loads**
`/settings/billing`. `mockMode = data ? … : true` (`billing/page.tsx` L30) shows the badge
during loading/failure. → Tri-state: no badge until loaded; "Billing status unavailable" on
failure. Tests: badge absent in loading/error. Conflict: none. User input: No.

**FP2-104 (FPA-104) — Settings shows build config under a "Runtime configuration" heading; hardcoded safety copy**
`/settings`. `settings/page.tsx` L50–57 (card titled "Runtime configuration", values from
`appConfig` suffixed "(build config)"; no `/health`-derived posture on the page);
`SafetyDisclaimers.tsx` L8–9 asserts paper-only/real-disabled unconditionally. → Render
posture from `useSafetyPosture()` with explicit "unverified" until loaded; retitle the
build card; gate or soften disclaimers. Tests: posture-unknown and paper-confirmed cases.
Conflict: none. User input: No.

**FP2-105 (FPA-105) — Safety-posture lifecycle: fetched once, never refreshed, and fetched twice per navigation**
Shell. `AppContext.tsx` L68–70 loads health/providers/kill-switch on mount only — posture
can be stale all session; *(runtime)* every page load also issues `/health` twice because
`AuthContext.tsx` L35–40 fetches it independently. → Single shared health source; interval
(~60 s) + focus/visibility refetch for health and kill-switch. Acceptance: one `/health`
per load; posture updates without manual refresh; fake-timer context tests. Conflict:
touches AppContext consumed by Portfolio/StatusStrip — land early in PR 1. User input: No.

**FP2-106 (FPA-106) — Hardcoded `$` ignoring `price_currency`**
`/settings/billing`. `QuotaPanel.tsx` L47, `UsageProviderTable.tsx` L29, L63;
`price_currency` exists in `lib/api/types.ts`. → Format via the shared currency formatter
(FP2-115). Tests: non-USD rendering. Conflict: depends on FP2-115. User input: No.

**FP2-107 (FPA-108) — Journal delete/create-lesson fail silently; delete unconfirmed**
`/journal`. `journal/page.tsx` L221–252 (`try…finally`, no catch);
`RecentJournalEntries.tsx` L162–171 (immediate destructive delete) *(runtime: red "Delete
entry" fires instantly)*. → Surface mutation errors; two-step inline confirm. Acceptance:
failed mutation shows an alert; delete requires confirmation. Tests: both paths. Conflict:
none. User input: No.

**FP2-108 (FPA-109) — Lesson accept fabricates a rule summary; silent strategy-load failure**
`/lessons`. `LessonAcceptPanel.tsx` L34–45 (uncaught `loadStrategies`), L53 (`ruleSummary ||
"Lesson-driven rule update"`). → Require non-empty summary; visible load-failure state.
Tests: both. Conflict: none. User input: No.

**FP2-109 (FPA-110) — Deep links resolve only within the first loaded page (Knowledge, Journal)**
`/knowledge?document=`, `/journal?entry=`. `knowledge/page.tsx` L86–116 (early return on
truncation); `journal/page.tsx` L43, L177–185 (limit 50). → Frontend-honest miss message
naming the searched window ("not found in the most recent 50 …"); true fix (get-by-id) is
Deferred FP2-D2. Tests: beyond-window ids. Conflict: none. User input: No.

**FP2-110 (FPA-111) — Provider chip fails soft to "0 mock" / "11 mock" semantics**
Shell. `TopBar.tsx` L28–29, L93–95: failed `/providers/status` renders "0 mock" (healthy-
looking). → Distinct "providers unknown" state. Tests: providers-error case. Conflict:
none. User input: No.

**FP2-111 (FPA-112) — Plan silently drops invalid deep-link context**
`/workspace`. `planContext.ts` L15–29 → null without notice (contrast Signals' explicit
miss alert). → Dismissible "signal context could not be applied" notice. Tests: invalid
`?source=`. Conflict: none. User input: No.

**FP2-112 (FPA-113) — Auth forms lack `autocomplete` and error↔field association**
`(public)` routes, most damaging at 390 px (password managers, mobile keyboards).
`login/page.tsx` L44–61 and siblings. → `autoComplete` attributes + `aria-describedby`/
`aria-invalid` wiring (primitives support it). Tests: attribute assertions. Conflict: none.
User input: No.

**FP2-113 (FPA-114) — No skip link to main content**
Shell, keyboard users. `app/layout.tsx`, `AppShell.tsx` L28. → Visually-hidden-until-
focused skip link to `#main`. Tests: AppShell. Conflict: none. User input: No.

**FP2-114 (FPA-115) — Status strip not announced; pinch-zoom blocked**
Shell. `StatusStrip.tsx` L54–59 (no live region); `app/layout.tsx` L31
(`maximumScale: 1`, WCAG 1.4.4). → `role="status"` polite region; remove the zoom cap.
Tests: role assertion; viewport export. Conflict: none. User input: No.

**FP2-115 (FPA-116) — No product-wide number/currency formatting policy** *(runtime)*
Portfolio shows `10,004.96448`, `4.96448`, `49,644.974` raw; `lib/utils.ts` has only
`formatDate`/`formatDecimal`; `pct`/`percent`/`formatLevel` duplicated across ≥6 pages
(`journal/statistics` L76–81, `journal/comparison` L75–81, `learning-analytics` L22 +
`OutcomeRatesCard` L6, `alerts/review` L26, `watcher` L39, three `paper-validation/*`
pages); `analytics/format.ts` is hub-local. → Promote a shared formatter module (align with
the analytics `format.ts` semantics: null → "—", explicit precision, currency-code aware);
adopt on Portfolio + premium journey; leave analytics internals as-is. Acceptance: no raw
5-decimal metrics on audited routes; null never renders as 0. Tests: formatter units +
portfolio metric rendering. Conflict: touches many files — mechanical; coordinate with
FP2-106. User input: No.

**FP2-116 (FPA-117) — Paper-trades table without horizontal-scroll wrapper**
`/strategy-lab/[id]` panels at 390 px. `strategy/PaperValidationPanel.tsx` L207 (bare
`<table>`; journal-import instance was fixed). → Standard `overflow-x-auto` wrapper.
Tests: class assertion. Conflict: none. User input: No.

**FP2-117 (FPA-118) — Portfolio history charts: color-only PnL, no accessible alternative**
`/portfolio`. `PaperPortfolioCharts.tsx` L57–85 (emerald/rose bars, `title` only, no
`role="img"`/label/table), L116–121 (generic equity label). → Labels + sr-only summary
table + non-color sign markers (match the Analytics chart pattern, e.g.
`DailyPnlChart.tsx` L165–168). Tests: a11y assertions. Conflict: none. User input: No.

**FP2-118 (FPA-119) — Strategy-lab detail swallows failures and double-fetches**
`/strategy-lab/[id]`. L90–107 `.catch(() => null/[])`; duplicate loads; no page test. →
Visible error/unavailable states; consolidate loads; add the missing page test. Conflict:
none. User input: No.

**FP2-119 (FPA-120) — Terminology drift across shell and pages** *(runtime-confirmed)*
Top bar "Analyze" over h1 "Analytics"; secondary "Inbox" vs primary "Signals"; secondary
"Risk & Cooldowns" vs page "Risk settings" vs hub link "Risk settings"; "Profile" vs h1
"Settings"; "Team" vs "Team invitations"; "Billing & plans" vs "Billing & Usage"
(`navigation-config.ts` L85–87, L106, L165, L209, L228, L231; `settings/page.tsx` L43;
`risk/page.tsx` h1). → One term per destination; defaults proposed in §7. Tests:
`navigation-config.test.ts` labels. Conflict: `navigation-config.ts` is otherwise
untouched now — safe in PR 2. User input: **Confirmation of proposed defaults**.

**FP2-120 (FPA-121) — `/settings/billing`: two `h1`s and duplicate quota fetch** *(runtime: h1=2, `/usage/quota` ×2)*
`settings/billing/page.tsx` L10–22 composes `billing/page.tsx` (h1 + quota loader) and
`usage/page.tsx` (h1 + quota loader). → Single `PageHeader` with `h2` sections; hoist one
quota fetch. Tests: new composed-page test (h1 count, single fetch). Conflict: none.
User input: No.

**FP2-121 — Audit identifiers and payloads clip off-screen at 390 px** *(new, runtime)*
`/settings/audit`, 390 px. Resource UUIDs run past the viewport edge and are unreachable
(the shell clips horizontal overflow): `AuditEventCard.tsx` L19–26 renders long unbroken
identifiers in grid `<span>`s without `break-all`/`min-w-0`; the metadata `<pre>` (L28) is
scrollable but the identifier spans are not. → `break-all` on identifier values; `min-w-0`
on grid items. Acceptance: full resource ids readable at 390 px. Tests: class assertions.
Conflict: none. User input: No.

**FP2-122 — Developer-voice copy on premium surfaces** *(new, runtime)*
Analytics (all tabs), `/positions`, `/settings/billing`, `/portfolio`. Users see:
`GET /journal/statistics · group_by setup buckets · win_rate` (`setupGroupCopy.ts`
L30–90 and sibling source labels), `as of 2026-07-28T16:43:30.123937Z` (raw ISO with
microseconds via `ChartFrame.tsx` L73), "This endpoint does not expose a server freshness
timestamp" (`sourceFreshness.ts`), "Journal setup ID is a setup-definition UUID…",
position chips `proposal_id: <uuid>` / `source: paper_execution` (`PositionCard.tsx`),
"Enable `BILLING_ENABLED=true` and Stripe keys…" (`billing/page.tsx` L62–64), and
snake_case "daily_loss_limit is not configured" (portfolio limitations). → Humanize:
formatted timestamps (`formatDate`), plain-language source names with technical detail
behind a tooltip/disclosure, product-voice limitation strings, linked (not raw) proposal
references. Acceptance: no HTTP verbs/paths, raw ISO stamps, env-var names, or snake_case
identifiers in default UI copy on audited routes. Tests: updated copy assertions.
Conflict: touches analytics copy modules — mechanical, isolated to strings. User input: No.

**FP2-123 — Paper-posture chrome stacked three-plus deep** *(new, runtime)*
All routes, worst on `/portfolio` at 390 px: status strip (Paper/PAPER/Real OFF/Risk low)
+ per-page `PaperModeIndicator` above the h1 + a page badge row (PAPER mode /
providers: mock / Real trading disabled / Paper only) + a second Kill switch button + a
safety banner that repeats its own text ("Paper-only simulated portfolio…" twice —
`AccountOverviewPanel`/`PaperPortfolioSafetyBanner` composition). ~5 posture statements
above the fold. → Keep the status strip as the single always-on posture surface; one
compact verified-paper chip in page headers; remove per-page badge rows and the duplicated
banner sentence; one kill-switch control (top bar). Acceptance: ≤2 posture surfaces per
viewport; no duplicated sentences. Tests: updated page tests. Conflict: touches shared
chrome + portfolio — sequence within one PR. User input: **Confirmation of proposed
default** (safety-visibility trade-off).

**FP2-124 — Portfolio hub mobile length and ordering** *(new, runtime)*
`/portfolio`, 390 px: 6 940 px tall (~8 screens); six always-expanded "Available /
complete" source cards (~550 px) and filters precede the first account metric; account
tiles are single-column. → Collapse source availability into a one-line summary chip row
when all sources are healthy (expand on demand / when degraded); move filters below the
account overview; two-column metric tiles at ≥390 px. Acceptance: first account metric
visible within ~1.5 screens; degraded sources still surface automatically. Tests: order/
collapse assertions in portfolio page test. Conflict: portfolio page only. User input: No
(standard progressive-disclosure fix; degraded states remain prominent).

**FP2-125 — Duplicate section navigation with mismatched labels** *(new, runtime)*
`/portfolio` (secondary nav "Overview | Positions | Risk & Cooldowns" **and** hub links
"Portfolio overview | Positions | Risk settings" — `PortfolioHubChrome.tsx` L134–156 vs
`navigation-config.ts` L218–222) and `/tradingview-signals` (secondary nav + in-page
shortcut row `page.tsx` L246–261). → Remove the in-page duplicates (secondary navigation
already covers them) or reduce to contextual links with distinct purpose; align labels with
FP2-119. Acceptance: one navigation row per destination set per page. Tests: updated page
tests. Conflict: overlaps FP2-119 label work — same PR. User input: No.

**FP2-126 — Performance/Comparison keep prior data visible during same-filter reload**
`/analytics?tab=performance|comparison`. Gate is `loading && !source` (`page.tsx` L183;
`ComparisonCharts.tsx` L42–49), so a same-filter retry shows previous figures with no
loading indication (Behaviour/Validation handle this with `retryLoading`; Overview blanks).
→ Apply the `retryLoading` pattern uniformly. Acceptance: reload always shows a loading
state before new/failed data. Tests: same-filter reload cases. Conflict: analytics only.
User input: No.

**FP2-127 — Shared journal+portfolio sources fetched on every Analytics visit**
`/analytics?tab=behaviour|validation|comparison` deep links still trigger the shared
`useAnalyticsSources` pair (`page.tsx` L53–54; hook has no `enabled` flag, unlike
`useSetupAnalyticsSources`). → Add `enabled: tab is overview|performance` (mirroring the
setups hook). Acceptance: no journal/statistics + performance/portfolio requests when
landing on non-overview tabs. Tests: hook/page request assertions. Conflict: analytics
only. User input: No.

**FP2-128 — Insufficient-sample gating gaps on Analytics**
`/analytics`. (a) `RuleComplianceChart.tsx` computes `muted` (L93–102) but never applies it
to bars (L181–186) — insufficient buckets render at full accent; (b) portfolio-fallback
overview tiles hardcode `insufficient: false` (`OverviewStats.tsx` L155–212) even at
`trade_count` 1; (c) win rate renders numerically when confidence is insufficient with only
a caption (`OverviewStats.tsx` L116–123). → Apply muting; derive `insufficient` from
`trade_count` for fallback tiles; de-emphasize insufficient rates consistently. Acceptance:
insufficient data is visually distinct everywhere. Tests: chart/tile insufficient cases.
Conflict: analytics only. User input: No.

**FP2-129 (FPA-122) — Core routes still lack page tests**
`/positions`, `/proposals`, `/approvals`, `/market`, `/strategy-lab/[id]` (plus lower-risk:
`exchange`, `usage`, `watchlist`, `settings/{audit,billing,exchange,team,usage}` shims).
41 of 54 route pages are tested; the untested set includes the route with both P0s. →
Page tests covering loading/error/empty honesty + primary actions. Acceptance: every
trade-adjacent route has a page test. Conflict: `/positions` tests depend on PR 1 fixes.
User input: No.

### P2 — refinement or polish

| ID (was) | Route · viewport | Finding → correction (files) | User input |
|---|---|---|---|
| FP2-201 (FPA-201) | Auth | `mustVerifyEmail` defaults true until `/health` resolves — conservative race (`AuthContext.tsx` L33–40) → initialize from cached posture | No |
| FP2-202 (FPA-202) | Shell | Command menu lacks arrow/Enter listbox semantics (`CommandMenu.tsx`) → combobox pattern | No |
| FP2-203 (FPA-203) | Shell | Kill switch uses `window.confirm`/`prompt` (`KillSwitchButton.tsx` L22–32) → in-app confirm consistent with FP2-107 pattern | No |
| FP2-204 (FPA-204) | Shell | Unused `NotFinancialAdviceBanner` hardcodes paper claim → delete | No |
| FP2-205 (FPA-205) | `/settings` | Email-verified Yes/No color-only; "Provider status snapshot" placeholder card (`settings/page.tsx` L30–34, L60–67) → text+icon; link or remove | No |
| FP2-206 (FPA-206) | `/settings/billing` · 390 | Usage tables scroll-only, `return null` when empty (`UsageProviderTable.tsx` L7, L40) → empty copy; optional card layout | No |
| FP2-207 (FPA-207) | `/workspace` | Long signal UUIDs unwrapped in context banner; AI CardTitle h3 under no h2 (`PlanSummary.tsx` L117; `card.tsx` L21–22) → truncate + heading | No |
| FP2-208 (FPA-208) | `/tradingview-signals` | 503-line page with inline detail; local date formatting; TV hard-fail vs others soft-fail → extract, share formatter, align failure modes | No |
| FP2-209 (FPA-209) | `/journal` | Quick entry prefills BTCUSDT/1h/long (`JournalQuickEntry.tsx` L24–26; 614 lines) → empty defaults; split component | No |
| FP2-210 (FPA-210) | `/knowledge` | Full-wrap URIs dominate cards; semantic source select ignores later URL changes (`KnowledgeSemanticSearch.tsx` L27–29) → clamp; sync | No |
| FP2-211 (FPA-211) | `/lessons` | Accept panel card-swap without focus management; dead `LessonCandidateCard`; local date fn → focus, delete, share | No |
| FP2-212 (FPA-212) | `/paper-validation` · 390 | Hub ~6 screens (runtime 5 175 px) → progressive disclosure below the fold | No |
| FP2-213 (FPA-213) | Cross-page | ~35 local `<h1>`s bypass `PageHeader`; `zinc-*` islands (worst: run-session, backtests, alerts/review, `/risk` L156–287) → migrate premium routes only | No |
| FP2-214 (FPA-214) | API | No timeout/AbortSignal in `apiFetch` (`client.ts` L86–118) → default timeout + abort on unmount | No |
| FP2-215 (FPA-215) | `/` | 19 API calls per visit (runtime; 14 `loadSource` fan-out) → acceptable for paper eval; real fix is Deferred FP2-D1 | No |
| FP2-216 | `/analytics` · 390 | Metric toggles/presets below 44 px (`RuleComplianceChart.tsx` L142–143; `ComparisonChart.tsx` L172–173; `AnalyticsFilterBar.tsx` presets `h-8`) → `min-h-11` | No |
| FP2-217 | `/analytics` | Non-overview tabs skip h1→h3 (no tab-level h2); `<th>` without `scope` in `SetupBucketTable.tsx` L147–155 / `ValidationRankingTable.tsx` L167–178; `SetupGroupToggle` lacks roving tabindex; recharts tooltips hover-only (sr-only tables mitigate) → h2 per tab, `scope="col"`, roving pattern | No |
| FP2-218 | `/analytics` | No page-level partial banner for Behaviour/Validation/Comparison; `strategy_version_id` URL param has no control; dead `ChartTooltip.tsx`; over-broad comparison request key → tidy | No |
| FP2-219 | `/analytics` · 390 | Filters expanded by default push content below fold (runtime) → collapse behind disclosure on mobile | No |
| FP2-220 | `/analytics` | First-load JS 265 kB (recharts; next-largest route 149 kB) — acceptable with dynamic import; monitor | No |
| FP2-221 | `/portfolio` | Liquidated closed positions unreachable (`page.tsx` L87–88 fetches `status:"closed"` only vs `buildClosedPositionRows.ts` L110–112); no status column distinguishes them → fetch/merge both statuses, add status cell (backend list filter already supports it) | No |
| FP2-222 | `/portfolio`, `/risk`, `/positions` | Hub chrome (attention banner, RiskBlock, section nav) only on `/portfolio`; orphaned `PaperPortfolioSummaryCards`; `PanelTitle` h3 collides with symbol h3s; long identifiers untruncated in panels; dual empty-history copy (`PortfolioHistoryPanel.tsx` L70–96 + `PaperPortfolioCharts.tsx`); breakdown `<th>` without scope → share chrome, delete orphan, heading/truncation/copy fixes | Chrome scope: confirmation of default |
| FP2-223 | Shell · 390 | TopBar truncations (`max-w-[11rem]`) and StatusStrip advice truncate can hide safety copy (runtime: acceptable but tight) → verify after FP2-123 consolidation | No |
| FP2-224 | Shell | Two controls answer to accessible name "menu" at 390 px (account menu + bottom-nav Menu; strict-mode collision observed in automation) → distinct aria-labels | No |
| FP2-225 (FPA-218/219) | Misc | FE `HealthResponse` lacks `git_sha`; legacy `billing/usage` page bodies still shipped behind redirects; `settings/usage` client shim flashes → tidy | No |
| FP2-226 | `/analytics` vs shell | Shell freshness pill reads "Freshness unavailable" on Analytics while charts show their own live pills (runtime) → feed shell adapter or suppress on hub | No |

### Deferred — not required for the paper-first launch

| ID | Item |
|---|---|
| FP2-D1 | Backend dashboard aggregate endpoint replacing the 14-call fan-out |
| FP2-D2 | Backend get-by-id endpoints for Knowledge documents / Journal entries (full deep-link resolution beyond the loaded window) |
| FP2-D3 | Provider-status-driven `providerMode` in posture surfaces (replace build-env value) |
| FP2-D4 | Automated visual-regression baseline (Playwright screenshots exist; no diffing) |
| FP2-D5 | Analytics blueprint deferred items (R-multiple distribution, holding-duration buckets, discipline trend, etc.) — analytics backlog, not polish |
| FP2-D6 | Backend parity for liquidated positions in analytics closed-trade helpers (`repositories/positions.py` filters CLOSED only) |

## 7. User confirmations recommended (non-blocking)

No specification questions exist for objective bugs. Three product-voice defaults should be
confirmed (work proceeds on the defaults if unanswered):

1. **Destination naming (FP2-119).** Default: keep verb-based primary labels (Plan,
   Validate, Analyze); rename secondary "Analytics" → "Analytics hub", "Inbox" → "Signals
   inbox", "Risk & Cooldowns" → "Risk settings", "Profile" → "Settings", "Team" → "Team";
   align page h1s accordingly.
2. **Posture chrome consolidation (FP2-123).** Default: status strip is the single
   always-on posture surface; pages keep one verified-paper chip in the header; one
   kill-switch control (top bar); per-page badge rows removed. Alternative: keep per-page
   badges and thin the strip instead.
3. **`/positions` role and chrome (FP2-222).** Default: keep `/positions` as the actionable
   close-trade surface and add the portfolio hub chrome to it and `/risk`. Alternative:
   fold actions into the hub and redirect.

## 8. Final implementation programme

Four focused, non-overlapping PRs in merge order. All are frontend-only except the
two-line backend fix isolated in PR 1. No architecture reopening; no new features.
"Execution effort" is expressed as agent-session scope, not calendar time.

### PR 1 — Safety, data honesty and blocking-mobile fixes *(merge first)*
- Scope: FP2-001, FP2-002, FP2-003 (backend, isolated commit), FP2-101, FP2-102, FP2-103,
  FP2-104, FP2-105, FP2-107, FP2-108, FP2-109, FP2-110, FP2-111, FP2-116, FP2-118,
  FP2-121, FP2-126.
- Likely files: `positions/page.tsx` (+new test), `PositionCard.tsx`,
  `backend/src/app/services/dashboard_summary_service.py` (+test), `hooks/useAsyncData.ts`
  (+consumer test audit), `(app)/page.tsx` + `TodaysDisciplineCard.tsx`,
  `billing/page.tsx`, `settings/page.tsx` + `SafetyDisclaimers.tsx`,
  `contexts/AppContext.tsx` + `contexts/AuthContext.tsx`, `journal/page.tsx` +
  `RecentJournalEntries.tsx`, `lessons/LessonAcceptPanel.tsx`, `knowledge/page.tsx`,
  `layout/TopBar.tsx`, `workflows/planContext.ts` + `workspace/page.tsx`,
  `strategy/PaperValidationPanel.tsx`, `strategy-lab/[id]/page.tsx`,
  `AuditEventCard.tsx`, analytics `page.tsx`/`ComparisonCharts.tsx` (reload gate only).
- Exclusions: no label renames, no visual restyling, no navigation-config changes, no
  analytics copy changes, no chart work.
- Dependencies: none. Branch: `fix/at041-p1-honesty-safety`. Model: Fable 5 (safety
  semantics). Effort: one focused agent session; ~22 files; the invasive edits are
  `useAsyncData` (audit its consumers) and the posture lifecycle (AppContext/AuthContext).
- Test plan: new/extended vitest per finding (listed in the register); backend pytest for
  the dashboard fix; full frontend suite + build; e2e smoke.
- CI: all six jobs green.

### PR 2 — Cross-product consistency, navigation and product voice
- Scope: FP2-106, FP2-115, FP2-119 (+ default naming from §7.1), FP2-120, FP2-122,
  FP2-123 (+ §7.2 default), FP2-125, FP2-127, FP2-128, FP2-204, FP2-225 (legacy page
  bodies).
- Likely files: `lib/utils.ts` (or shared `lib/format.ts` matching analytics semantics),
  `usage/QuotaPanel.tsx` + `UsageProviderTable.tsx`, `navigation-config.ts` (+test),
  `settings/billing/page.tsx` + `billing/page.tsx` + `usage/page.tsx`,
  `analytics/setupGroupCopy.ts` + `sourceFreshness.ts` + `ChartFrame.tsx` +
  `OverviewStats.tsx` + `RuleComplianceChart.tsx` + `useAnalyticsSources.ts`,
  `PortfolioHubChrome.tsx` + posture chrome components, `PositionCard.tsx` (chips),
  `tradingview-signals/page.tsx` (shortcut row), portfolio page metric rendering.
- Exclusions: no data-loading behavior changes beyond FP2-127's `enabled` flag; no chart
  redesign; no mobile reordering (PR 3).
- Dependencies: PR 1 merged (shared files: billing, positions card). Branch:
  `feat/at041-p2-consistency-voice`. Model: Composer 2.5 with Fable 5 review (broad
  mechanical edits). Effort: one to two agent sessions; wide shallow diffs (~30 files);
  highest-contention file is `navigation-config.ts`.
- Test plan: label tests, formatter units (null honesty, currency codes), copy assertions,
  updated page tests; full suite + build.

### PR 3 — Mobile ergonomics, touch and accessibility
- Scope: FP2-112, FP2-113, FP2-114, FP2-117, FP2-124, FP2-202, FP2-203, FP2-205, FP2-206,
  FP2-207, FP2-210, FP2-211, FP2-216, FP2-217, FP2-219, FP2-222 (chrome sharing + heading/
  truncation fixes, per §7.3 default), FP2-224.
- Likely files: `app/layout.tsx`, `AppShell.tsx`, `StatusStrip.tsx`, auth pages,
  `PaperPortfolioCharts.tsx`, `portfolio/page.tsx` + `PortfolioSourceAvailability.tsx`
  (collapse/order), `AnalyticsFilterBar.tsx` + toggle components + tables (`scope`,
  targets, tab h2s), `CommandMenu.tsx`, `KillSwitchButton.tsx`, `MobileBottomNavigation.tsx`
  / TopBar aria-labels, lessons/knowledge/plan touch-ups.
- Exclusions: no navigation-config changes (done in PR 2); no honesty logic; no formatter
  changes.
- Dependencies: PR 2 (labels/chrome consolidated first). Branch:
  `feat/at041-p3-mobile-a11y`. Model: Fable 5. Effort: one to two agent sessions;
  ~25 files; portfolio reorder is the only structural edit.
- Test plan: a11y assertions (skip link, live region, roles, labels, scope), tap-target
  class assertions, portfolio order/collapse tests; full suite + build.

### PR 4 — Regression coverage and staging readiness *(merge last)*
- Scope: FP2-129 (page tests for positions/proposals/approvals/market/strategy-lab detail
  + settings composites), FP2-212/213 touch-ups only where cheap, FP2-221, FP2-226;
  ungate/extend e2e (analytics hub spec into regular smoke where stable; deep-link
  contracts: `?signal=`, `?entry=`, `?document=`, `?tab=`; close-paper flow); execute the
  §9–§10 checklists on staging + iPhone; final readiness update of this document.
- Likely files: new `page.test.tsx` files; `frontend/e2e/*`; `portfolio/page.tsx`
  (liquidated fetch); this document.
- Exclusions: no production behavior changes beyond FP2-221/226; no new features.
- Dependencies: PRs 1–3 merged. Branch: `test/at041-p4-regression-readiness`. Model:
  Fable 5. Effort: one agent session plus a manual staging/iPhone pass; additive tests,
  near-zero production risk.
- Test plan: the tests are the deliverable; full CI + e2e.

## 9. Final readiness checklists

### Mobile checklist (390 px; re-verify after PRs 1–3)
- [ ] No horizontal page overflow on any route *(baseline: passing on all 26 routes)*
- [ ] Audit identifiers/JSON fully readable (FP2-121 fixed)
- [ ] Portfolio: first account metric within ~1.5 screens; source cards collapsed when
      healthy (FP2-124)
- [ ] All tap targets ≥44 px including analytics toggles/presets (FP2-216) *(baseline:
      bottom nav 56 px passing)*
- [ ] Journal quick entry: sticky save clears bottom nav; keyboard never hides validation
      *(baseline: passing)*
- [ ] Analytics filters collapsed behind disclosure; tab bar wraps cleanly (FP2-219)
- [ ] Paper close flow requires exit price and confirmation on a phone (FP2-001)
- [ ] Menu sheet: opens, traps focus, Escape closes, targets ≥44 px *(baseline: passing)*
- [ ] Long identifiers (signal UUIDs, source URIs, symbols) wrap or truncate everywhere

### Desktop checklist (1280 px)
- [ ] Sidebar + secondary nav + content alignment consistent on all premium routes
      *(baseline: passing)*
- [ ] One `h1` per page including `/settings/billing` (FP2-120)
- [ ] No raw backend error strings anywhere (FP2-003) — check Dashboard + Portfolio
      limitations
- [ ] Charts readable with formatted timestamps and human source names (FP2-122)
- [ ] Command menu keyboard complete (FP2-202); kill-switch confirm in-app (FP2-203)
- [ ] No duplicate section-nav rows (FP2-125); labels match §7.1 decisions

### Accessibility checklist
- [ ] Skip link present and functional (FP2-113)
- [ ] Pinch-zoom enabled — no `maximumScale: 1` (FP2-114)
- [ ] Status strip announces posture changes politely (FP2-114)
- [ ] Auth forms: `autocomplete`, `aria-describedby` error wiring (FP2-112)
- [ ] Portfolio charts: `role="img"`, labels, sr-only data alternative, non-color sign
      (FP2-117) *(baseline: analytics charts already pass)*
- [ ] Tables: `scope="col"` on all header cells (FP2-217, FP2-222)
- [ ] Heading order without skips on analytics tabs and portfolio panels (FP2-217/222)
- [ ] Unique accessible names for the two "menu" controls (FP2-224)
- [ ] Focus visible on every interactive element *(baseline: global focus-visible ring
      present)*; reduced motion respected *(baseline: skeletons + charts pass)*

### Cross-product consistency checklist
- [ ] One name per destination across sidebar, secondary nav, top bar, mobile nav, and h1
      (FP2-119)
- [ ] One shared number/currency/percent formatter; no raw 5-decimal metrics (FP2-115)
- [ ] Posture chrome consolidated per §7.2 (FP2-123)
- [ ] `states.tsx` primitives used for loading/error/empty on all premium routes
      *(baseline: mostly passing; positions fixed in PR 1)*
- [ ] Product-voice copy only — no HTTP paths, env vars, snake_case, raw UUIDs as labels
      (FP2-122)
- [ ] `PageHeader` + tokens on premium routes; zinc islands limited to legacy/advanced
      pages (FP2-213)

### Data-honesty and paper-safety checklist
- [ ] `GET /health` on the target env returns `execution_mode="paper"`,
      `real_trading_enabled=false`; strip shows confirmed PAPER *(baseline: passing)*
- [ ] Kill-switch activate → BLOCK visible on shell + portfolio (including with discipline
      source down) → deactivate → recovery *(baseline logic: passing, tested)*
- [ ] Paper close records only user-entered exit prices (FP2-001); realized PnL derives
      from real inputs
- [ ] No failed source anywhere renders as zero/empty success (FP2-002 closes the last
      known instance)
- [ ] Loading, unavailable, empty, insufficient, and stale are visually distinct on every
      analytics tab *(baseline: passing except FP2-126/128)*
- [ ] Freshness timestamps humanized but truthful; missing server timestamps disclosed
      *(baseline: disclosed, wording via FP2-122)*
- [ ] Dashboard fallback never invents zeros (FP2-102); billing badge only after verified
      status (FP2-103)
- [ ] No real-trading, withdrawal, transfer, or leverage controls anywhere *(baseline:
      passing)*

### Staging / iPhone validation checklist (execute in PR 4)
- [ ] Staging env: `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`,
      `PROVIDER_MODE=fallback`, non-live `EXCHANGE_MODE`; `render.yaml` placeholders only
- [ ] Full CI green on `main` (backend, deployment-safety, frontend, evaluation,
      docker-build, e2e-smoke)
- [ ] On a physical iPhone (Safari): register/login, complete one full daily loop
      (Dashboard → Signals → Plan → Validate → Journal), close a paper trade with an
      explicit exit price, review Portfolio and two Analytics tabs
- [ ] Safe-area insets correct (notch/home indicator); keyboard behavior on journal +
      login forms; pinch-zoom works
- [ ] Kill-switch drill from the phone; posture chips update within the refresh interval
- [ ] Deep links from a message app resolve (signal, journal entry, knowledge document,
      analytics tab); back/forward never opens a wrong record
- [ ] No console errors in remote inspection during the walk

### Feature-freeze definition
Feature freeze is in effect when PR 1 merges and lasts through the paper evaluation:
- Allowed: PRs 2–4 as scoped here, test additions, copy/label fixes, defect fixes filed
  against register IDs, and documentation.
- Not allowed: new routes, new backend capabilities, new charts/metrics, navigation
  restructuring beyond §7.1, dependency additions, or schema changes.
- Any exception requires an explicit human decision recorded in `.ai/DECISIONS.md`.

### Paper-evaluation readiness definition
The product is ready to start the two-week paper evaluation when:
1. PR 1 is merged (all three P0s closed with tests) and full CI is green on `main`.
2. The data-honesty and paper-safety checklist passes on staging.
3. The kill-switch drill has been performed once end-to-end.
4. The evaluation protocol is agreed (active signal sources, in-scope strategies, journal
   discipline expectations, daily review loop) with the explicit statement that the
   evaluation measures process discipline and product dependability — no profitability
   claims.
5. Defect triage rule is agreed: only new P0s interrupt the window; other findings are
   filed against this register.
PRs 2–4 are strongly recommended before the window but may land during it (they do not
change data semantics).

## 10. Final definition of done

AT-040 final polish is done when all of the following hold:

1. PRs 1–4 are merged in order with full CI green after each; every P0 and P1 in §6 is
   closed or explicitly deferred by a human with its register ID recorded in
   `.ai/DECISIONS.md`.
2. The three §7 defaults are confirmed (or explicitly changed) and reflected in the code
   and in `.ai/DECISIONS.md`.
3. All six §9 checklists pass, including the staging/iPhone pass, with results recorded.
4. Safety invariants re-verified unchanged: paper-only posture from runtime `/health`,
   kill-switch and risk BLOCK authoritative and visible under all source-failure
   combinations, real trading disabled, and no UI path that fabricates stored trading data
   (FP2-001 closed).
5. Route matrix (§5) re-scored with no W remaining in the States/Honesty column.
6. This document's readiness estimates updated to final and the audit PR approved by a
   human reviewer.
7. The paper evaluation is unblocked per §9's readiness definition; live trading remains
   disabled throughout.
