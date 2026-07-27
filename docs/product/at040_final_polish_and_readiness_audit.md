# AT-040 — Final Product Polish and Readiness Audit

Status: **DRAFT FOR REVIEW — NOT FINAL.** Final readiness conclusions require PR #37
(Portfolio/Risk) and PR #38 (Analytics blueprint) to merge to `main` first. Provisional
and blueprint-scoped findings are explicitly marked below.

| Field | Value |
|---|---|
| Workstream | AT-040 Final Product Polish and Readiness Audit |
| Audit branch | `docs/at040-final-polish-readiness-audit` |
| Audited base | `main` @ `686f6060679695e2943a9cf9ac1bb514e0de53cc` |
| PR #36 (Knowledge hub) | **MERGED** 2026-07-27, branch `feat/at040-knowledge-hub`, head `a4aed6fc9913ae2c5bc6cf8d300ff56eab4b2495` |
| PR #37 (Portfolio/Risk) | **OPEN**, branch `feat/at040-portfolio-risk-command-centre`, head `d30e4feb3799c42aa528a97af391ea0db464b266` — findings marked **PROVISIONAL** |
| PR #38 (Analytics blueprint) | **OPEN**, branch `docs/at040-analytics-charts-blueprint`, head `e82d4fc3287a693ea755901e01e2b5d868ee8ecb` — findings marked **BLUEPRINT/PLANNED** |
| Scope of this PR | This document only. No production code changes. |

Method: every finding below was verified against actual repository files (main at the base
SHA above; PR branches read-only at their heads). File paths and line numbers refer to
those revisions. Nothing in this document is derived from PR descriptions alone.

---

## 1. Executive verdict

AlphaTrade's premium frontend is close to paper-evaluation readiness. The core journey
(Dashboard → Signals → Plan → Validate → Journal → Lessons → Knowledge) is well built:
navigation is centralized and consistent (`frontend/src/components/layout/navigation-config.ts`),
loading/empty/error/partial states are mostly explicit and honest, paper posture is verified
fail-closed from `GET /health` (`frontend/src/contexts/AppContext.tsx`,
`frontend/src/components/ui/paper-mode-indicator.tsx`), risk BLOCK has no override UI
(`frontend/src/components/ui/risk-block.tsx`), and the strongest pages (Validate, Knowledge,
Lessons) have exemplary "unavailable ≠ empty ≠ zero" handling with deep test coverage.

The remaining gaps are concentrated and fixable in three small PRs:

- **Two P0 data-honesty defects** on admin surfaces: `/settings/audit` and `/settings/team`
  render "No audit events" / "No invitations yet" while loading or after a failed fetch
  (`frontend/src/app/(app)/audit/page.tsx` L20–27,
  `frontend/src/app/(app)/invitations/page.tsx` L13–31).
- A cluster of **P1 honesty/safety-display issues**: stale metrics rendered beside an error
  after failed reloads (`frontend/src/hooks/useAsyncData.ts` keeps `data` on error), the
  Dashboard discipline fallback that invents zeros, build-time execution mode shown as if
  runtime on `/settings`, an unverified "Mock billing mode" badge, hardcoded `$` symbols,
  swallowed mutation errors in Journal/Lessons, and shell safety posture that is fetched once
  and never refreshed.
- **P1 accessibility and responsive gaps**: no skip link, `maximumScale: 1` blocks pinch
  zoom, missing `aria-live` on the status strip, missing `autocomplete` on auth forms, two
  tables without horizontal-scroll wrappers, and color-only daily-PnL bars in the portfolio
  charts.
- **Provisional (PR #37)**: one P1 — `buildRiskPosture` early-returns hide the portfolio
  hub's RiskBlock when the discipline source fails even if the kill switch reports
  `execution_blocked=true` (the shell StatusStrip and KillSwitchButton still show it, so the
  BLOCK is not hidden app-wide).

Nothing found weakens backend trading safety: `EXECUTION_MODE=paper` posture, kill-switch
enforcement, and real-trading-disabled are backend-authoritative; all findings are frontend
display/honesty/polish issues.

## 2. Current product readiness estimate

Estimates below are engineering judgments from this audit, not measurements. They assume the
backend paper stack is already staging-validated (out of scope here).

| Area | Estimate | Basis |
|---|---|---|
| Core journey (Dashboard, Signals, Plan, Validate, Journal, Lessons, Knowledge) | ~85–90 % ready | Strong states/tests; residual P1s are honesty polish (fallback zeros, deep-link windows, label drift) |
| App shell, navigation, auth entry | ~85 % ready | Nav complete and tested; P1s: skip link, aria-live, zoom, autocomplete, posture refresh |
| Settings / Billing / Team / Audit | ~65 % ready | Both P0s live here, plus mock-badge, build-config posture, `$` hardcoding, weak tests |
| Portfolio & Risk | **PROVISIONAL** (~80 % on PR #37 branch) | Strong honesty design; one P1 (kill-switch visibility under discipline failure) + P2s; re-audit after merge |
| Analytics | **BLUEPRINT/PLANNED** | Current `/analytics` is a different product surface (proposal-flow analytics) with the weakest state handling in the premium journey; replacement follows the approved 4-PR blueprint (PR #38), not these polish PRs |
| Test/CI safety net | ~75 % ready | CI runs lint+typecheck+vitest+build+e2e smoke; 15 of 54 routes lack page tests, including `/positions`, `/proposals`, `/approvals`, `/risk`, `/market` |

Overall: **paper evaluation can start after PR A (blockers) lands**; PR B/C raise the product
to a professional, dependable standard during the evaluation window.

## 3. Route-by-route quality matrix

Ratings: **S** strong · **A** adequate · **W** weak. Columns: Clarity / States & honesty /
Responsive / Accessibility / Tests.

| Route (nav label) | Cl | St | Re | A11y | Te | Notes |
|---|---|---|---|---|---|---|
| Auth entry `(public)/login`, `register`, … | A | A | A | W | A | Errors `role="alert"`; missing `autocomplete`, error↔field association (FPA-113) |
| `/` (Dashboard) | S | A | S | A | S | One clear question + attention queue; discipline fallback zeros (FPA-102); 14-call fan-out (FPA-131) |
| `/tradingview-signals` (Signals) | S | S | A | S | S | Exemplary deep-link miss handling; label drift "Signals/Inbox" (FPA-120); 503-line page (FPA-134) |
| `/workspace` (Plan) | A | S | A | A | S | Safety strip + AI assist compete with plan summary; silent invalid deep-link params (FPA-112) |
| `/paper-validation` (Validate) | A | S | S | S | S | Best honesty model in repo; hub density is high (FPA-122) |
| `/journal` (Journal) | S | A | S | S | S | Sticky save clears bottom nav; delete/create-lesson errors swallowed, no delete confirm (FPA-108) |
| `/lessons` (Lessons) | S | A | S | S | S | Fabricated default rule summary on accept (FPA-109) |
| `/knowledge` (Knowledge, PR #36) | S | S | S | S | S | Deep link limited to first 50 docs; param is `document` not `id` (FPA-110) |
| `/analytics` (Analyze) | W | W | A | A | W | Proposal-flow analytics, easily confused with Journal Statistics/Learning Analytics; stale-data-beside-error (FPA-101); happy-path test only. Superseded by Analytics blueprint — do not polish beyond FPA-101 |
| `/learning-analytics` | A | A | A | A | A | Same stale-data pattern; dimension state not URL-synced |
| `/journal/statistics`, `/journal/comparison` | A | S | A | A | A | Null-safe formatting; duplicated `pct`/`num` helpers (FPA-116) |
| `/portfolio` (Portfolio) — **PROVISIONAL PR #37** | S | S | S | A | S | Command centre with strong source-availability honesty; kill-switch visibility hole when discipline fails (FPA-107) |
| `/risk` — **PROVISIONAL PR #37** | A | A | A | A | W | Settings form only; still `zinc-*` styling; no save/reset tests |
| `/positions` (legacy) | A | A | A | A | W | Duplicates hub open-positions read view; no page test; product decision needed (US-4) |
| `/settings` (Profile) | A | W | A | A | W | Shows build-time `appConfig.executionMode` as posture (FPA-104); label "Profile" vs h1 "Settings" |
| `/settings/billing` (Billing & Usage) | A | W | A | W | A | Mock badge unverified (FPA-103); two `<h1>`; duplicate QuotaPanel fetch (FPA-121); hardcoded `$` (FPA-106) |
| `/settings/team` | A | **W (P0)** | A | A | W | "No invitations yet" while loading/failed (FPA-002) |
| `/settings/audit` | A | **W (P0)** | A | A | — | "No audit events" while loading/failed (FPA-001); no page test |
| `/settings/exchange` | S | S | A | A | A | Correct early-return states; paper/real badges explicit |
| Shell (sidebar, bottom nav, top bar, status strip) | S | A | S | A | S | Posture fetched once, no refresh (FPA-105); "0 mock" on provider failure (FPA-111); no skip link / aria-live (FPA-114/115) |

## 4. P0/P1/P2 issue register

Issue ID scheme: `FPA-###`. Every entry lists: route · files · evidence · impact ·
severity · correction · tests · conflict risk (#37/#38) · user spec needed.

### P0 — blocks data honesty

**FPA-001 — Failed audit fetch renders as empty success**
- Route: `/settings/audit` (re-export of `/audit`)
- Files: `frontend/src/app/(app)/audit/page.tsx` (L20–27)
- Evidence: `data?.items.length ? … : <EmptyState title="No audit events" />` renders whenever
  `data` is null — including while `loading` is true and when `error` is set. A failed fetch
  shows `ErrorState` **and** "No audit events" simultaneously; the latter is a false claim.
- Impact: a compliance-review surface asserts an empty audit trail that was never loaded.
  Violates "failed sources never appear as zero" and "loading is distinct from unavailable".
- Severity: **P0** (data honesty; narrow blast radius, trivial fix)
- Correction: gate the list/empty branch on a successful load (`!loading && !error && data`);
  render only `LoadingState` while loading, only `ErrorState` on failure.
- Tests: new `audit/page.test.tsx` — loading shows no empty state; error shows no empty
  state; success-empty shows `EmptyState`; success-with-items renders cards.
- Conflict risk: none (#37/#38 do not touch this file).
- User spec: not required.

**FPA-002 — Team invitations show "No invitations yet" while loading / after failure**
- Route: `/settings/team` (re-export of `/invitations`)
- Files: `frontend/src/app/(app)/invitations/page.tsx` (L13–31 and list render)
- Evidence: `invitations` initializes to `[]` with no loading flag; the load error only sets
  `error`. Before the fetch resolves and after a failed fetch, the page shows the empty-list
  copy as apparent fact.
- Impact: owner/admin sees a false "no invitations" state; same honesty violation as FPA-001.
- Severity: **P0**
- Correction: add a `loading`/`loaded` state; show `LoadingState` until resolved; on error
  show `ErrorState` without the empty-list claim.
- Tests: extend `invitations/page.test.tsx` — loading, error, empty-after-load, list-after-load.
- Conflict risk: none.
- User spec: not required.

### P1 — required for a professional, dependable paper product

**FPA-101 — Stale metrics rendered beside error after failed reload**
- Routes: `/analytics`, `/learning-analytics` (pattern is generic to `useAsyncData` consumers
  that render `{error} … {data}` independently)
- Files: `frontend/src/hooks/useAsyncData.ts` (L10–20: `data` is not cleared on error),
  `frontend/src/app/(app)/analytics/page.tsx` (L39–42),
  `frontend/src/app/(app)/learning-analytics/page.tsx` (L56–59)
- Evidence: after a successful load followed by a failed `reload()`, `data` retains the old
  payload; both pages render `ErrorState` and the previous metrics with no staleness marking.
- Impact: outdated analytics presented as current. Rated P1 (not P0) because the error and
  retry control are displayed directly adjacent and the values are real prior data, not
  fabricated — degraded honesty rather than false success.
- Severity: **P1**
- Correction: either clear `data` on error in `useAsyncData`, or expose `isStale` and require
  consumers to render `StaleState` (`frontend/src/components/states.tsx`) around retained
  data. Recommended: clear on error (simplest honest behavior); audit consumers for
  regressions.
- Tests: `useAsyncData` unit test (error clears/flags data); page tests asserting no metrics
  render alongside `ErrorState`.
- Conflict risk: **#38** — Analytics PR 1 rewrites `/analytics`; coordinate so the hook fix
  lands first and the blueprint's `useAnalyticsFilters`/tab work builds on it.
- User spec: not required.

**FPA-102 — Dashboard discipline fallback fabricates zero metrics**
- Route: `/`
- Files: `frontend/src/app/(app)/page.tsx` (L227–268, esp. L235–249),
  `frontend/src/components/TodaysDisciplineCard.tsx` (L66–90)
- Evidence: when the dashboard summary source is unavailable, a legacy composite fallback
  seeds `paper_trades_opened_today: 0` and similar literals; the card then renders
  "Trades today: 0" and clear-looking protection badges. A limitations list is shown
  (L259–264), which partially mitigates.
- Impact: invented counts can read as measured success during outages of one source.
- Severity: **P1**
- Correction: per-metric "unavailable" rendering (as Validate does via `countOrNull`) instead
  of zero literals; keep the card, mark unmeasured fields explicitly. Exact presentation is a
  product choice — see **US-3**.
- Tests: extend `page.fallback.test.tsx` — unavailable fields never render "0"/"clear".
- Conflict risk: none.
- User spec: **US-3** (presentation choice; implementation can proceed with recommended default).

**FPA-103 — "Mock billing mode" badge asserted before status is verified**
- Route: `/settings/billing`
- Files: `frontend/src/app/(app)/billing/page.tsx` (L30: `const mockMode = data ? … : true`,
  L57–65)
- Evidence: while loading or after a failed load, the amber "Mock billing mode" banner shows
  as fact although billing status was never retrieved.
- Impact: unverified posture claim (fails toward the safe claim, but still unverified).
- Severity: **P1**
- Correction: tri-state — no badge until loaded; on failure show "Billing status unavailable".
- Tests: billing page test for loading/error badge absence.
- Conflict risk: none.
- User spec: not required.

**FPA-104 — Settings "Runtime configuration" card shows only build-time values; hardcoded safety copy**
- Route: `/settings`
- Files: `frontend/src/app/(app)/settings/page.tsx` (L50 card titled "Runtime
  configuration"; L56–57 render `appConfig.executionMode` / `appConfig.providerMode`,
  suffixed "(build config)"), `frontend/src/components/SafetyDisclaimers.tsx` (L6–13:
  hardcoded "Paper trading only — no real orders are placed." / "Real trading is disabled."
  with no posture check)
- Evidence: the values are honestly suffixed "(build config)", but the card is titled
  "Runtime configuration" and Settings shows no runtime-verified posture at all — while
  `GET /health` (`execution_mode`, `real_trading_enabled`) is what the rest of the shell
  treats as authoritative (`frontend/src/contexts/AppContext.tsx` L154–161). The disclaimers
  component asserts paper-only/real-disabled as static facts wherever it is mounted.
- Impact: on the page users would check to verify posture, only unverified build values
  appear under a "Runtime" heading; violates "paper mode is only confirmed from verified
  runtime posture".
- Severity: **P1**
- Correction: add runtime posture from `useSafetyPosture()` with explicit "unverified" until
  `/health` resolves; retitle the build-values card "Build configuration". Gate
  `SafetyDisclaimers` assertions on confirmed posture or reword to non-assertive copy.
- Tests: settings page test — posture unknown → "unverified"; paper-confirmed → paper copy.
- Conflict risk: none.
- User spec: not required.

**FPA-105 — Shell safety posture fetched once, never refreshed**
- Route: shell (all pages)
- Files: `frontend/src/contexts/AppContext.tsx` (L50–70: health/providers/kill-switch loaded
  on mount only), `frontend/src/components/layout/TopBar.tsx` (manual refresh L97–104)
- Evidence: no polling or focus-refetch anywhere in the shell; kill-switch activation or
  posture change elsewhere is invisible until manual refresh or reload.
- Impact: the status strip can display stale safety posture for the whole session. Enforcement
  is backend-side, so this does not weaken safety — it weakens the honesty of the display.
- Severity: **P1**
- Correction: modest interval refetch (e.g. 60 s) plus `visibilitychange`/focus refetch for
  `/health` and `/risk/kill-switch`; keep manual refresh.
- Tests: AppContext test asserting refetch on focus/interval (fake timers).
- Conflict risk: **#37 (PROVISIONAL)** — the portfolio hub consumes kill-switch state from
  AppContext; coordinate after merge.
- User spec: not required.

**FPA-106 — Hardcoded `$` in quota/usage cost tables**
- Route: `/settings/billing`
- Files: `frontend/src/components/usage/QuotaPanel.tsx` (L47–48),
  `frontend/src/components/usage/UsageProviderTable.tsx` (L29, L63)
- Evidence: literal `$` prefixes while `frontend/src/lib/api/types.ts` carries
  `price_currency` (~L1357).
- Impact: unsupported currency symbol if backend ever reports non-USD; violates "no
  unsupported currency symbols".
- Severity: **P1**
- Correction: format from `price_currency` via a shared `formatCurrency` (see FPA-116).
- Tests: component tests with non-USD currency.
- Conflict risk: none.
- User spec: not required.

**FPA-107 — PROVISIONAL (PR #37): risk-posture early returns hide kill-switch BLOCK on the hub**
- Route: `/portfolio` (PR #37 branch)
- Files: `frontend/src/components/portfolio/buildRiskPosture.ts` @ `d30e4fe` (L114–186 early
  returns set `showRiskBlock: false`, `tradingState: "unavailable"` without consulting
  `killSwitchResolution`; contrast L70–89 and the doc comment L92–94),
  `frontend/src/app/(app)/portfolio/page.tsx` @ `d30e4fe` (L247:
  `riskBlocked={riskPosture.showRiskBlock}`),
  `frontend/src/components/portfolio/PortfolioHubChrome.tsx` @ `d30e4fe` (L122–132)
- Evidence: if the dashboard/discipline source is loading, failed, or returns no snapshot,
  the hub renders "Risk posture unavailable" and suppresses `RiskBlock` even when
  `killSwitchStatus.execution_blocked === true`. No test covers kill-switch BLOCK + failed
  discipline. Mitigation: the shell `StatusStrip` and `KillSwitchButton` still surface the
  BLOCK, so it is not hidden app-wide.
- Impact: on the page whose job is risk posture, an authoritative BLOCK can be shown as
  merely "unavailable" — contradicts "risk BLOCK remains authoritative".
- Severity: **P1 (PROVISIONAL until #37 merges — fix as a follow-up, not in #37's branch)**
- Correction: in each early-return branch, when `killSwitchResolution === "blocked"`, force
  `tradingState: "blocked"`, `showRiskBlock: true`, and a kill-switch reason.
- Tests: `buildRiskPosture.test.ts` matrix rows for blocked + (null / unavailable / missing
  snapshot) discipline.
- Conflict risk: **directly on #37 files** — must land after #37 merges.
- User spec: not required.

**FPA-108 — Journal mutations fail invisibly; delete has no confirmation**
- Route: `/journal`
- Files: `frontend/src/app/(app)/journal/page.tsx` (L221–253: `handleCreateLesson` and
  `handleDelete` are `try…finally` with **no catch**),
  `frontend/src/components/journal/RecentJournalEntries.tsx` (L162–171)
- Evidence: a failed delete or create-lesson call rejects unhandled while `finally` clears
  the busy flag; nothing is surfaced to the user. Delete fires immediately with no confirm
  step.
- Impact: silent failures; accidental destructive action on user data.
- Severity: **P1**
- Correction: surface mutation errors (`ErrorState`/inline `role="alert"`); add a
  confirmation affordance (see **US-7** for the pattern).
- Tests: journal page tests for failed delete/create-lesson and confirm flow.
- Conflict risk: none.
- User spec: **US-7** (confirmation pattern; can proceed with recommended default).

**FPA-109 — Lesson accept fabricates a rule summary; strategy list failure is silent**
- Route: `/lessons`
- Files: `frontend/src/components/lessons/LessonAcceptPanel.tsx` (L34–45 strategy load with
  no error handling; L49–57 default summary `"Lesson-driven rule update"` when input empty)
- Evidence: as cited.
- Impact: a stored rule change can carry text the user never wrote; a failed strategy fetch
  renders an empty select with no explanation.
- Severity: **P1**
- Correction: require a non-empty summary (validation error instead of default); show a
  load-failure state for strategies.
- Tests: accept-panel tests for both paths.
- Conflict risk: none.
- User spec: not required.

**FPA-110 — Knowledge deep link fails silently beyond the first 50 documents**
- Route: `/knowledge`
- Files: `frontend/src/app/(app)/knowledge/page.tsx` (L86–116 resolution probes only the
  loaded window; early return on truncation),
  `frontend/src/components/knowledge/knowledgeContext.ts` (L31–37: param is `document`)
- Evidence: with more than 50 unfiltered documents, `?document=<id>` for an older record
  cannot resolve; there is no get-by-id fetch. Filter/query exclusion is handled well (a
  dedicated deep-link card is kept), but window truncation is a hard miss.
- Impact: valid deep links (e.g. from Lessons/Journal) dead-end as the corpus grows.
- Severity: **P1** (frontend-honest messaging now; true fix may need a backend get-by-id —
  see Deferred D-2)
- Correction (frontend-only): explicit "not found in the most recent 50 documents" notice
  with the searched-window disclosure; do not present as generic not-found.
- Tests: knowledge page test for beyond-window id.
- Conflict risk: Knowledge files are otherwise frozen for parallel work — small, isolated edit
  after confirming no other open PR touches them (none do today).
- User spec: **US-6**.

**FPA-111 — Top bar provider count fails soft to "0 mock"**
- Route: shell
- Files: `frontend/src/components/layout/TopBar.tsx` (L28–29, L93–95)
- Evidence: when `/providers/status` fails, the null result is treated as an empty array and
  the chip reads "0 mock", which looks like a healthy all-live posture.
- Impact: provider degradation can be misread as health.
- Severity: **P1**
- Correction: distinct "providers unknown" presentation when the source failed.
- Tests: TopBar test with providers error.
- Conflict risk: none.
- User spec: not required.

**FPA-112 — Plan silently ignores invalid deep-link context**
- Route: `/workspace`
- Files: `frontend/src/components/workflows/planContext.ts` (L15–29: invalid `source` →
  null context, no user-facing state); contrast Signals' explicit miss UI
  (`frontend/src/app/(app)/tradingview-signals/page.tsx` L102–119, L288–300)
- Evidence: as cited.
- Impact: a malformed link from Signals/alerts drops context without telling the user;
  inconsistent with the repo's own best pattern.
- Severity: **P1**
- Correction: render a dismissible "signal context could not be applied" notice for present
  but invalid params.
- Tests: workspace page test with invalid `?source=`.
- Conflict risk: none.
- User spec: not required.

**FPA-113 — Auth forms lack `autocomplete` and error↔field association**
- Routes: `(public)/login`, `register`, `forgot-password`, `reset-password`
- Files: `frontend/src/app/(public)/login/page.tsx` (and siblings) — no `autoComplete`
  attributes; errors are `role="alert"` but not linked via `aria-describedby`
- Impact: password managers and screen readers degraded on the product's front door.
- Severity: **P1**
- Correction: `autoComplete="email" / "current-password" / "new-password"`;
  `aria-describedby` + `aria-invalid` wiring (primitives already support it —
  `frontend/src/components/ui/input.tsx`).
- Tests: extend auth page tests for attributes.
- Conflict risk: none.
- User spec: not required.

**FPA-114 — No skip link to main content**
- Route: shell
- Files: `frontend/src/app/layout.tsx`, `frontend/src/components/layout/AppShell.tsx` (L28
  renders `main` with no skip target)
- Severity: **P1** — keyboard users must tab through the sidebar on every page.
- Correction: visually-hidden-until-focused "Skip to content" anchor to `#main`.
- Tests: AppShell test.
- Conflict risk: none. User spec: not required.

**FPA-115 — Status strip changes are not announced; zoom is blocked**
- Route: shell
- Files: `frontend/src/components/layout/StatusStrip.tsx` (L53–108: no `aria-live`/
  `role="status"` on the posture region), `frontend/src/app/layout.tsx` (L27–31:
  `viewport.maximumScale: 1`)
- Impact: screen-reader users don't hear posture/kill-switch changes; low-vision users cannot
  pinch-zoom (WCAG 1.4.4).
- Severity: **P1**
- Correction: `role="status"`/polite live region on the strip; remove `maximumScale: 1`.
- Tests: StatusStrip test for role; snapshot of viewport export.
- Conflict risk: none. User spec: not required.

**FPA-116 — No shared currency/percent formatters; duplicated helpers across ≥13 pages**
- Routes: cross-cutting
- Files: `frontend/src/lib/utils.ts` (only `formatDate`, `formatDecimal`); duplicated local
  helpers: `pct`/`num` in `journal/statistics/page.tsx` (L76–81) and
  `journal/comparison/page.tsx` (L75–81); `percent` in `learning-analytics/page.tsx` (L22–24)
  and `components/learning-analytics/OutcomeRatesCard.tsx` (L6–8); identical `formatLevel`
  in `alerts/review/page.tsx` (L26), `watcher/page.tsx` (L39), and three
  `paper-validation/*` pages; ad-hoc `(x*100).toFixed(0)%` in `analytics/page.tsx` (L63,
  L160); 13 pages call raw `toLocaleString()` instead of `formatDate`
- Impact: drift in rounding/locale behavior; the Analytics blueprint (§ PR 1) already plans a
  shared `format.ts` — polish work should align, not duplicate.
- Severity: **P1** (maintainability with user-visible inconsistency)
- Correction: add `formatPercent`/`formatCurrency`(currency-code aware)/`formatPrice` to
  `frontend/src/lib/utils.ts` (or `lib/format.ts` matching the blueprint name), adopt in the
  premium-journey pages; leave `/analytics` internals to the Analytics workstream.
- Tests: formatter unit tests incl. null-honesty (`null` → "—"/"unavailable", never 0).
- Conflict risk: **#38** — blueprint PR 1 plans `format.ts`; agree on one location/name first.
- User spec: not required.

**FPA-117 — Tables without horizontal-scroll wrappers**
- Routes: `/journal/import`, strategy panels
- Files: `frontend/src/app/(app)/journal/import/page.tsx` (L66),
  `frontend/src/components/strategy/PaperValidationPanel.tsx` (L207)
- Evidence: `<table>` without `overflow-x-auto` wrapper; every other table in the repo has
  one.
- Impact: horizontal page overflow at 390 px.
- Severity: **P1**
- Correction: wrap in `overflow-x-auto` (repo-standard pattern).
- Tests: class-presence assertions in existing tests.
- Conflict risk: none. User spec: not required.

**FPA-118 — Portfolio charts: color-only PnL meaning, no accessible alternative**
- Route: `/portfolio` (component predates PR #37 and is retained by it)
- Files: `frontend/src/components/portfolio/PaperPortfolioCharts.tsx` (L70 emerald/rose sign
  encoding with only `title` tooltips; daily-PnL and drawdown bars lack `role="img"`,
  meaningful `aria-label`, or a hidden data table; equity SVG has generic label L119–120)
- Impact: chart data invisible to screen readers; sign communicated by color alone.
- Severity: **P1**
- Correction: `role="img"` + descriptive labels + visually-hidden summary/table alternative;
  add a non-color sign marker. Note chart *ownership* questions belong to the Analytics
  workstream (US-5); this fix is accessibility-only on the existing component.
- Tests: chart component a11y assertions.
- Conflict risk: **#37 (PROVISIONAL)** — file is composed by the new hub; land after merge.
- User spec: not required.

**FPA-119 — `strategy-lab/[id]` silently swallows fetch failures and duplicates fetches**
- Route: `/strategy-lab/[id]`
- Files: `frontend/src/app/(app)/strategy-lab/[id]/page.tsx` (L90–107:
  `.catch(() => setEligibility(null))` and empty-array fallbacks; duplicate
  paper-validation/eligibility/signals/trades loads across effects)
- Impact: failed paper-validation data renders as "none", violating honesty; wasted requests.
- Severity: **P1**
- Correction: route failures into visible error/unavailable states; consolidate loads.
- Tests: new page test (route currently has none).
- Conflict risk: none. User spec: not required.

**FPA-120 — Terminology drift across navigation and page titles**
- Routes: shell + several pages
- Files/evidence: `frontend/src/components/layout/navigation-config.ts` — primary "Analyze"
  (L105–109) vs secondary "Analytics" (L209) for the same `/analytics`; primary "Signals"
  (L84–88) vs secondary "Inbox" (L165) for `/tradingview-signals`; secondary "Profile"
  (L228) vs `<h1>Settings</h1>` (`settings/page.tsx` L17); nav "Team" (L231) vs h1 "Team
  invitations" (`invitations/page.tsx` L62); link copy "Billing & plans"
  (`settings/page.tsx` L42–44) vs nav "Billing & Usage"; sidebar chip "Paper"/"Unverified"
  (`DesktopSidebar.tsx` L163–166) vs strip "PAPER"/"Execution unverified"
- Impact: same destination answers to different names; erodes premium feel and orientation.
- Severity: **P1**
- Correction: adopt one term per destination (see **US-1/US-2** for the two genuinely
  subjective ones; the rest are mechanical alignment).
- Tests: `navigation-config.test.ts` label assertions.
- Conflict risk: navigation config is frozen for #37/#38 parallel work — land in PR B after
  both merge.
- User spec: **US-1, US-2**.

**FPA-121 — `/settings/billing` composition: two `<h1>`s and duplicate quota fetch**
- Route: `/settings/billing`
- Files: `frontend/src/app/(app)/settings/billing/page.tsx` (L10–21 composes both pages),
  `billing/page.tsx` (L50 h1 "Billing"; QuotaPanel via its loader L19–24),
  `usage/page.tsx` (L31 h1 "Usage"; QuotaPanel again L17–24)
- Impact: broken heading hierarchy; `GET /usage/quota` fetched and rendered twice.
- Severity: **P1**
- Correction: single `PageHeader` "Billing & Usage" with `h2` sections; hoist the quota fetch.
- Tests: new composed-page test (none exists).
- Conflict risk: none. User spec: not required.

**FPA-122 — Missing page tests on core trading routes**
- Routes: `/positions`, `/proposals`, `/approvals`, `/risk`, `/market`, `/strategy-lab/[id]`
  (9 further non-core routes also lack tests: `audit`, `exchange`, `usage`, `watchlist`,
  `settings/audit`, `settings/billing`, `settings/exchange`, `settings/team`,
  `settings/usage`)
- Evidence: 54 `page.tsx` vs 39 `page.test.tsx` under `frontend/src/app/(app)/`.
- Impact: regressions in trade-adjacent surfaces would ship silently; weakens the two-week
  paper evaluation's dependability.
- Severity: **P1** for the six named core routes; **P2** for the rest
- Correction: page tests covering loading/error/empty honesty and primary actions.
- Conflict risk: `/risk` and `/positions` overlap **#37** — write after merge.
- User spec: not required.

### P2 — useful polish, not required before paper evaluation

| ID | Route | Files (evidence) | Finding → correction | Conflict / spec |
|---|---|---|---|---|
| FPA-201 | shell | `frontend/src/contexts/AuthContext.tsx` L33–40, L80–84 | `mustVerifyEmail` defaults `true` until `/health` resolves; unverified-email users logging in within that window are conservatively routed to `/verify-email`. Fail-closed, tiny window → initialize from a cached health value or gate login submit on posture load | none |
| FPA-202 | shell | `frontend/src/components/layout/CommandMenu.tsx` L100–127 | No arrow-key/Enter listbox pattern (Tab-only) → add combobox/listbox semantics | none |
| FPA-203 | shell | `frontend/src/components/KillSwitchButton.tsx` L22–32 | `window.confirm`/`prompt` for a safety-critical action → replace with in-app confirm consistent with US-7 | none |
| FPA-204 | shell | `frontend/src/components/layout/NotFinancialAdviceBanner.tsx` L6–8 | Unused component hardcodes "paper-only" claim → delete (honesty footgun if re-mounted) | none |
| FPA-205 | `/settings` | `settings/page.tsx` L30–34, L60–67 | Email-verified Yes/No is color-only; "Provider status snapshot" is a dead-end placeholder → add text/icon; link or remove | none |
| FPA-206 | `/settings/billing` | `UsageProviderTable.tsx` L13–14, L40–41, L7–8 | Tables `overflow-x-auto` only, `return null` when empty (no empty copy) → mobile card alternative optional; add empty state | none |
| FPA-207 | `/workspace` | `PlanSummary.tsx` L117; `card.tsx` L21–22 | Long signal UUIDs not truncated; AI `CardTitle` (h3) can skip h2 → truncate + heading fix | none |
| FPA-208 | `/tradingview-signals` | `page.tsx` L352–499, L419 | Inline 150-line detail pane; local date formatting; TV source hard-fails while others soft-fail → extract component, use shared formatter, align failure modes | none |
| FPA-209 | `/journal` | `JournalQuickEntry.tsx` L24–26 (614 lines total) | Prefills `BTCUSDT`/`1h`/`long` before input; oversized form component → empty defaults w/ placeholder; split component | none |
| FPA-210 | `/knowledge` | `KnowledgeDocumentCard.tsx` L83–86; `KnowledgeSemanticSearch.tsx` L26–29 | Full-wrap URIs can dominate cards; semantic source select doesn't sync to URL changes after mount → clamp + sync | Knowledge files: verify no open PR touches them first |
| FPA-211 | `/lessons` | `LessonAcceptPanel.tsx` L102–210; `LessonCandidateCard.tsx`; `lessonDisplay.ts` L19–24 | Accept panel is card-swap without focus management; legacy duplicate card component; local date formatting → focus target + remove dead component + shared formatter | none |
| FPA-212 | `/paper-validation` | `page.tsx` (six sections) | Hub density: counts+pipeline+attention+sessions+outcomes+limitations compete → progressive disclosure below the fold | none |
| FPA-213 | cross-page | infra audit: ~35 pages use local `<h1 className="text-2xl font-semibold">`; heavy `zinc-*` vs tokens (worst: run-session 44×, backtests 34×, alerts/review 34×); `DataNumber`/`FreshnessPill`/`ContentContainer` almost unused | Migrate premium-journey pages to `PageHeader` + tokens; leave legacy/advanced pages as-is | `/analytics` excluded (blueprint rewrites it) |
| FPA-214 | cross-page | `frontend/src/lib/api/client.ts` (no timeout/AbortSignal, no non-401 retry) | Hung requests spin forever → add default timeout + abort on unmount | none |
| FPA-215 | `/` | `page.tsx` L58–88 (14 parallel `loadSource` calls) | Heavy first paint; graceful per-source degradation already in place → acceptable for paper eval; real fix is a backend aggregate (see D-3) | none |
| FPA-216 | maintainability | `backtests/[id]/page.tsx` 876 lines (+ only poller, 4 s), `paper-validation/run-sessions/[sessionId]/page.tsx` 686, `alerts/review/page.tsx` 656 | God-pages → split when next touched; no action in polish PRs | none |
| FPA-217 | shell | `TopBar.tsx` L111 `max-w-[11rem]`; `StatusStrip` advice truncate | Aggressive truncation can hide safety copy on small screens → verify at 390 px in visual QA | none |
| FPA-218 | shell | infra audit S5 | FE `HealthResponse` type omits backend `git_sha` → add for support/debug display | none |
| FPA-219 | redirects | `billing/page.tsx`, `usage/page.tsx`, `settings/usage/page.tsx` L10–15 | Redirected legacy paths still ship full page implementations; `/settings/usage` client shim flashes blank → remove after PR B re-exports settle | none |

**PROVISIONAL P2s on PR #37 (re-audit after merge, fix in follow-up if still present):**
liquidated closed positions unreachable (`page.tsx` @ `d30e4fe` fetches `status:"closed"`
only vs `buildClosedPositionRows.ts` L110–112 handling `liquidated`); hub chrome absent on
`/risk` and `/positions` (fragmented command centre); orphaned
`PaperPortfolioSummaryCards`; `PanelTitle` h3 colliding with position-symbol h3s; risk page
`zinc-*` styling; no risk-settings save/reset tests; long identifiers untruncated in new
panels; dual empty-history copy (`PortfolioHistoryPanel` vs `PaperPortfolioCharts`).

**BLUEPRINT/PLANNED (feed into the Analytics workstream, NOT polish PRs):** daily-PnL chart
ownership conflict (Portfolio already charts it; blueprint C1 assigns it to Analytics —
US-5); `api.analytics.*` client functions accept no `start_date`/`end_date` though the
backend supports them; `PerformanceMetrics.win_rate` is non-null and backend zeros empty
sets → Analytics PR 1 must gate on `trade_count`; `/analytics` identity change (proposal-flow
→ performance hub) leaves a behaviour-content gap between blueprint PR 1 and PR 3.

### Deferred — future capability or backend work

| ID | Item | Why deferred |
|---|---|---|
| D-1 | Backend dashboard aggregate endpoint to replace the 14-call fan-out | New backend capability; not polish |
| D-2 | Backend get-document-by-id (Knowledge) and get-entry-by-id (Journal) for deep links beyond the loaded window | Backend routes + tests; frontend honest-miss messaging ships in PR A instead |
| D-3 | Provider-status-driven `providerMode` in the paper banner (replace build-env value) | Needs provider status contract decision |
| D-4 | Analytics implementation (all charts, tabs, filters) | Owned by the approved four-PR blueprint (PR #38) |
| D-5 | Playwright visual-regression baseline beyond the existing screenshot project | Tooling investment; manual QA checklist covers the gap for now |

## 5. Mobile and responsive findings

Verified patterns (390 px / 768 px / 1280 px reasoning from code; confirm visually via §13):

- **Solid foundation.** Bottom nav is 4 destinations + Menu with `min-h-14` targets and
  safe-area insets (`MobileBottomNavigation.tsx` L34, L51); content clears the bar via
  `pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))]` (`AppShell.tsx` L25); Journal's sticky
  save uses `bottom-20` above the bar (`JournalQuickEntry.tsx` L562); Validate/Journal hubs
  add `pb-24`. Knowledge breaks long URIs with `break-all`/`min-w-0`
  (`KnowledgeDocumentCard.tsx` L40–86). Closed positions on PR #37 use the best table
  pattern in the repo: mobile cards + `md:` table (`ClosedPositionsPanel.tsx` L74, L138).
- **P1 — FPA-117**: two tables lack `overflow-x-auto` (`journal/import/page.tsx` L66,
  `PaperValidationPanel.tsx` L207) → horizontal overflow at 390 px.
- **P1 — FPA-115**: `maximumScale: 1` blocks pinch zoom globally (`app/layout.tsx` L31).
- **P2**: usage tables scroll-only with no card alternative (FPA-206); long signal UUIDs
  unwrapped in Plan context banner (FPA-207); `min-w-[8rem]` CTAs can crowd narrow rows
  (`LessonReviewCard.tsx` L194/207, `NeedsJournalingQueue.tsx` L158/166); TopBar/StatusStrip
  truncation may hide safety copy at 390 px (FPA-217); Signals detail `grid-cols-2` is tight
  on narrow phones.
- **Form-heavy mobile screens** (Journal quick entry, auth): labels + `aria-invalid` are in
  place; missing `autocomplete` (FPA-113) also degrades mobile keyboards
  (email/password input modes).

## 6. Accessibility findings

Strengths: `aria-current` across all nav layers; focus traps with Escape in the mobile sheet
and command menu (`hooks/useFocusTrap.ts`); global `:focus-visible` outline
(`globals.css` L26–29); `IconButton` requires `aria-label`; states carry
`role="status"`/`role="alert"` with polite live regions (`states.tsx`); `RiskBlock` is
`role="alert"` with explicit text; badges pair text with color throughout the core journey;
`Tabs` implements full roving-tabindex keyboard semantics; skeletons respect
`motion-reduce`.

Gaps (register references): no skip link (FPA-114); status strip not announced + zoom blocked
(FPA-115); auth form autocomplete/association (FPA-113); command menu keyboard model
(FPA-202); portfolio charts color-only + no text alternative (FPA-118); two-`<h1>` billing
composition (FPA-121); email-verified color-only badge (FPA-205); Plan heading skip
(FPA-207); lessons accept panel focus management (FPA-211); PROVISIONAL PR #37 heading-level
collisions and breakdown tables missing `scope="col"`.

## 7. Data-honesty and safety findings

Posture architecture is sound: paper confirmation derives only from runtime `GET /health`
(`execution_mode` + `real_trading_enabled`), fail-closed until loaded
(`AppContext.tsx` L154–161; `paper-mode-indicator.tsx`); kill-switch state from
`GET /risk/kill-switch` with `execution_blocked`; risk BLOCK UI has no override; failed
kill-switch reads degrade to "Risk unknown", never to "clear"
(`status-strip-state.ts` L101–103). Real trading remains disabled and no finding changes
that.

Violations and weaknesses, strongest first: FPA-001/002 (false-empty on audit/team — P0);
FPA-101 (stale-beside-error); FPA-102 (fallback zeros); FPA-103 (unverified mock-billing
claim); FPA-104 (build config presented as posture + hardcoded disclaimers); FPA-105 (posture
staleness across session); FPA-106 (hardcoded `$`); FPA-111 ("0 mock" on provider failure);
FPA-119 (failures rendered as "none" in strategy lab); FPA-109 (fabricated rule summary);
PROVISIONAL FPA-107 (kill-switch BLOCK hidden behind "unavailable" on the portfolio hub when
discipline fails). BLUEPRINT: `win_rate` zero-for-empty must be gated in Analytics PR 1.

## 8. Navigation and deep-link findings

- All configured nav hrefs resolve to real pages (verified against route directories); no
  dead links. Phase-B redirects cover `/billing`, `/usage`, `/settings/usage`,
  `/invitations`, `/audit`, `/exchange` (`phase-b-redirects.ts` L12–19, wired in
  `next.config.ts` L8–13).
- Best-in-repo pattern: Signals deep-link miss shows an explicit alert and never opens an
  unrelated record (`tradingview-signals/page.tsx` L102–119); Lessons verifies `?candidate=`
  server-side and keeps a dedicated section when filters would hide it; Knowledge keeps a
  deep-link card under filter/query exclusion.
- Gaps: Knowledge/Journal deep links limited to the loaded window (FPA-110, and
  `journal/page.tsx` L41–46 for `?entry=` — same class); Plan silently drops invalid context
  (FPA-112); Validate hub has no inbound deep-link params at all (acceptable; note only).
- Back/forward is safe: `router.replace` is used to clear bad params (Signals L176–179);
  cross-page relationships use stored identifiers (`/journal?entry=`,
  `/journal?position_id=` on PR #37 builders; `/workspace?source=…&signal=…`).
- `/backtests/[id]` is deep-link-only by design (maps to Validate destination,
  `navigation-config.ts` L242–248) — not a dead end (linked from Strategy Lab and research
  validation).

## 9. Visual consistency findings

The AT-040 design system (`frontend/src/components/ui/`, tokens, `design-system.test.tsx`)
is high quality but unevenly adopted:

- Only 6 pages use `PageHeader` directly (plus Validate/Journal chromes); ~35 pages carry a
  local `<h1 className="text-2xl font-semibold">` (FPA-213).
- Token adoption is split: newest surfaces (Knowledge, Validate chrome, PR #37 panels) use
  semantic tokens; older pages remain `zinc-*` (worst: run-session, backtests, alerts/review).
- `DataNumber`, `FreshnessPill`, `ContentContainer`, `Skeleton` are almost unused outside
  the shell and newest pages; PR #37 (PROVISIONAL) adopts Panel/DataNumber/RiskBlock but
  re-implements source-availability/limitations UI inline instead of `states.tsx`.
- Status badge language varies between sidebar chip, status strip, and paper indicators
  (FPA-120).
- Empty/error/loading presentation is consistent where `states.tsx` is used; pages that
  bypass it (audit, invitations, analytics) are exactly where honesty defects live.

Recommendation: PR B migrates the premium-journey routes (not legacy/advanced pages, not
`/analytics`) to `PageHeader` + tokens + shared states, and stops there.

## 10. Performance and maintainability findings

- Fan-out: Dashboard issues 14 parallel `loadSource` calls (FPA-215/D-1); Validate adds
  per-session outcome probes; `strategy-lab/[id]` double-fetches (FPA-119);
  `/settings/billing` fetches quota twice (FPA-121).
- Polling: only `backtests/[id]` polls (4 s while active) — no runaway polling anywhere.
- API client: no timeout/abort (FPA-214); errors are typed `ApiError`s and helpers do not
  swallow (good); single-flight 401 refresh with one retry.
- Oversized client components: `backtests/[id]/page.tsx` 876 lines, run-session detail 686,
  `alerts/review` 656, `JournalQuickEntry` 614, `journal/comparison` 585, `lessons` 522,
  `tradingview-signals` 503 (FPA-216/208/209).
- Duplicate utilities: percent/level/date formatters re-implemented across ≥13 pages
  (FPA-116).
- Bundle: no chart library on main (verified — the blueprint adds `recharts` later);
  `lucide-react` + Tailwind only; no avoidable growth found in polish scope.
- Test gaps: 15 routes without page tests (FPA-122); CI (`.github/workflows/ci.yml`) runs
  backend ruff+pytest (Postgres 16), deployment-safety gates, frontend
  lint+typecheck+vitest+build, evaluation scripts, docker build, Playwright smoke.

## 11. User specifications required

The audit continued around each open question; none blocks PR A.

**US-1 — Canonical name for the analytics destination ("Analyze" vs "Analytics")**
- Decision: one label for `/analytics` across primary nav, secondary nav, TopBar title, page h1.
- Options: (a) verb "Analyze" everywhere (matches Plan/Validate verb set); (b) noun
  "Analytics" everywhere (matches page h1 and blueprint); (c) keep primary "Analyze" and
  rename the secondary item "Analytics hub" (matches "Plan hub"/"Validate hub" convention).
- Recommended default: **(c)** — smallest change, consistent with existing hub naming.
- Consequences: (a)/(b) touch more titles/tests; (c) leaves a verb/noun split between levels
  by design.
- Can implementation continue without the answer? **Yes** — label edits are isolated in PR B.

**US-2 — "Signals" vs "Inbox" for `/tradingview-signals` secondary label**
- Options: (a) rename secondary item to "Signals inbox" (matches the page's h2); (b) rename
  to "Signals hub"; (c) keep "Inbox".
- Recommended default: **(a)**.
- Consequences: cosmetic only; (c) preserves current mild drift.
- Continue without answer? **Yes**.

**US-3 — Dashboard discipline fallback presentation when the summary source fails**
- Options: (a) per-metric "unavailable" text in the existing card (recommended — matches the
  Validate `countOrNull` pattern); (b) replace the card with an `UnavailableState`; (c) keep
  current zero-seeded fallback with a stronger warning banner.
- Recommended default: **(a)**.
- Consequences: (b) loses the partially-available fields that do load; (c) retains the
  honesty defect.
- Continue without answer? **Yes** — PR A implements (a) unless overridden.

**US-4 — Fate of legacy `/positions` after the Portfolio command centre merges (PROVISIONAL)**
- Decision: keep `/positions` as the actionable close-paper-trade surface alongside the hub's
  read-only open-positions panel, or fold actions into the hub and redirect `/positions`.
- Options: (a) keep both, add the hub chrome to `/positions` for continuity (recommended);
  (b) fold + redirect (larger, touches PR #37 surface); (c) leave as-is (fragmented).
- Recommended default: **(a)**.
- Continue without answer? **Yes** — only the PR-C regression tests depend on it.

**US-5 — Daily-PnL chart ownership (Portfolio vs Analytics hub)**
- Context: main's Portfolio already renders a daily-PnL chart (`PaperPortfolioCharts.tsx`);
  blueprint C1 assigns the canonical daily-PnL chart to Analytics → Performance; AT-039 says
  no metric is fully charted twice.
- Options: (a) Portfolio keeps it until Analytics PR 1 ships, then Portfolio links to
  Analytics (recommended); (b) Portfolio keeps it permanently and the blueprint's C1 becomes
  cumulative-PnL only; (c) remove from Portfolio now (premature).
- Recommended default: **(a)** — decision executes inside the Analytics workstream, not the
  polish PRs.
- Continue without answer? **Yes**.

**US-6 — Deep-link recovery beyond the loaded window (Knowledge `?document=`, Journal `?entry=`)**
- Options: (a) frontend-only honest miss message naming the searched window (recommended for
  PR A); (b) add backend get-by-id endpoints and resolve directly (Deferred D-2); (c) raise
  the list limit (papering over).
- Recommended default: **(a) now, (b) later**.
- Continue without answer? **Yes**.

**US-7 — Standard confirmation pattern for destructive actions**
- Context: Signals uses a typed confirm phrase; KillSwitchButton uses `window.confirm` +
  `prompt`; Journal delete has none.
- Options: (a) inline confirm affordance (two-step button) for ordinary destructive actions +
  typed phrase for safety-critical ones (recommended); (b) typed phrase everywhere (heavy);
  (c) native dialogs everywhere (inaccessible, unstyled).
- Recommended default: **(a)**.
- Continue without answer? **Yes** — PR A applies (a) to Journal delete; KillSwitch migration
  in PR B.

## 12. Final implementation sequence

At most three small PRs, in order, after PR #37 and PR #38 merge (except where noted, all
work is frontend-only and excludes Analytics implementation, which follows its own approved
four-PR blueprint).

### PR A — critical honesty, safety-display, navigation and mobile blockers
- Scope: FPA-001, FPA-002, FPA-101, FPA-102 (US-3 default), FPA-103, FPA-104, FPA-105,
  FPA-107 (post-#37 follow-up), FPA-108 (US-7 default), FPA-109, FPA-110 (frontend miss
  message, US-6 default) + same-class Journal `?entry=` message, FPA-111, FPA-112, FPA-117,
  FPA-119.
- Likely files: `audit/page.tsx`, `invitations/page.tsx`, `hooks/useAsyncData.ts` (+ affected
  consumers/tests), `(app)/page.tsx` + `TodaysDisciplineCard.tsx` + `page.fallback.test.tsx`,
  `billing/page.tsx`, `settings/page.tsx` + `SafetyDisclaimers.tsx`, `contexts/AppContext.tsx`,
  `components/portfolio/buildRiskPosture.ts` (+test), `journal/page.tsx` +
  `RecentJournalEntries.tsx`, `lessons/LessonAcceptPanel.tsx`, `knowledge/page.tsx`,
  `layout/TopBar.tsx`, `workflows/planContext.ts` + `workspace/page.tsx`,
  `journal/import/page.tsx`, `strategy/PaperValidationPanel.tsx`,
  `strategy-lab/[id]/page.tsx`, plus tests.
- Dependencies: PR #37 merged (for FPA-107 and to avoid conflicts on AppContext/portfolio);
  PR #38 merged (doc-only, so only sequencing hygiene). US-3/US-6/US-7 answered or defaults
  accepted.
- Branch: `fix/at040-polish-a-honesty-safety`
- Recommended model: Fable 5 (safety-semantics judgment required).
- Estimated Cursor effort: one focused agent session; ~20 files, small scoped diffs; the only
  invasive edit is the `useAsyncData` behavior change (audit its ~30 consumers' tests).
- Test plan: new/extended vitest page tests per finding (listed in the register); full
  `npm run lint && npm run typecheck && npm run test && npm run build`.
- CI: full repository CI green including Playwright smoke.
- Conflict risks: `buildRiskPosture.ts` and AppContext overlap #37 (merge first);
  `useAsyncData` overlaps everything (keep the change minimal); avoid `/analytics` internals
  beyond the hook fix (blueprint rewrites the page).
- Exclusions: no navigation-config changes, no label renames, no visual restyling, no
  Analytics tabs/charts, no backend changes, no new endpoints.

### PR B — cross-page visual consistency, accessibility and responsive polish
- Scope: FPA-106, FPA-113, FPA-114, FPA-115, FPA-116, FPA-118, FPA-120 (US-1/US-2 answers),
  FPA-121, FPA-203, FPA-204, FPA-205, FPA-207, FPA-211, FPA-213 (premium-journey routes
  only), FPA-219.
- Likely files: `app/layout.tsx`, `AppShell.tsx`, `StatusStrip.tsx`, `(public)/*` auth pages,
  `lib/utils.ts` (or new `lib/format.ts` — align name with the Analytics blueprint),
  `usage/QuotaPanel.tsx`, `usage/UsageProviderTable.tsx`, `settings/billing/page.tsx` +
  `billing/page.tsx` + `usage/page.tsx`, `navigation-config.ts` (+test),
  `PaperPortfolioCharts.tsx`, `KillSwitchButton.tsx`, premium-journey `page.tsx` headers,
  deletion of `NotFinancialAdviceBanner.tsx` and legacy redirect page bodies.
- Dependencies: PR A merged; #37 merged (portfolio chart + nav config unfrozen);
  US-1/US-2 answered or defaults accepted.
- Branch: `feat/at040-polish-b-consistency-a11y`
- Recommended model: Composer 2.5 (broad mechanical edits) with Fable 5 review, matching the
  blueprint's model convention.
- Estimated Cursor effort: one to two agent sessions; wide but shallow diffs (~30 files),
  low logic risk, moderate test-churn risk from label/header changes.
- Test plan: navigation-config label tests; formatter unit tests (null honesty); a11y
  assertions (skip link, live region, chart labels); updated page snapshots; full frontend
  suite + build.
- CI: full repository CI green.
- Conflict risks: `navigation-config.ts` is the highest-contention file — confirm no other
  open PR touches it at start; `format.ts` naming must match the Analytics blueprint to
  avoid a duplicate utility.
- Exclusions: no `/analytics` page changes, no legacy/advanced-page restyling beyond headers,
  no behavior changes to data loading, no backend changes.

### PR C — final integration, regression tests, visual QA and paper-evaluation readiness
- Scope: FPA-122 (page tests for `/positions`, `/proposals`, `/approvals`, `/risk`,
  `/market`, `/strategy-lab/[id]`; settings composition test from FPA-121), re-audit closure
  of all PROVISIONAL items against merged main, execution of the §13 manual visual QA
  checklist with screenshots, §14 staging checklist sign-off, e2e smoke additions for the
  deep-link contracts (Signals `?signal=`, Journal `?entry=`, Knowledge `?document=`,
  Plan context params), and updating this document's readiness percentages to final.
- Likely files: new `page.test.tsx` files for the routes above; `frontend/e2e/*` smoke specs;
  `docs/product/at040_final_polish_and_readiness_audit.md` (final status update).
- Dependencies: PR A + PR B merged; US-4 answered (test targets for `/positions`).
- Branch: `test/at040-polish-c-regression-readiness`
- Recommended model: Fable 5 (test design + honest QA reporting).
- Estimated Cursor effort: one agent session plus a manual/computer-use visual QA pass at
  390/768/1280 px; additive test files only, near-zero production-code risk.
- Test plan: the new tests are the deliverable; full frontend suite, Playwright chromium
  project, screenshot capture project.
- CI: full repository CI green; e2e smoke green.
- Conflict risks: minimal (additive tests); coordinate with any Analytics PR 1 branch that
  may be open by then (do not add tests to `/analytics`).
- Exclusions: no production behavior changes except test hooks; no Analytics tests; no
  deployment.

## 13. Manual visual QA checklist

Run at 390 px, 768 px, 1280 px (Chromium; plus one iOS Safari pass for safe-area/keyboard).
For each: no horizontal overflow, tap targets ≥ 44 px, focus visible on every interactive
element, content clears the bottom nav.

1. Auth: login/register/reset — labels, error display, password-manager fill, mobile keyboard
   types, redirect to `?next=`.
2. Shell: sidebar (1280), secondary bar (768+), bottom nav + menu sheet (390) — active states,
   focus trap, Escape, safe-area padding; status strip readable and truncation acceptable at
   390 px; command menu ⌘K open/filter/navigate/Escape.
3. Dashboard: attention queue links; summary-unavailable notice; discipline card honesty
   (post-PR A: no invented zeros); "More workflows" disclosure.
4. Signals: list/detail stacking at 390; deep-link miss alert (`?signal=bogus`); typed
   confirm for candidate creation; freshness pills.
5. Plan: safety strip wrap; AI assist disclosure; invalid `?source=` notice (post-PR A);
   back-to-evidence link round-trip.
6. Validate: six count cards reflow 2→3 cols; unavailable counts read "unavailable", never 0;
   stage nav wrap; outcomes honesty labels.
7. Journal: quick-entry form on mobile (sticky save clears bottom nav, keyboard doesn't hide
   errors); delete confirm + error surfacing (post-PR A); `?entry=` hit and miss.
8. Lessons: filter chips wrap; `?candidate=` under conflicting filter shows dedicated
   section; accept panel requires summary (post-PR A).
9. Knowledge: URI wrapping in cards; deep link in/outside window; semantic search degraded
   badge; store-document round trip.
10. Portfolio (post-#37): source-availability alerts; mobile closed-positions cards vs
    desktop table; kill-switch BLOCK visible when discipline source fails (post-PR A);
    history coverage labels.
11. Risk + Positions: form labels/validation; posture ownership copy; close-paper-trade
    confirm.
12. Settings: profile posture card runtime-verified (post-PR A); billing single header +
    single quota panel (post-PR B); currency from API; team/audit honest loading/error
    (post-PR A); exchange diagnostics badges.
13. Cross-cutting: pinch zoom works (post-PR B); skip link appears on first Tab; kill-switch
    toggle announces state; back/forward through deep-linked pages never opens a wrong
    record; dark surfaces consistent (no `zinc` islands on premium routes post-PR B).

## 14. Staging readiness checklist

- [ ] PR #37 and PR #38 merged; this audit re-based and PROVISIONAL findings resolved
- [ ] PR A merged (both P0s closed; honesty cluster closed)
- [ ] Full repository CI green on `main` (backend ruff+pytest, deployment-safety job,
      frontend lint/typecheck/vitest/build, e2e smoke, docker build, evaluation scripts)
- [ ] Staging env: `EXECUTION_MODE=paper`, `ENABLE_REAL_TRADING=false`,
      `PROVIDER_MODE=fallback`, `EXCHANGE_MODE` non-live per `.cursor/rules/20-trading-safety.mdc`;
      `render.yaml` placeholders only
- [ ] `GET /health` on staging returns `execution_mode="paper"`,
      `real_trading_enabled=false`; status strip shows confirmed PAPER
- [ ] Kill-switch activate/deactivate round-trip on staging reflects in UI (post-FPA-105
      within the refresh interval)
- [ ] Provider status shows real mock/live counts; TopBar no longer reads "0 mock" on failure
- [ ] Auth flows (register → verify → login → reset) work against staging with
      `must_verify_email` as configured
- [ ] No console errors on the §13 route walk; no 404s from nav or deep links
- [ ] HANDOFF.md / CHANGELOG_SESSION.md regenerated and synced per `.ai/MASTER_WORKFLOW.md`

## 15. Two-week paper-evaluation readiness checklist

- [ ] Sections 13–14 complete; PR B merged (or explicitly waived); PR C tests green
- [ ] Evaluation protocol agreed: which signals sources are active, which strategies are in
      scope, journal discipline expectations, and the daily review loop
      (Dashboard → Signals → Plan → Validate → Journal)
- [ ] Data-honesty spot checks scheduled (twice weekly): failed-source displays, freshness
      pills, portfolio source availability, validation outcome coverage labels
- [ ] Kill-switch drill performed once at start: activate → verify BLOCK across shell +
      portfolio hub → deactivate → verify recovery
- [ ] Risk BLOCK verified authoritative: a blocked state renders `RiskBlock` with no
      override anywhere
- [ ] Mobile daily-driver check: one full journey day executed at 390 px
- [ ] Backlog triage rule agreed: defects found during evaluation are filed against this
      register's IDs; only P0s interrupt the evaluation window
- [ ] Explicit statement recorded that the evaluation measures process discipline and product
      dependability — no profitability claims or guarantees
- [ ] End-of-window review scheduled: journal statistics + validation outcomes + lessons
      review, feeding `.ai/TASKS.md`

## 16. Definition of done

This workstream is done when all of the following hold:

1. PR #36 merged (done), PR #37 and PR #38 merged, and every PROVISIONAL/BLUEPRINT marker in
   this document is resolved (confirmed, updated, or removed) against merged `main`.
2. FPA-001 and FPA-002 are fixed with regression tests; no route in the premium journey
   renders a failed source as zero, empty, or success.
3. All PR A P1 items are closed; PR B items are closed or explicitly deferred by the user
   with register IDs recorded; PR C tests exist and pass for the six named core routes.
4. All seven US questions are answered (or their recommended defaults explicitly accepted)
   and reflected in `.ai/DECISIONS.md`.
5. Full repository CI is green on `main`; the §13 visual QA checklist has been executed at
   all three breakpoints with results recorded; §14 staging checklist is complete.
6. Safety invariants are re-verified unchanged: paper-only posture from runtime `/health`,
   kill-switch and risk BLOCK authoritative and visible, real trading disabled, no
   fabricated metrics anywhere in the premium journey.
7. This document's readiness estimates and implementation sequence are updated to final,
   the audit PR is approved by a human reviewer, and Analytics implementation remains
   exclusively governed by its own approved blueprint.
