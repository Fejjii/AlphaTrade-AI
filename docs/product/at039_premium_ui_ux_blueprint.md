# AT-039 — AlphaTrade Premium UI/UX Product Blueprint (v1)

Status: PROPOSED (planning document — no code changes authorized by this document)
Task: AT-039
Scope: Product experience and visual-design blueprint for the AlphaTrade AI frontend
(`frontend/`, Next.js 15 App Router + React 19 + Tailwind CSS 3.4).
Companion document: `docs/product/at039_screen_inventory.md` (route-by-route audit).

---

## 0. Context and verified baseline

Facts verified against the repository at commit `0e45ef0` (main):

- The frontend has **48 authenticated routes** under `frontend/src/app/(app)/` and
  **5 public auth routes** under `frontend/src/app/(public)/`.
- The sidebar (`frontend/src/components/layout/nav-items.ts`) exposes **33 navigation
  items across 6 sections** ("Overview", "Paper-first workflow", "Legacy proposal flow",
  "Strategy & journal", "Market & tools", "Platform"). One section is literally named
  "Legacy proposal flow" in the user-facing UI.
- Mobile navigation (`MobileMoreNav.tsx`) shows 5 primary tabs and pushes the remaining
  ~28 items into a "More" drawer.
- The design system is minimal: four primitives exist in `frontend/src/components/ui/`
  (`badge`, `button`, `card`, `input`). Pages compose raw Tailwind classes directly
  (`text-2xl font-semibold`, `zinc-950` surfaces, `emerald` accents).
- Every page renders behind `AppShell` with a persistent `PaperModeBanner` and
  `NotFinancialAdviceBanner`.
- A basic `manifest.json` exists in `frontend/public/`; no dedicated charting library is
  currently installed in `frontend/package.json`.
- Trading safety is paper-first and human-in-the-loop: `EXECUTION_MODE=paper`,
  risk-engine `BLOCK` is final, market data carries `is_live` / `fallback_used`
  freshness metadata. The UI must express these guarantees, never hide them.

The core product problem is **navigation and metric sprawl**: the system's genuinely
strong paper-first learning loop is buried under 33 flat navigation entries, duplicated
surfaces (two market-watcher pages, alerts vs. signals vs. proposals vs. approvals), and
screens that expose every metric at once. This blueprint defines the target experience.

---

## 1. Product experience principles

1. **Calm over dense.** A trading assistant should reduce cognitive load, not add to it.
   Each screen answers one question ("What needs my decision?", "How am I performing?").
   Everything else is one deliberate tap away, never on-screen by default.
2. **Progressive disclosure as the default pattern.** Summary first, evidence on demand.
   A signal card shows symbol, direction, confidence, and freshness; the full detector
   payload, orchestration trace, and audit trail live in an expandable detail layer.
3. **Safety is a visible product feature, not a disclaimer.** Paper mode, risk blocks,
   cooldowns, and data-freshness states are rendered as first-class, well-designed UI
   states — a premium product is proud of its guardrails.
4. **The human decides; the system explains.** Every recommendation surface (signals,
   proposals, validation verdicts) must show *why* — evidence, confidence, and provenance
   — before asking for approval. No black-box "Approve" buttons.
5. **One concept, one place.** Alerts, TradingView signals, and watcher scans are all
   "signals"; positions and portfolio are one "portfolio"; validation drafts, candidates,
   plans, and sessions are one pipeline. Duplicated concepts are consolidated, not themed.
6. **Fast by perception and by measurement.** Skeletons within 100 ms, interactive within
   1 s on a mid-range phone, optimistic UI for reversible actions, no layout shift.
7. **Honest data, always.** Stale, fallback, or mock data is visually distinct
   (freshness pill), consistent with the backend's `is_live` / `fallback_used` contract.
   The UI never lets simulated or stale data masquerade as live market truth.
8. **Commercial polish is consistency.** Same spacing scale, same card anatomy, same
   empty-state pattern, same verb tense on buttons, everywhere. Nothing ad hoc.

---

## 2. Information architecture

### 2.1 Model: eight top-level destinations

The 48 routes collapse into **8 primary destinations** (required target navigation),
each owning a clear question:

| Destination | Owns the question | Absorbs (today's routes) |
|---|---|---|
| **Dashboard** | "What needs my attention right now?" | `/` |
| **Plan** | "What trade am I preparing, and is it approved?" | `/workspace`, `/proposals`, `/approvals`, `/pre-trade`, `/manual-levels`, `/strategy-lab/*` |
| **Signals** | "What is the market and the system telling me?" | `/tradingview-signals`, `/alerts`, `/alerts/review`, `/watcher`, `/market-watcher`, `/market`, `/watchlist`, `/paper-signal-orchestration` |
| **Validate** | "Is this setup actually worth trading?" | `/paper-validation/*` (drafts, candidates, run-plans, run-sessions), `/validation-priority`, `/research-validation`, `/backtests/[id]` |
| **Journal** | "What did I trade, what did I learn, what am I teaching the system?" | `/journal`, `/journal/import`, `/lessons`, `/knowledge` |
| **Analyze** | "How are I and the system performing?" | `/analytics`, `/journal/statistics`, `/journal/comparison`, `/learning-analytics`, `/coaching`, `/strategy-quality` |
| **Portfolio** | "What do I hold, and what is my risk state?" | `/portfolio`, `/positions`, risk/cooldown *state* from `/risk` |
| **Settings** | "How is my account and platform configured?" | `/settings`, risk *configuration* from `/risk`, `/billing`, `/usage`, `/invitations`, `/audit`, `/exchange` |

Full per-route dispositions are in `docs/product/at039_screen_inventory.md`.

### 2.2 Hierarchy rules

- **Level 1** — the 8 destinations above. Always visible (sidebar on desktop, bottom
  bar on mobile). Nothing else lives at level 1.
- **Level 2** — tabs or segmented controls *inside* a destination (e.g. Portfolio →
  Overview | Positions | Risk & Cooldowns). Level 2 is a URL (`/portfolio/positions`)
  so deep links and back-button behavior stay correct.
- **Level 3** — detail views (a signal, a validation candidate, a journal entry).
  Rendered as a right-side panel on desktop (list stays visible) and a full-screen
  push on mobile. Always URL-addressable.
- **Advanced surfaces** (orchestration diagnostics, research validation, exchange
  diagnostics, audit) stay accessible but are placed behind an explicit "Advanced"
  affordance inside their destination. They are hidden from primary navigation, not
  deleted.
- **No user-facing "legacy" labels.** The proposals/approvals flow merges into Plan;
  the section title "Legacy proposal flow" disappears.

### 2.3 The spine: signal → plan → validate → journal → analyze

The IA mirrors the actual learning loop. Each destination links forward along the
spine with a single primary action:

- Signals: "Review" → opens evidence → "Create draft" (→ Validate) or "Plan trade" (→ Plan).
- Plan: "Submit for approval" → approval card → "Approve (paper)" → position (→ Portfolio).
- Validate: "Record outcome" → "Journal it" (→ Journal).
- Journal: "Extract lesson" → lesson review (→ Journal/Lessons) → knowledge (teaching).
- Analyze: read-only synthesis; links back to the underlying journal/validation records.

---

## 3. Proposed primary navigation

### 3.1 Desktop (≥ 1024 px)

- **Left sidebar, 240 px, no section headers needed** — just the 8 destinations, each
  with icon + label; active item gets a subtle filled pill (not just a color change).
- Below the destinations, a thin divider and two persistent utilities: **Command menu
  hint (⌘K)** and the **environment chip** ("Paper" — see §7).
- Sidebar collapses to a 64 px icon rail on demand; state persists per user.
- **Top bar** keeps: page title/breadcrumb, global search / command menu (⌘K),
  freshness indicator for the data on-screen, and the account menu. The two current
  banners (paper mode, not-financial-advice) merge into one compact, dismissible-per-
  session status strip attached to the top bar rather than stacked page-level banners.

### 3.2 Mobile (< 1024 px)

- **Bottom bar with exactly 5 items:** Dashboard, Signals, Plan, Portfolio, and
  **Menu**. Plan sits in the center as the primary-action tab.
- **Menu** opens a half-sheet with the remaining destinations (Validate, Journal,
  Analyze, Settings) as large tappable rows — 4 rows, not today's ~28-item drawer.
- Level-2 tabs render as horizontally scrollable segmented controls under the title.

### 3.3 Command menu

A ⌘K / long-press-search command menu provides jump-to-anything (destinations, symbols,
recent signals, journal entries) and quick actions ("New journal entry", "New draft").
This is what makes an 8-item navigation feel *faster* than a 33-item sidebar.

---

## 4. Core user journeys

Each journey lists: entry point → steps → success state. All journeys are paper-mode;
none creates a live order.

### J1 — Review a TradingView signal
1. Push/badge on **Signals**; signal inbox sorted by freshness + confidence.
2. Tap a signal card (symbol, direction, source badge "TradingView", freshness pill,
   confidence). Detail panel opens: parsed payload, matched playbook, detector evidence,
   chart snapshot with levels, signed-webhook provenance.
3. Actions: **Create validation draft**, **Plan trade**, or **Dismiss** (with reason
   chips — feeds learning).
Success: signal is triaged in ≤ 3 taps with evidence seen, decision recorded.

### J2 — Prepare and approve a paper trade
1. From a signal or from **Plan → New plan**: guided trade ticket (symbol, direction,
   entry, stop, target). Position size is *computed* from risk settings, shown with
   its formula on tap — not hand-typed.
2. Pre-trade checks run inline (today's `/pre-trade` becomes a step, not a page):
   risk-per-trade, exposure, cooldown, data freshness. Each check renders pass /
   warn / **block**. A risk-engine BLOCK is terminal and visually final (§7).
3. Submit → approval card appears in **Plan → Approvals** with full context.
4. Human taps **Approve (paper)** — button explicitly labeled paper — confirmation
   sheet restates size, risk, and R-multiple. Approved → paper position opens.
Success: an approved paper position exists in Portfolio with a full audit trail.

### J3 — Journal a completed trade
1. Position closes (or user closes it) → toast + Dashboard "Needs journaling" item.
2. **Journal → New entry** arrives pre-filled (symbol, R-result, plan link, chart
   snapshot). User adds rating, emotion tags, and "what happened vs. plan".
3. Optional: "Extract lesson" turns free text into a structured lesson for review.
Success: entry saved in ≤ 2 minutes; statistics and Human-vs-System update.

### J4 — Compare Human versus System performance
1. **Analyze → Human vs System** (today's `/journal/comparison`, promoted).
2. Side-by-side scorecards: win rate, expectancy, avg R, drawdown, sample size —
   with confidence-interval hints so small samples aren't over-read.
3. Drill-down: divergence list ("system said skip, human traded", and inverse) linking
   to the underlying journal entries.
Success: user can answer "where does the system beat me?" with linked evidence.

### J5 — Inspect setup evidence
1. From any signal, candidate, or proposal: **Evidence** tab in the detail panel.
2. Shows detector scores with history (from strategy-quality data), validation run
   outcomes for this setup class, sample sizes, and freshness/provenance of every
   input. Low-sample or stale evidence is explicitly flagged.
Success: "why should I trust this?" answered on one screen without leaving context.

### J6 — Review portfolio, risk and cooldown state
1. **Portfolio** opens on Overview: equity curve, open risk, exposure by asset.
2. **Risk & Cooldowns** tab: today's risk budget consumed, active cooldowns with
   countdown and *reason* ("2 consecutive losses on BTC setups"), current limits
   (read-only here; editing lives in Settings → Risk with confirmation).
Success: risk state is understood at a glance; no way to "accidentally" edit limits.

### J7 — Teach AlphaTrade (observation, asset thesis, or setup)
1. **Journal → Teach** (today's `/knowledge`, promoted and renamed) or the ⌘K quick
   action "Teach AlphaTrade".
2. Structured capture: type chips (Observation | Asset thesis | Setup rule), free text,
   optional symbol/timeframe/links to trades or signals.
3. System echoes back its structured interpretation for confirmation before saving —
   the user confirms the machine understood the teaching.
Success: knowledge item saved, visible in a reviewable list with edit/retire actions.

---

## 5. Design-system direction

### 5.1 Strategy

Grow the existing minimal `components/ui` layer into a small, documented set of
**shadcn/ui-style primitives on Radix behavior + Tailwind tokens** (this matches the
current stack; no new framework). Rule: **pages compose primitives; pages do not
invent visual styles.** Raw one-off Tailwind class stacks in `page.tsx` files are the
current source of inconsistency and are phased out.

### 5.2 Primitive inventory (target)

- Existing, to be tokenized: `Button`, `Card`, `Badge`, `Input`.
- To add (each replaces ≥ 3 ad-hoc implementations found in current pages):
  `PageHeader`, `Tabs`, `Sheet`/`Drawer`, `Dialog`, `Select`, `Table` (with mobile
  card fallback, §8), `Skeleton`, `EmptyState` (exists informally — standardize),
  `Stat` (metric tile), `FreshnessPill`, `StatusBadge` (pass/warn/block/stale),
  `Toast`, `CommandMenu`, `ConfirmSheet` (for approvals), `Timeline` (audit/history).

### 5.3 Color tokens (dark-first, see §10)

Semantic tokens, not raw palette references, in `globals.css` / Tailwind config:

- `surface-0/1/2` — page, card, raised layers (today's zinc-950/900/800 mapped).
- `accent` — emerald family (kept; it is the brand's "paper-safe" green).
- `positive` / `negative` — P&L green/red, tuned for AA contrast on dark and
  never used for anything except directional financial meaning.
- `warning` (amber) — stale data, cooldowns, warn-level checks.
- `danger` (red) — risk BLOCK, destructive actions.
- `info` (blue) — system/informational.
- Directional color is always paired with an icon or sign (▲/＋, ▼/−) — color is
  never the only channel (§12).

---

## 6. Typography and spacing

- **Typeface:** Inter (or Geist, already Next-native) for UI; a tabular-figure
  monospace (`font-feature-settings: "tnum"` or JetBrains Mono) for **all numerals in
  tables, tickets, and stats** so prices and P&L align and don't jitter on update.
- **Type scale (rem):** display 1.75 / page title 1.5 / section 1.125 / body 0.875 /
  caption 0.75. One page title per page (`PageHeader`), rendered by the primitive —
  the current hand-written `text-2xl font-semibold` h1s are replaced by it.
- **Weights:** 600 for titles, 500 for emphasis and buttons, 400 for body. Nothing
  bolder than 600; premium feel comes from spacing and hierarchy, not weight.
- **Spacing:** strict 4 px base scale; components use 8/12/16/24/32. Card padding 16 px
  (mobile) / 24 px (desktop). Page gutter 16 px / 24 px. Vertical rhythm between page
  sections: 24 px. Max content width stays `max-w-7xl`; reading-heavy surfaces
  (journal entry, teaching) constrain to ~65ch.
- **Radii & elevation:** radius 8 px (controls) / 12 px (cards); elevation expressed by
  surface step + 1 px border (`surface-2` + border) rather than heavy shadows — shadows
  read poorly on dark themes.

---

## 7. Cards, tables, forms and safety states

### 7.1 Card anatomy (one pattern everywhere)

Header (title + optional `FreshnessPill` + overflow menu) → primary value/content →
supporting row (caption-size metadata) → optional footer actions. Signal cards,
position cards, stat tiles, and approval cards are all instances of this anatomy.

### 7.2 Tables

- Desktop: dense but readable — 44 px rows, right-aligned tabular numerals, sticky
  header, column sort. Row click opens the detail panel (level 3), never navigates
  away from the list.
- Mobile: tables **do not** horizontally scroll by default; they collapse into
  key-value cards showing the 3–4 decision-critical columns, with "View details" for
  the rest (progressive disclosure).
- Virtualize beyond ~100 rows (signals, audit).

### 7.3 Forms

- Single-column, top-aligned labels, inline validation on blur, error text under the
  field. Destructive or irreversible actions get a `ConfirmSheet` that restates the
  consequence in plain language.
- Trading forms never ask for what the system can compute: position size, R-multiple,
  and risk-% derive live from risk settings and render as computed, explained values.
- Server errors map to field-level errors where possible; a generic toast is the last
  resort, never the first.

### 7.4 Safety states (first-class visual grammar)

| State | Visual | Behavior |
|---|---|---|
| **Paper mode** | Persistent compact "Paper" chip in top bar (replaces stacked banner) | Always on; approval buttons say "Approve (paper)" |
| **Risk check: pass** | Muted green check row | Non-blocking |
| **Risk check: warn** | Amber row + reason | Proceed allowed, reason must be visible |
| **Risk check: BLOCK** | Red panel, lock icon, reason + rule reference | Primary action disabled; **no override control exists in the UI** — the risk engine's BLOCK is final |
| **Cooldown active** | Amber chip with countdown + cause | Plan ticket disabled for affected scope |
| **Data stale / fallback** | Amber `FreshnessPill` ("delayed · 4m", "fallback source") on every affected value | Confirmation sheets repeat the freshness warning |
| **Not-financial-advice** | Footer line in the app shell + on statements/exports | Not a per-page banner |

---

## 8. Chart and analytics standards

- **One charting stack.** Adopt a single library — recommendation: **TradingView
  Lightweight Charts** for price/candle/level charts and **Recharts** for statistical
  charts (equity curve, distributions) — added once, in a dedicated Phase (§11);
  no per-page chart implementations. (Neither is currently installed; today's pages
  are chartless or ad hoc, which caps the perceived quality.)
- **Standards for every chart:** dark-theme tokens (§5.3), tabular-numeral axis
  labels, no gridline overload (y-axis only, muted), interactive crosshair with a
  single shared tooltip style, and an explicit **provenance caption** (source +
  as-of time), consistent with the freshness contract.
- **Price charts** show plan context by default: entry/stop/target lines, manual
  levels, and fill markers for paper executions.
- **Statistical charts** always show sample size; distributions preferred over single
  averages (e.g. R-multiple histogram, not just "avg R"). Confidence/sample warnings
  render inside the chart area, not in footnotes.
- **Sparklines** (equity, detector-quality trend) use the `Stat` primitive's slot —
  same 32 px height, no axes, everywhere.
- Empty analytic states show a labeled skeleton of the chart-to-be with the action
  that will populate it ("Close 5 journaled trades to unlock expectancy").

---

## 9. Loading, empty, stale, blocked and error states

Every data surface must implement all five, via primitives — no blank divs:

- **Loading:** skeletons matching final layout (cards, table rows, chart frames)
  within 100 ms; no spinners for primary content; no layout shift on resolve.
  Mutations use inline button spinners + optimistic UI where reversible.
- **Empty:** the existing `EmptyState` pattern is kept and standardized: icon, one
  sentence of *why it's empty*, one primary action that starts the journey that fills
  it (the current pages already do this well — e.g. drafts: "Mark a setup alert as
  watching or important, then create a paper draft" — keep that spirit, standardize
  the component).
- **Stale/fallback:** amber `FreshnessPill` per §7.4; page-level stripe when the whole
  view is degraded ("Market data delayed — decisions use conservative values").
  Distinct from error: stale data still renders, clearly labeled.
- **Blocked:** risk BLOCK and cooldown render as designed states (§7.4), visually
  distinct from errors — the system working as intended, not failing.
- **Error:** inline retry cards for partial failures (one widget fails, page stands);
  full-page error only when nothing can render; error text says what failed and what
  to do, never a bare status code. Route-level `error.tsx` boundaries per destination.

---

## 10. Dark-mode-first direction

- **Dark is the primary, designed-first theme** — the current zinc-950 base is kept
  and tokenized (§5.3). Charts, skeletons, and imagery are designed on dark first.
- Near-black neutral surfaces (no blue-tinted grays), 1 px borders + surface steps for
  elevation, desaturated accents so P&L colors don't glow.
- All text/interactive contrast meets WCAG AA on `surface-0/1/2` (verified in CI or
  review checklist, not by eye).
- A light theme is a token-swap deliverable in a later phase (§11), enabled by the
  semantic-token architecture; `next-themes` (or equivalent) with
  `prefers-color-scheme` default and a Settings toggle. No component may hardcode a
  palette value — that is the enforcement rule that makes light mode cheap.

---

## 11. Mobile and PWA experience

- **Responsive rules:** bottom bar + Menu sheet (§3.2); tables → key-value cards
  (§7.2); detail panels → full-screen pushes; touch targets ≥ 44 px; thumb-zone
  placement for primary actions (bottom-anchored action bar on tickets/approvals).
- **Mobile-critical journeys** (J1 review signal, J2 approve, J6 risk state, J3 quick
  journal) are designed mobile-first; deep analysis (J4, J5 drill-downs) may remain
  desktop-optimized but must degrade gracefully.
- **PWA:** complete the existing `manifest.json` (name, theme color, maskable icons),
  add installability, an app-shell cache for instant cold starts, and offline behavior
  that is *honest*: cached views render with an explicit "offline — data as of HH:MM"
  stripe; all mutating actions disabled offline (no queued approvals — queuing a
  trade approval offline is a safety hazard, so it is deliberately unsupported).
- Push notifications (approval pending, cooldown lifted, signal above threshold) are
  opt-in per category in Settings; each notification deep-links to its level-3 detail.

---

## 12. Accessibility

- **WCAG 2.1 AA** as the acceptance bar for all new/redesigned surfaces.
- Full keyboard operability: visible focus rings (accent, 2 px offset), logical tab
  order, ⌘K menu fully keyboard-driven; list → detail-panel focus management and
  Escape-to-close; focus trap in sheets/dialogs.
- Screen readers: landmarks per app-shell region, one h1 per page (enforced by
  `PageHeader`), `aria-live="polite"` for freshness/price updates, descriptive labels
  on icon-only controls (the current codebase already does this in places — e.g. the
  mobile nav's `aria-label` and `aria-expanded` — extend to everything).
- Color independence: every directional/safety meaning carries an icon or text in
  addition to color (§5.3); charts get accessible summaries (visually hidden text or
  data-table toggle).
- Reduced motion: all non-essential animation behind `prefers-reduced-motion`.
- Numbers announce meaningfully: P&L values expose sign and unit to assistive tech,
  not just "−142".

---

## 13. Implementation roadmap

Phased by dependency, not calendar time. Each phase is independently shippable and
leaves the app consistent (no half-migrated navigation states visible to users).

- **Phase 0 — Tokens and primitives.** Introduce semantic color/type/spacing tokens
  (§5.3, §6) and the primitive set (§5.2), including `PageHeader`, `FreshnessPill`,
  `StatusBadge`, `Skeleton`, standardized `EmptyState`. No route changes. Risk: low;
  purely additive.
- **Phase 1 — Shell and navigation.** New 8-destination sidebar, mobile bottom bar +
  Menu sheet, merged status strip (paper + advice), command menu. Old routes keep
  working via redirects; `nav-items.ts` is replaced. This phase delivers the largest
  perceived-quality jump for the least page-level work.
- **Phase 2 — Spine consolidation.** Signals inbox (merging alerts/tradingview-
  signals/watcher surfaces), Plan hub (workspace + proposals + approvals + pre-trade
  as ticket steps), Validate pipeline (drafts → candidates → runs as one flow),
  Portfolio merge (positions tab, risk & cooldown state tab). Route redirects per the
  screen inventory. Most invasive phase; done destination-by-destination.
- **Phase 3 — Charts and analytics.** Add the charting stack (§8), Dashboard redesign,
  Analyze hub (statistics + comparison + learning analytics + coaching + strategy
  quality), evidence panels (J5).
- **Phase 4 — Mobile/PWA polish and accessibility hardening.** Manifest/installability,
  offline shell, notification opt-ins, AA audit pass, reduced-motion audit.
- **Phase 5 — Light theme and commercial finish.** Token-swap light mode, auth-screen
  polish, micro-interaction pass (hover/press states, transitions ≤ 200 ms).

Dependencies: 1 requires 0; 2–3 require 1; 4–5 require 2–3 only for the surfaces they
polish. Backend/API changes are **not** required for phases 0–1 and are expected to be
minimal elsewhere (the consolidation is presentational; existing endpoints remain).

---

## 14. Commercially polished acceptance criteria

The redesign is "commercially polished" when all of the following hold:

**Navigation & IA**
1. Primary navigation contains exactly 8 destinations; no user-visible "legacy",
   duplicate, or diagnostic entries at level 1.
2. Every retained route from the screen inventory is reachable in ≤ 2 interactions
   from its destination; old URLs redirect (no dead links).
3. Mobile bottom bar has exactly 5 items; the Menu sheet lists 4 destinations, not a
   scrolling item dump.

**Consistency**
4. Zero pages hand-roll page titles, empty states, stat tiles, badges, or freshness
   indicators — all come from primitives (verifiable by grep for `text-2xl` h1s and
   ad-hoc empty-state divs in `app/`).
5. All numerals in tables/tickets/stats render in tabular figures; P&L never renders
   color-only (icon/sign always present).

**Safety & honesty**
6. Paper mode is indicated persistently on every authenticated view; every approval
   control is labeled "(paper)".
7. A risk-engine BLOCK renders as a designed terminal state with reason; no UI path
   overrides it. Cooldowns show cause + countdown.
8. Every market-data value on screen carries provenance; stale/fallback data is
   visually flagged within one component boundary of the value itself.

**States & performance**
9. Every data surface implements loading/empty/stale/blocked/error per §9 (audited
   per destination with a state checklist).
10. Core mobile journeys (J1, J2, J3, J6) are completable one-handed on a 390 px
    viewport with no horizontal scrolling; Lighthouse (mobile) ≥ 90 performance /
    ≥ 95 accessibility on Dashboard, Signals, Plan, Portfolio.
11. Skeletons appear within 100 ms; navigation between destinations has no visible
    layout shift (CLS < 0.1).

**Experience**
12. All seven core journeys (§4) pass an unassisted walkthrough by someone unfamiliar
    with the old UI, using only on-screen affordances.
13. The app is installable as a PWA; offline shows the honest offline state (§11);
    no mutation is possible offline.
14. AA contrast verified for all token pairs; full keyboard walkthrough of J1–J7
    recorded as part of acceptance.
15. No screen displays more than ~7 primary metrics without a disclosure interaction —
    progressive disclosure is the enforced default, not a guideline.

---

*End of AT-039 blueprint v1. Companion route audit:
`docs/product/at039_screen_inventory.md`.*
