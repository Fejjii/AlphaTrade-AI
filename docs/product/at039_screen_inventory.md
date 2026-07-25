# AT-039 — Screen Inventory and Route Dispositions (v1)

Status: PROPOSED (planning document — no code changes authorized by this document)
Task: AT-039
Scope: Audit of every current frontend route with a disposition for the premium
redesign. Companion document: `docs/product/at039_premium_ui_ux_blueprint.md`
(referenced below as "the blueprint").

Baseline verified at commit `0e45ef0` (main): **48 authenticated routes** under
`frontend/src/app/(app)/` and **5 public routes** under `frontend/src/app/(public)/`,
**53 total**. Route purposes were read from each `page.tsx` (headings, empty-state
copy) and the nav labels in `frontend/src/components/layout/nav-items.ts`.

## Classification key

- **retain** — keep as its own URL and surface, minor polish only
- **simplify** — keep, but reduce visible density/controls (progressive disclosure)
- **redesign** — keep the job-to-be-done, rebuild the surface
- **consolidate** — merge into another destination as a tab, panel, step, or filter
- **rename** — user-facing name changes (noted inline alongside another disposition)
- **hide** — keep functional but move behind an explicit "Advanced" affordance
- **remove** — route retired; its function is absorbed elsewhere (redirect kept)

**Primary users** (from blueprint §1.1): *Daily trader* (short, frequent, often
mobile sessions), *Researcher* (long desktop sessions), *Owner/operator*
(configuration, billing, diagnostics), *Visitor* (unauthenticated).

**Priorities:** P1 = core spine (redesign fails without it), P2 = strong contributor
to perceived quality, P3 = polish. **Phases** A–F match the blueprint roadmap (§13);
routes are assigned to the phase in which their change ships (Phase A tokens and
Phase F review are cross-cutting and own no routes). All consolidations and removals
keep a redirect from the old URL.

Each route record carries: route, screen name, current purpose, primary user,
usability/density problem, target navigation group, disposition, desktop treatment,
mobile treatment, priority, phase, consolidation partners, essential information
(always visible), and advanced information (behind progressive disclosure).

## Summary counts

**By classification (each route counted once):**

| Disposition | Count |
|---|---|
| retain | 14 |
| simplify | 6 |
| redesign | 7 |
| consolidate | 21 |
| hide | 3 |
| remove | 2 |
| **Total** | **53** |

Renames (noted inline, overlapping the above): 5 — Workspace→Plan,
Strategy Lab→Playbooks, Watcher Scanner→Scanner, Knowledge Base→Teach,
Strategy Quality→Evidence.

**By implementation phase:**

| Phase | Scope | Routes |
|---|---|---|
| A — Design-system foundation | Tokens + primitives; no route changes | 0 |
| B — Navigation and shell | Nav-only moves, Settings hub, Advanced placements | 8 |
| C — Critical daily workflows | Spine consolidations and redesigns | 32 |
| D — Analytics visualisation | Analyze hub, charts, evidence/backtests | 7 |
| E — Mobile/PWA polish | Auth screens, import wizard, PWA, light theme | 6 |
| F — Usability and consistency review | Cross-cutting audit; no route changes | 0 |
| **Total** | | **53** |

**By priority:** P1 = 19, P2 = 18, P3 = 16.

---

## 1. Dashboard

#### `/` — Dashboard
- **Disposition:** redesign (Phase C, P1)
- **Current purpose:** Landing page with strategy tiles, portfolio summary, and
  miscellaneous panels.
- **Primary user:** Daily trader.
- **Problem:** Generic tile grid gives equal weight to everything; does not answer
  "what needs my decision right now"; duplicates metrics owned by other screens.
- **Target group:** Dashboard.
- **Desktop:** Attention-first layout — needs-decision queue (signals awaiting
  triage, approvals pending, trades needing journaling, active cooldowns), portfolio
  snapshot, freshness strip. Sparkline/stat references only (blueprint §8.3).
- **Mobile:** Stacked cards, decision queue first; every item one-tap deep-links.
- **Consolidate with:** None (references other destinations, owns nothing twice).
- **Essential:** Needs-decision queue with counts; paper-mode chip; equity sparkline;
  open risk; active cooldown indicator.
- **Progressive disclosure:** Per-item detail (opens in owning destination); full
  equity/drawdown charts (Portfolio); full signal list (Signals).

---

## 2. Plan

Group question: *"What trade am I preparing, and is it approved?"*

#### `/workspace` — AI Trading Workspace
- **Disposition:** redesign + rename → **Plan hub** (Phase C, P1)
- **Current purpose:** AI-assisted analysis and plan creation.
- **Primary user:** Daily trader.
- **Problem:** "Workspace" is vague; overlaps proposals; the core J2 journey has no
  obvious entry point.
- **Target group:** Plan.
- **Desktop:** Plan hub landing: "New plan" primary action, in-flight plans,
  approvals badge, AI assistance embedded in the ticket rather than a separate room.
- **Mobile:** Center bottom-bar tab; ticket as a full-screen stepped flow.
- **Consolidate with:** Absorbs `/proposals`, `/approvals`, `/pre-trade` as tabs/steps.
- **Essential:** New-plan action; count of plans awaiting approval; active cooldown
  warning if planning is restricted.
- **Progressive disclosure:** AI reasoning traces; historical plans; playbook library.

#### `/proposals` — Trade Proposals
- **Disposition:** consolidate → Plan → Proposals (Phase C, P1)
- **Current purpose:** Trade proposal list + detail (currently under a nav section
  literally titled "Legacy proposal flow").
- **Primary user:** Daily trader.
- **Problem:** User-facing "legacy" label; split from approvals although they are one
  pipeline; duplicate of the workspace concept.
- **Target group:** Plan.
- **Desktop:** List + right detail panel inside Plan.
- **Mobile:** Card list; full-screen detail push.
- **Consolidate with:** `/workspace` (hub), `/approvals` (same pipeline).
- **Essential:** Symbol, direction, computed size, R-multiple, status, freshness of
  underlying data.
- **Progressive disclosure:** Full rationale, detector evidence, audit trail.

#### `/approvals` — Approvals
- **Disposition:** consolidate → Plan → Approvals (Phase C, P1)
- **Current purpose:** Human review queue for proposals awaiting approval.
- **Primary user:** Daily trader.
- **Problem:** Separate page for the decision step of the same pipeline as proposals.
- **Target group:** Plan.
- **Desktop:** Approvals tab; approval card with evidence and `ConfirmSheet`; button
  labeled "Approve (paper)".
- **Mobile:** Bottom-anchored approve/reject bar; one-handed operation (J2).
- **Consolidate with:** `/proposals` (one pipeline inside Plan).
- **Essential:** Symbol, direction, size, risk-%, R-multiple, pre-trade check results
  (pass/warn/BLOCK), data freshness.
- **Progressive disclosure:** Full evidence panel, orchestration trace, prior similar
  trades, raw payload.

#### `/pre-trade` — Pre-Trade Analysis
- **Disposition:** consolidate → Plan ticket step (Phase C, P1)
- **Current purpose:** Standalone pre-trade risk/size checks.
- **Primary user:** Daily trader.
- **Problem:** Disconnected calculator that can be skipped; duplicates what the
  ticket should enforce inline.
- **Target group:** Plan.
- **Desktop:** Inline checks step inside the Plan ticket — pass/warn/BLOCK rows;
  BLOCK is terminal (blueprint §7.4).
- **Mobile:** Same, as a ticket step.
- **Consolidate with:** Plan ticket (`/workspace` flow).
- **Essential:** Each check's status and one-line reason; computed position size.
- **Progressive disclosure:** Check formulas, rule references, historical check
  outcomes for this setup.

#### `/manual-levels` — Manual Levels
- **Disposition:** simplify → Plan → Levels (Phase C, P2)
- **Current purpose:** CRUD for manual price levels.
- **Primary user:** Daily trader / Researcher.
- **Problem:** Isolated table page; levels are invisible where they matter (charts
  and tickets).
- **Target group:** Plan.
- **Desktop:** Levels tab; levels also rendered on all price charts (blueprint §8.1).
- **Mobile:** Simple list + add sheet.
- **Consolidate with:** None (kept as a tab; surfaced on charts).
- **Essential:** Symbol, level price, direction/type, active/inactive.
- **Progressive disclosure:** Notes, creation source (manual vs. AI Workspace),
  edit history.

#### `/strategy-lab` — Strategy Lab
- **Disposition:** simplify + rename → **Playbooks** (Phase C, P2)
- **Current purpose:** Strategy card library.
- **Primary user:** Researcher.
- **Problem:** "Lab" jargon; flat table without quality context.
- **Target group:** Plan.
- **Desktop:** Playbooks list with quality/evidence chips per playbook.
- **Mobile:** Card list.
- **Consolidate with:** None (list retained; children fold in below).
- **Essential:** Playbook name, setup class, quality/evidence score, sample size.
- **Progressive disclosure:** Full rules, linked backtests, validation history.

#### `/strategy-lab/new` — Create strategy
- **Disposition:** consolidate → Playbooks drawer (Phase C, P3)
- **Current purpose:** Create-strategy form.
- **Primary user:** Researcher.
- **Problem:** A full page for a short form.
- **Target group:** Plan.
- **Desktop:** Drawer/modal from the Playbooks list.
- **Mobile:** Full-screen sheet.
- **Consolidate with:** `/strategy-lab` (parent list).
- **Essential:** Name, setup class, core rule fields.
- **Progressive disclosure:** Optional metadata, advanced parameters.

#### `/strategy-lab/[id]` — Strategy detail
- **Disposition:** retain (Phase C, P2)
- **Current purpose:** Single strategy card detail.
- **Primary user:** Researcher.
- **Problem:** Structurally fine; lacks an evidence panel (J5).
- **Target group:** Plan.
- **Desktop:** Detail panel with Evidence tab (quality scores, linked backtests —
  Phase D adds the charts).
- **Mobile:** Full-screen push.
- **Consolidate with:** Absorbs `/strategy-lab/[id]/edit` as inline edit.
- **Essential:** Rules summary, quality score, sample size, last validation outcome.
- **Progressive disclosure:** Full backtest results, edit mode, version history.

#### `/strategy-lab/[id]/edit` — Edit strategy
- **Disposition:** consolidate → inline edit in detail (Phase C, P3)
- **Current purpose:** Edit-strategy form.
- **Primary user:** Researcher.
- **Problem:** Separate URL for content that should be inline-editable.
- **Target group:** Plan.
- **Desktop:** Inline edit within the detail panel.
- **Mobile:** Edit sheet.
- **Consolidate with:** `/strategy-lab/[id]`.
- **Essential:** Same fields as create, pre-filled.
- **Progressive disclosure:** Advanced parameters, change history.

---

## 3. Signals

Group question: *"What is the market and the system telling me?"* One unified signal
inbox with source filters replaces four overlapping feeds.

#### `/tradingview-signals` — TradingView Signals
- **Disposition:** redesign → Signals inbox (Phase C, P1)
- **Current purpose:** Validated TradingView webhook signals list.
- **Primary user:** Daily trader.
- **Problem:** One of four separate signal-ish feeds; no unified triage flow.
- **Target group:** Signals.
- **Desktop:** Unified inbox (source badge "TradingView"), sorted by freshness +
  confidence; detail panel with evidence (J1/J5).
- **Mobile:** Card inbox; tap triage; full-screen detail.
- **Consolidate with:** `/alerts`, `/alerts/review`, scanner output (one inbox).
- **Essential:** Symbol, direction, source badge, confidence, freshness pill.
- **Progressive disclosure:** Parsed payload, matched playbook, detector evidence,
  signed-webhook provenance, orchestration trace.

#### `/alerts` — Alerts
- **Disposition:** consolidate → Signals inbox (Phase C, P1)
- **Current purpose:** In-app alert list.
- **Primary user:** Daily trader.
- **Problem:** Duplicate feed concept; separated from its own review page.
- **Target group:** Signals.
- **Desktop:** Inbox rows with source badge "Watcher / In-app".
- **Mobile:** Same inbox.
- **Consolidate with:** `/tradingview-signals`, `/alerts/review`.
- **Essential:** Symbol, alert type, freshness, triage status.
- **Progressive disclosure:** Alert payload, generating scan configuration.

#### `/alerts/review` — Setup Alert Review
- **Disposition:** consolidate → inbox detail panel (Phase C, P1)
- **Current purpose:** Triage a setup alert; create a paper draft from it.
- **Primary user:** Daily trader.
- **Problem:** Review lives on a different URL from the list; an extra hop in J1.
- **Target group:** Signals.
- **Desktop:** Detail panel of the inbox; actions: Create draft / Plan trade /
  Dismiss with reason chips.
- **Mobile:** Full-screen detail push.
- **Consolidate with:** Signals inbox (detail layer).
- **Essential:** Setup summary, chart snapshot with levels, primary actions.
- **Progressive disclosure:** Detector scores, similar historical setups, raw data.

#### `/watcher` — Market Watcher Scanner
- **Disposition:** consolidate + rename → Signals → **Scanner** (Phase C, P2)
- **Current purpose:** Configure and run market watcher scans.
- **Primary user:** Researcher.
- **Problem:** Two watcher pages exist (`/watcher`, `/market-watcher`); naming
  collision and split state.
- **Target group:** Signals.
- **Desktop:** Scanner tab: configure + run scan; results feed the unified inbox.
- **Mobile:** Simple run-and-review sheet.
- **Consolidate with:** `/market-watcher` (absorbed).
- **Essential:** Scan scope, run action, last-run time and result count.
- **Progressive disclosure:** Detector configuration, per-detector results, scan
  history.

#### `/market-watcher` — Market Watcher
- **Disposition:** **remove** — merged into Scanner (Phase C, P2)
- **Current purpose:** Watcher output/monitor view.
- **Primary user:** Researcher.
- **Problem:** Near-duplicate of `/watcher`; splits one concept across two pages.
- **Target group:** Signals (function absorbed).
- **Desktop:** Function absorbed by Scanner tab + inbox; redirect kept.
- **Mobile:** —
- **Consolidate with:** `/watcher` (survivor).
- **Essential:** Nothing unique — its outputs render in the inbox.
- **Progressive disclosure:** — (capability fully relocated, nothing dropped).

#### `/market` — Market Monitor
- **Disposition:** simplify → Signals → Markets (Phase C, P2)
- **Current purpose:** Market overview/quotes.
- **Primary user:** Daily trader.
- **Problem:** Standalone monitor with no link into the signal flow.
- **Target group:** Signals.
- **Desktop:** Markets tab: quotes with freshness pills; chart popovers.
- **Mobile:** Compact quote cards.
- **Consolidate with:** `/watchlist` (watchlist is the default filter).
- **Essential:** Symbol, last price, change with sign + icon, freshness pill.
- **Progressive disclosure:** Full chart, related signals and levels for the symbol.

#### `/watchlist` — Watchlist
- **Disposition:** consolidate → Signals → Markets filter (Phase C, P2)
- **Current purpose:** User watchlist of symbols.
- **Primary user:** Daily trader.
- **Problem:** A separate page for what is a filter of the market view.
- **Target group:** Signals.
- **Desktop:** Watchlist as the default filter of the Markets tab.
- **Mobile:** Same; star-to-watch.
- **Consolidate with:** `/market`.
- **Essential:** Watched symbols with price, change, freshness.
- **Progressive disclosure:** Add/remove management, per-symbol signal history.

#### `/paper-signal-orchestration` — Signal Orchestration
- **Disposition:** hide → Signals → Advanced (Phase B, P3)
- **Current purpose:** Signal routing/dedup orchestration diagnostics.
- **Primary user:** Owner/operator.
- **Problem:** Operator diagnostics exposed as a peer of daily-use pages.
- **Target group:** Signals (Advanced).
- **Desktop:** Advanced panel; the per-signal orchestration trace is also linked from
  signal detail (J1 disclosure layer).
- **Mobile:** Accessible via Menu, not the bottom bar.
- **Consolidate with:** None (kept intact, relocated).
- **Essential:** Orchestration health summary when opened.
- **Progressive disclosure:** Full routing traces, dedup decisions, raw events.

---

## 4. Validate

Group question: *"Is this setup actually worth trading?"* The four `paper-validation`
list pages become one pipeline view with stage tabs: Drafts → Queue → Run plans →
Sessions.

#### `/paper-validation/drafts` — Paper Validation Drafts
- **Disposition:** consolidate → Validate, stage 1 (Phase C, P1)
- **Current purpose:** List of paper validation drafts.
- **Primary user:** Researcher.
- **Problem:** Four sibling list pages fragment one pipeline; users lose the thread
  between stages.
- **Target group:** Validate.
- **Desktop:** Pipeline view, "Drafts" stage tab; stage counts visible across the top.
- **Mobile:** Stage tabs as segmented control; card list.
- **Consolidate with:** `/paper-validation/candidates`, `/run-plans`,
  `/run-sessions` (one pipeline view).
- **Essential:** Setup name, symbol, draft status, age.
- **Progressive disclosure:** Draft parameters, source alert, edit history.

#### `/paper-validation/drafts/[draftId]` — Paper Draft Detail
- **Disposition:** retain (Phase C, P1)
- **Current purpose:** Draft detail; mark ready for validation.
- **Primary user:** Researcher.
- **Problem:** Structurally fine; the forward action should be more prominent.
- **Target group:** Validate.
- **Desktop:** Detail panel; primary action "Queue for validation".
- **Mobile:** Full-screen push.
- **Consolidate with:** None (level-3 detail of the pipeline).
- **Essential:** Setup definition, source evidence link, status, primary action.
- **Progressive disclosure:** Full parameters, edit mode, related drafts.

#### `/paper-validation/candidates` — Paper Validation Queue
- **Disposition:** consolidate → Validate, stage 2 (Phase C, P1)
- **Current purpose:** Candidates awaiting validation review.
- **Primary user:** Researcher.
- **Problem:** Same fragmentation; priority ordering lives on yet another page
  (`/validation-priority`).
- **Target group:** Validate.
- **Desktop:** "Queue" stage tab, sorted by priority score by default; score chip
  visible per row.
- **Mobile:** Card list with priority chips.
- **Consolidate with:** Pipeline view; absorbs `/validation-priority` as its sort.
- **Essential:** Candidate name, priority score, status, sample size so far.
- **Progressive disclosure:** Score composition, full candidate history.

#### `/paper-validation/candidates/[candidateId]` — Validation Candidate
- **Disposition:** retain (Phase C, P1)
- **Current purpose:** Candidate detail; create a run plan.
- **Primary user:** Researcher.
- **Problem:** Fine; needs the evidence panel (J5).
- **Target group:** Validate.
- **Desktop:** Detail panel: evidence, history, "Create run plan".
- **Mobile:** Full-screen push.
- **Consolidate with:** None.
- **Essential:** Candidate definition, evidence summary, primary action.
- **Progressive disclosure:** Detector score history, prior run outcomes, raw config.

#### `/paper-validation/run-plans` — Paper Validation Run Plans
- **Disposition:** consolidate → Validate, stage 3 (Phase C, P2)
- **Current purpose:** Run plans list.
- **Primary user:** Researcher.
- **Problem:** Fragmentation (as above).
- **Target group:** Validate.
- **Desktop:** "Run plans" stage tab.
- **Mobile:** Card list.
- **Consolidate with:** Pipeline view.
- **Essential:** Plan name, linked candidate, planned scope, status.
- **Progressive disclosure:** Full plan parameters, schedule details.

#### `/paper-validation/run-plans/[planId]` — Validation Run Plan
- **Disposition:** retain (Phase C, P2)
- **Current purpose:** Run plan detail; start a session.
- **Primary user:** Researcher.
- **Problem:** Fine.
- **Target group:** Validate.
- **Desktop:** Detail panel; primary action "Start session".
- **Mobile:** Full-screen push.
- **Consolidate with:** None.
- **Essential:** Plan summary, linked candidate, primary action.
- **Progressive disclosure:** Full parameters, prior sessions under this plan.

#### `/paper-validation/run-sessions` — Paper Validation Run Sessions
- **Disposition:** consolidate → Validate, stage 4 (Phase C, P2)
- **Current purpose:** Run sessions list.
- **Primary user:** Researcher.
- **Problem:** Fragmentation (as above).
- **Target group:** Validate.
- **Desktop:** "Sessions" stage tab.
- **Mobile:** Card list.
- **Consolidate with:** Pipeline view.
- **Essential:** Session name, linked plan, status, outcome count.
- **Progressive disclosure:** Session timeline, per-outcome details.

#### `/paper-validation/run-sessions/[sessionId]` — Validation Run Session
- **Disposition:** retain (Phase C, P1)
- **Current purpose:** Session detail; record outcomes.
- **Primary user:** Researcher.
- **Problem:** Outcome recording is the payoff moment of the whole pipeline; it
  deserves the best form UX in the app.
- **Target group:** Validate.
- **Desktop:** Detail panel; structured outcome form; "Journal it" follow-through
  linking into J3.
- **Mobile:** Full-screen push; bottom-anchored save.
- **Consolidate with:** None.
- **Essential:** Session status, outcome form, recorded outcomes list.
- **Progressive disclosure:** Full session configuration, raw event log.

#### `/validation-priority` — Validation Priority
- **Disposition:** **remove** — becomes the Queue's sort (Phase C, P2)
- **Current purpose:** Prioritization list for validation candidates.
- **Primary user:** Researcher.
- **Problem:** A whole page for what is a sort order of the queue.
- **Target group:** Validate (function absorbed).
- **Desktop:** Priority becomes the default sort + visible score chip in the Queue
  stage; redirect kept.
- **Mobile:** —
- **Consolidate with:** `/paper-validation/candidates` (survivor).
- **Essential:** Nothing unique — score renders on queue rows.
- **Progressive disclosure:** Score composition moves to candidate detail.

#### `/research-validation` — Research Validation
- **Disposition:** hide → Validate → Advanced (Phase B, P3)
- **Current purpose:** Research-grade validation tooling.
- **Primary user:** Researcher.
- **Problem:** Specialist surface presented as a peer of the core flow.
- **Target group:** Validate (Advanced).
- **Desktop:** Advanced tab within Validate; desktop-first is acceptable.
- **Mobile:** Accessible via Menu; graceful but not optimized.
- **Consolidate with:** None (kept intact, relocated).
- **Essential:** Tool entry points with one-line descriptions.
- **Progressive disclosure:** Everything else (research parameters, outputs).

#### `/backtests/[id]` — Backtest detail
- **Disposition:** retain (Phase D, P2)
- **Current purpose:** Backtest result detail, reached by ID.
- **Primary user:** Researcher.
- **Problem:** Reachable only by direct link; chartless today.
- **Target group:** Validate (linked evidence; also from Playbooks).
- **Desktop:** Standard chart canvas per blueprint §8.1: equity + drawdown, key
  stats (expectancy, profit factor, win rate), parameters; clearly labeled as
  historical simulation (J5 step 3).
- **Mobile:** Full-screen; charts stacked.
- **Consolidate with:** None (linked detail).
- **Essential:** Equity curve, headline stats with sample size, setup identity.
- **Progressive disclosure:** Trade-by-trade list, parameter details, raw output.

---

## 5. Journal

Group question: *"What did I trade, what did I learn, what am I teaching the
system?"*

#### `/journal` — Journal
- **Disposition:** redesign (Phase C, P1)
- **Current purpose:** Trade/lesson journal list and entry.
- **Primary user:** Daily trader.
- **Problem:** Entry friction; not pre-filled from closed paper trades; statistics
  mixed into sibling nav entries.
- **Target group:** Journal.
- **Desktop:** Journal home: entries list + "Needs journaling" prompts; quick-entry
  composer pre-filled from closed trades (J3).
- **Mobile:** Quick-entry optimized: ≤ 2 minutes, one-handed.
- **Consolidate with:** Absorbs `/lessons` as a tab; statistics move to Analyze.
- **Essential:** Needs-journaling queue; entry list (symbol, R-result, rating, date).
- **Progressive disclosure:** Full entry detail, MFE/MAE values, chart snapshot,
  lesson extraction.

#### `/journal/import` — Journal import
- **Disposition:** simplify (Phase E, P3)
- **Current purpose:** Import external trade history; reconciliation reports.
- **Primary user:** Researcher / Owner.
- **Problem:** Utilitarian but sound; wizard steps are unclear.
- **Target group:** Journal.
- **Desktop:** Import wizard (upload → map → reconcile → commit) as a Journal tab.
- **Mobile:** Supported but desktop-preferred; degrades gracefully.
- **Consolidate with:** None (kept as a tab).
- **Essential:** Wizard step indicator, current batch status, reconciliation result.
- **Progressive disclosure:** Row-level reconciliation details, past batches.

#### `/lessons` — Lessons
- **Disposition:** consolidate → Journal → Lessons (Phase C, P2)
- **Current purpose:** Review pending lessons from journaling, analysis, coaching.
- **Primary user:** Daily trader.
- **Problem:** A separate page splits the learning loop from the journal that
  feeds it.
- **Target group:** Journal.
- **Desktop:** Lessons tab with pending-review queue; accept/edit/reject.
- **Mobile:** Card queue, swipe-friendly.
- **Consolidate with:** `/journal` (tab).
- **Essential:** Pending lesson text, source (which trade/session), accept/reject.
- **Progressive disclosure:** Source entry detail, lesson history, related lessons.

#### `/knowledge` — Knowledge Base
- **Disposition:** redesign + rename → Journal → **Teach** (Phase C, P1)
- **Current purpose:** Stored observations/theses (knowledge base).
- **Primary user:** Daily trader.
- **Problem:** Passive "base"; J7 (teach an observation, asset thesis, or setup) has
  no guided capture; the system's interpretation is not confirmed by the user.
- **Target group:** Journal.
- **Desktop:** "Teach" tab: structured capture (type chips: Observation / Asset
  thesis / Setup rule), system echo-back confirmation before save, reviewable list
  with edit/retire.
- **Mobile:** Full-screen capture sheet; ⌘K-equivalent quick action.
- **Consolidate with:** None (promoted within Journal).
- **Essential:** Capture entry point; list of taught items with type and status.
- **Progressive disclosure:** System's structured interpretation, linked trades or
  signals, retirement history.

---

## 6. Analyze

Group question: *"How are I and the system performing?"* One hub with tabs replaces
six scattered analytics pages; each metric has one canonical home (blueprint §8.2).

#### `/analytics` — Analytics
- **Disposition:** redesign → Analyze hub (Phase D, P2)
- **Current purpose:** Setup statistics from proposals/paper trades.
- **Primary user:** Researcher.
- **Problem:** Thin; disconnected from journal statistics; no charting standard;
  overlaps `/journal/statistics` in spirit.
- **Target group:** Analyze.
- **Desktop:** Analyze landing: headline scorecards + links into tabs; charts per
  blueprint §8; chart budget enforced (§8.3).
- **Mobile:** Stacked scorecards; charts full-width.
- **Consolidate with:** Absorbs `/journal/statistics` content as the Statistics tab.
- **Essential:** Headline scorecards (expectancy, profit factor, win rate — each with
  sample size).
- **Progressive disclosure:** Per-setup breakdowns, distributions, trade drill-downs.

#### `/journal/statistics` — Journal statistics
- **Disposition:** consolidate → Analyze → Statistics (Phase D, P2)
- **Current purpose:** Aggregated journal statistics.
- **Primary user:** Researcher.
- **Problem:** Lives under Journal though it is analysis; duplicates `/analytics`.
- **Target group:** Analyze.
- **Desktop:** Statistics tab — canonical home for expectancy, setup win rate,
  profit factor, MFE/MAE scatter, available-profit capture (blueprint §8.2);
  distributions over averages; sample sizes always shown.
- **Mobile:** Scrollable chart stack.
- **Consolidate with:** `/analytics` (one Statistics tab).
- **Essential:** Expectancy, win rate, profit factor with sample sizes.
- **Progressive disclosure:** MFE/MAE scatter, capture distribution, per-setup and
  per-timeframe cuts.

#### `/journal/comparison` — Human vs System
- **Disposition:** retain (promote) → Analyze → Human vs System (Phase D, P1)
- **Current purpose:** Human-versus-system performance comparison.
- **Primary user:** Daily trader.
- **Problem:** Buried as a journal sub-page; this is a headline commercial feature
  (J4).
- **Target group:** Analyze.
- **Desktop:** Side-by-side scorecards (win rate, expectancy, avg R, drawdown,
  sample size) with confidence-interval hints; divergence drill-down linking to
  journal entries.
- **Mobile:** Stacked scorecards; swipe between Human and System.
- **Consolidate with:** None (promoted, canonical home per §8.2).
- **Essential:** Paired scorecards with sample sizes.
- **Progressive disclosure:** Divergence list ("system said skip, human traded" and
  inverse), per-entry links.

#### `/learning-analytics` — Learning Analytics
- **Disposition:** consolidate → Analyze → Learning (Phase D, P2)
- **Current purpose:** Validation-session outcomes and recurring themes.
- **Primary user:** Researcher.
- **Problem:** Overlaps coaching and statistics; three pages tell one story.
- **Target group:** Analyze.
- **Desktop:** Learning tab: outcome trends + recurring themes.
- **Mobile:** Stacked cards.
- **Consolidate with:** `/coaching` (adjacent tabs in one hub).
- **Essential:** Outcome trend, top recurring themes with counts.
- **Progressive disclosure:** Theme drill-down to sessions and lessons.

#### `/coaching` — Coaching
- **Disposition:** simplify → Analyze → Coaching (Phase D, P3)
- **Current purpose:** Behavior patterns from validation sessions.
- **Primary user:** Daily trader.
- **Problem:** Sparse page; unclear how it differs from learning analytics.
- **Target group:** Analyze.
- **Desktop:** Coaching tab: behavioral insights, each with linked evidence.
- **Mobile:** Card list.
- **Consolidate with:** `/learning-analytics` (adjacent tabs; distinct jobs kept:
  behavior vs. outcomes).
- **Essential:** Current top behavioral insights with evidence counts.
- **Progressive disclosure:** Insight history, underlying session links.

#### `/strategy-quality` — Strategy Quality
- **Disposition:** consolidate + rename → Analyze → **Evidence** (Phase D, P2)
- **Current purpose:** Detector quality scores built from validation outcomes.
- **Primary user:** Researcher.
- **Problem:** Island page; this data is exactly what J5 (inspect setup and backtest
  evidence) needs in context elsewhere.
- **Target group:** Analyze.
- **Desktop:** Evidence tab with per-detector score history; the same data powers the
  Evidence panels in Signals, Validate, and Playbooks (canonical home per §8.2).
- **Mobile:** Score cards with trend sparklines.
- **Consolidate with:** Feeds Evidence panels app-wide; canonical view in Analyze.
- **Essential:** Per-detector current score, trend direction, sample size.
- **Progressive disclosure:** Score composition, outcome history, low-sample flags.

---

## 7. Portfolio

Group question: *"What do I hold, and what is my risk state?"*

#### `/portfolio` — Paper Portfolio
- **Disposition:** redesign → Portfolio → Overview (Phase C, P1)
- **Current purpose:** Paper portfolio metrics.
- **Primary user:** Daily trader.
- **Problem:** Metrics grid without hierarchy; no equity curve; separated from
  positions.
- **Target group:** Portfolio.
- **Desktop:** Overview tab — canonical home for equity curve and drawdown
  (blueprint §8.2, charts land in Phase D); open risk; exposure by asset; freshness
  pill on every value.
- **Mobile:** Snapshot cards; equity sparkline first.
- **Consolidate with:** Absorbs `/positions` as a tab and `/risk` state as a tab.
- **Essential:** Account value, open risk, exposure summary, freshness.
- **Progressive disclosure:** Full equity/drawdown charts, per-asset breakdown,
  history.

#### `/positions` — Positions
- **Disposition:** consolidate → Portfolio → Positions (Phase C, P1)
- **Current purpose:** Open paper positions list.
- **Primary user:** Daily trader.
- **Problem:** Positions split from portfolio; two nav entries for one mental model.
- **Target group:** Portfolio.
- **Desktop:** Positions tab: table with plan links; close action behind a
  `ConfirmSheet`.
- **Mobile:** Key-value position cards; close via bottom sheet.
- **Consolidate with:** `/portfolio` (tab).
- **Essential:** Symbol, direction, size, unrealized P&L (sign + icon), stop
  distance.
- **Progressive disclosure:** Entry plan link, fill history, per-position risk
  detail.

#### `/risk` — Risk Settings
- **Disposition:** consolidate (split state/configuration) (Phase C, P1)
- **Current purpose:** Risk limits and current risk state on one page.
- **Primary user:** Daily trader (state) / Owner (configuration).
- **Problem:** Mixes read-mostly *state* (budget used, cooldowns) with dangerous
  *configuration* (limits) on one page.
- **Target group:** Portfolio (state) + Settings (configuration).
- **Desktop:** Risk *state* → Portfolio → Risk & Cooldowns tab (read-only: budget
  consumed, cooldown countdown + cause, current limits — canonical home per §8.2).
  Risk *configuration* → Settings → Risk with `ConfirmSheet` on every change.
- **Mobile:** State tab one-thumb readable (J6); configuration desktop-preferred
  with confirm sheets.
- **Consolidate with:** `/portfolio` (state tab); `/settings` (config tab).
- **Essential (state):** Risk budget consumed today, active cooldowns with countdown
  and cause, current limits (read-only).
- **Progressive disclosure:** Limit change history, cooldown rule definitions,
  per-scope budgets.

---

## 8. Settings

Group question: *"How is my account and platform configured?"* One hub with tabs:
Profile, Risk, Notifications, Team, Billing & Usage, Advanced.

#### `/settings` — Settings
- **Disposition:** retain (as hub) (Phase B, P2)
- **Current purpose:** Account/platform settings.
- **Primary user:** Owner/operator.
- **Problem:** Flat page; gains sections as other routes consolidate here.
- **Target group:** Settings.
- **Desktop:** Settings hub with a left tab rail.
- **Mobile:** Settings list → per-section pages.
- **Consolidate with:** Receives `/billing`, `/usage`, `/invitations`, `/audit`,
  `/exchange`, and risk configuration from `/risk`.
- **Essential:** Section list; account identity; paper-mode status (read-only).
- **Progressive disclosure:** Each section's contents.

#### `/billing` — Billing
- **Disposition:** retain → Settings → Billing & Usage (Phase B, P3)
- **Current purpose:** Subscription and billing management.
- **Primary user:** Owner.
- **Problem:** Fine; a separate nav entry inflates the sidebar.
- **Target group:** Settings.
- **Desktop:** Billing & Usage tab (shared with usage metering).
- **Mobile:** Standard forms.
- **Consolidate with:** `/usage` (one tab).
- **Essential:** Plan name, renewal date, payment status.
- **Progressive disclosure:** Invoices, payment method management.

#### `/usage` — Usage
- **Disposition:** consolidate → Settings → Billing & Usage (Phase B, P3)
- **Current purpose:** API/feature usage metering.
- **Primary user:** Owner.
- **Problem:** A peer nav entry for a read-only meter.
- **Target group:** Settings.
- **Desktop:** Usage panel within the Billing & Usage tab.
- **Mobile:** Read-only cards.
- **Consolidate with:** `/billing`.
- **Essential:** Current-period usage vs. plan limits.
- **Progressive disclosure:** Historical usage, per-feature breakdown.

#### `/invitations` — Team invitations
- **Disposition:** consolidate → Settings → Team (Phase B, P3)
- **Current purpose:** Team invitations management.
- **Primary user:** Owner.
- **Problem:** Single-purpose page; belongs with team management.
- **Target group:** Settings.
- **Desktop:** Team tab: members + invitations.
- **Mobile:** Standard list + invite sheet.
- **Consolidate with:** Settings Team tab.
- **Essential:** Pending invitations, member list.
- **Progressive disclosure:** Invitation history, role details.

#### `/audit` — Audit
- **Disposition:** simplify → Settings → Advanced → Audit (Phase B, P3)
- **Current purpose:** Audit event log.
- **Primary user:** Owner/operator.
- **Problem:** Raw log exposed as a primary nav peer.
- **Target group:** Settings (Advanced).
- **Desktop:** Audit log with filters using the `Timeline` primitive; row → detail;
  desktop-first is acceptable.
- **Mobile:** Read-only filterable list.
- **Consolidate with:** None (relocated).
- **Essential:** Recent events (actor, action, timestamp).
- **Progressive disclosure:** Full event payloads, filter builder, export.

#### `/exchange` — Exchange diagnostics
- **Disposition:** hide → Settings → Advanced → Diagnostics (Phase B, P3)
- **Current purpose:** Exchange connectivity/mode status.
- **Primary user:** Owner/operator.
- **Problem:** A diagnostics page in primary navigation; alarming to non-operators.
- **Target group:** Settings (Advanced).
- **Desktop:** Diagnostics panel: exchange mode (paper-internal etc.), connectivity,
  read-only.
- **Mobile:** Read-only status cards.
- **Consolidate with:** None (relocated).
- **Essential:** Current exchange mode, connectivity status.
- **Progressive disclosure:** Per-provider details, diagnostic history.

---

## 9. Public (unauthenticated)

All five are **retain (Phase E, P3)**, primary user **Visitor**, target group
outside the app shell. Shared problem: functional but below the commercial bar for a
first-impression surface. Shared treatment: one polished auth-card pattern (brand
mark, token-based styling) on desktop; full-height centered on mobile. No
consolidation; no progressive-disclosure needs beyond standard form error states.

#### `/login` — Sign in
- **Essential:** Email/password, submit, forgot-password link.
- **Notes:** First impression for returning users; add product brand mark.

#### `/register` — Create account
- **Essential:** Registration form, one-line product promise.
- **Notes:** Currently no value proposition on the page.

#### `/forgot-password` — Forgot password
- **Essential:** Email field, submit, back-to-login.

#### `/reset-password` — Reset password
- **Essential:** New-password fields, submit.

#### `/verify-email` — Email verification
- **Essential:** Verification status, clear next action (go to sign-in).

---

## 10. Navigation mapping recap (required target navigation)

| Target destination | Routes mapped (primary) |
|---|---|
| **Dashboard** | `/` |
| **Plan** | `/workspace`, `/proposals`, `/approvals`, `/pre-trade`, `/manual-levels`, `/strategy-lab`, `/strategy-lab/new`, `/strategy-lab/[id]`, `/strategy-lab/[id]/edit` |
| **Signals** | `/tradingview-signals`, `/alerts`, `/alerts/review`, `/watcher`, `/market-watcher`, `/market`, `/watchlist`, `/paper-signal-orchestration` |
| **Validate** | `/paper-validation/*` (8 routes), `/validation-priority`, `/research-validation`, `/backtests/[id]` |
| **Journal** | `/journal`, `/journal/import`, `/lessons`, `/knowledge` |
| **Analyze** | `/analytics`, `/journal/statistics`, `/journal/comparison`, `/learning-analytics`, `/coaching`, `/strategy-quality` |
| **Portfolio** | `/portfolio`, `/positions`, `/risk` (state; configuration moves to Settings) |
| **Settings** | `/settings`, `/billing`, `/usage`, `/invitations`, `/audit`, `/exchange`, plus risk configuration |

All 48 authenticated routes are accounted for exactly once; the 5 public routes are
retained outside the app shell. Every consolidation or removal keeps a redirect from
the old URL (blueprint acceptance criterion 2).

## 11. Internal consistency review (Phase 4 checks)

Recorded results of the pre-finalization review:

1. **Route completeness:** all 53 routes (48 authenticated + 5 public) appear
   exactly once above; counts by classification (14+6+7+21+3+2) and by phase
   (8+32+7+6) both total 53. PASS.
2. **Blueprint agreement:** dispositions match the blueprint IA table (§2.1),
   journeys (§4), metric catalog homes (§8.2), and phase definitions (§13). PASS.
3. **Top-level exposure:** exactly 8 level-1 destinations; no route re-enters
   primary navigation. PASS.
4. **Mobile coverage:** signal review (Signals inbox, J1), approval (Plan →
   Approvals, J2), journaling (Journal quick-entry, J3), and portfolio/risk
   monitoring (Portfolio tabs, J6) all have explicit mobile treatments. PASS.
5. **Desktop-first allowances:** research validation, journal import, audit, risk
   configuration, and exchange diagnostics are explicitly desktop-first with
   graceful mobile degradation. PASS.
6. **No capability dropped:** both `remove` routes (`/market-watcher`,
   `/validation-priority`) name their surviving replacement and relocated
   information; every `hide` route keeps a stated access path. PASS.

*End of AT-039 screen inventory v1.*
