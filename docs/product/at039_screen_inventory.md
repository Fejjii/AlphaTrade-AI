# AT-039 — Screen Inventory and Route Dispositions (v1)

Status: PROPOSED (planning document — no code changes authorized by this document)
Task: AT-039
Scope: Audit of every current frontend route with a disposition for the premium
redesign. Companion document: `docs/product/at039_premium_ui_ux_blueprint.md`.

Baseline verified at commit `0e45ef0` (main): **48 authenticated routes** under
`frontend/src/app/(app)/` and **5 public routes** under `frontend/src/app/(public)/`,
53 total. Route purposes below were read from each `page.tsx` (headings, empty-state
copy, and nav labels in `frontend/src/components/layout/nav-items.ts`).

## Classification key

- **retain** — keep as its own URL and surface, minor polish only
- **simplify** — keep, but reduce visible density/controls (progressive disclosure)
- **redesign** — keep the job-to-be-done, rebuild the surface
- **consolidate** — merge into another destination as a tab, panel, step, or filter
- **rename** — user-facing name changes (may combine with another disposition)
- **hide** — keep functional but move behind an explicit "Advanced" affordance
- **remove** — route retired; its function is absorbed elsewhere (redirect kept)

Priorities: **P1** = core spine (must ship for the redesign to hold together),
**P2** = strong contributor to perceived quality, **P3** = polish / later phase.
"Desktop" and "Mobile" columns give the target treatment. All consolidations keep a
redirect from the old URL.

## Disposition summary

| Disposition | Count |
|---|---|
| retain | 14 |
| simplify | 7 |
| redesign | 8 |
| consolidate | 19 |
| rename (combined with above) | 4 |
| hide | 3 |
| remove | 2 |
| **Total routes** | **53** |

(Rename overlaps other dispositions; counts above assign each route one primary
disposition, with renames noted inline.)

---

## 1. Dashboard

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/` | **redesign** | Dashboard: strategy tiles, portfolio summary, misc. panels | Generic tile grid; doesn't answer "what needs my decision now"; equal weight to everything | Attention-first layout: needs-decision queue (approvals, unjournaled trades, fresh signals), portfolio/risk snapshot, freshness strip | Stacked cards, decision queue first; one-thumb triage | P1 |

## 2. Plan

Target group question: *"What trade am I preparing, and is it approved?"*

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/workspace` | **redesign + rename** → Plan hub | "AI Trading Workspace" — AI-assisted analysis/plan creation | Vague name; overlaps proposals; unclear entry point for the core J2 journey | Plan hub landing: new-ticket action, in-flight plans, approvals badge | Bottom-bar center tab; ticket as full-screen stepped flow | P1 |
| `/proposals` | **consolidate** → Plan → Proposals | Trade proposal list + detail ("Legacy proposal flow" in nav) | User-facing "legacy" section; split from approvals though it's one pipeline | List + right detail panel inside Plan | Card list; full-screen detail push | P1 |
| `/approvals` | **consolidate** → Plan → Approvals | Human review queue for proposals | Separate page for the decision step of the same pipeline | Approvals tab; approval card with evidence + `ConfirmSheet`; "Approve (paper)" labeling | Bottom-anchored approve/reject bar; one-handed | P1 |
| `/pre-trade` | **consolidate** → ticket step | "Pre-Trade Analysis" — standalone risk/size checks | Disconnected calculator; users can skip it; duplicates what the ticket should enforce | Inline checks step inside the Plan ticket (pass/warn/BLOCK rows) | Same, as a ticket step | P1 |
| `/manual-levels` | **simplify** → Plan → Levels | CRUD for manual price levels | Isolated table page; levels are invisible where they matter (charts, tickets) | Levels tab; levels also rendered on all price charts | Simple list + add sheet | P2 |
| `/strategy-lab` | **simplify + rename** → Playbooks | Strategy card library | "Lab" jargon; flat table | Playbooks list with quality/evidence chips | Card list | P2 |
| `/strategy-lab/new` | **consolidate** | Create strategy form | Full page for a short form | Drawer/modal from Playbooks | Full-screen sheet | P3 |
| `/strategy-lab/[id]` | **retain** | Strategy detail | Fine structurally; needs evidence panel (J5) | Detail panel with evidence tab, linked backtests | Full-screen push | P2 |
| `/strategy-lab/[id]/edit` | **consolidate** | Edit strategy form | Separate URL for inline-editable content | Inline edit within detail | Edit sheet | P3 |

## 3. Signals

Target group question: *"What is the market and the system telling me?"* One unified
signal inbox with source filters replaces four overlapping feeds.

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/tradingview-signals` | **redesign** → Signals inbox | Validated TradingView webhook signals | One of four separate signal-ish feeds; no unified triage | Unified inbox (source badge "TradingView"), sorted by freshness + confidence; detail panel with evidence (J1/J5) | Card inbox; swipe/tap triage; full-screen detail | P1 |
| `/alerts` | **consolidate** → Signals inbox | In-app alert list | Duplicate feed concept; separate from its own review page | Inbox rows with source badge "Watcher/In-app" | Same inbox | P1 |
| `/alerts/review` | **consolidate** → inbox detail | "Setup Alert Review" — triage a setup alert, create paper draft | Review lives on a different URL from the list; extra hop | Detail panel of the inbox; actions: Create draft / Plan trade / Dismiss-with-reason | Full-screen detail push | P1 |
| `/watcher` | **consolidate + rename** → Signals → Scanner | "Market Watcher Scanner" — run scans | Two watcher pages exist (`/watcher`, `/market-watcher`); naming collision | Scanner tab: configure + run scan; results feed the inbox | Scanner as simple run-and-review sheet | P2 |
| `/market-watcher` | **remove** (merge into Scanner) | "Market Watcher" — watcher output/monitor | Near-duplicate of `/watcher`; splits one concept across two pages | Function absorbed by Scanner tab + inbox; redirect kept | — | P2 |
| `/market` | **simplify** → Signals → Markets | "Market Monitor" — market overview | Standalone monitor with no link into the signal flow | Markets tab: quotes with freshness pills, chart popovers | Compact quote cards | P2 |
| `/watchlist` | **consolidate** → Signals → Markets | User watchlist of symbols | Separate page for what is a filter of the market view | Watchlist as the default filter of Markets tab | Same; star-to-watch | P2 |
| `/paper-signal-orchestration` | **hide** → Signals → Advanced | "Signal Orchestration" — routing/dedup diagnostics | Operator diagnostics exposed as a peer of user pages | Advanced panel: orchestration trace per signal (also linked from signal detail) | Accessible but not in primary nav | P3 |

## 4. Validate

Target group question: *"Is this setup actually worth trading?"* The four
`paper-validation` list pages become one pipeline view with stage tabs:
Drafts → Queue → Run plans → Run sessions.

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/paper-validation/drafts` | **consolidate** → Validate, stage 1 | Paper validation drafts list | Four sibling pages fragment one pipeline; users lose the thread between stages | Pipeline view, "Drafts" stage tab; stage counts visible | Stage tabs as segmented control; card list | P1 |
| `/paper-validation/drafts/[draftId]` | **retain** | Draft detail; mark ready for validation | Structurally fine; forward action should be more prominent | Detail panel with primary action "Queue for validation" | Full-screen push | P1 |
| `/paper-validation/candidates` | **consolidate** → Validate, stage 2 | "Paper Validation Queue" — candidates awaiting review | Same fragmentation; priority lives on yet another page | "Queue" stage tab, sorted by priority score | Card list, priority chips | P1 |
| `/paper-validation/candidates/[candidateId]` | **retain** | Candidate detail; create run plan | Fine; needs evidence panel (J5) | Detail panel: evidence, history, "Create run plan" | Full-screen push | P1 |
| `/paper-validation/run-plans` | **consolidate** → Validate, stage 3 | Run plans list | Fragmentation (as above) | "Run plans" stage tab | Card list | P2 |
| `/paper-validation/run-plans/[planId]` | **retain** | Run plan detail; start session | Fine | Detail panel, "Start session" | Full-screen push | P2 |
| `/paper-validation/run-sessions` | **consolidate** → Validate, stage 4 | Run sessions list | Fragmentation (as above) | "Sessions" stage tab | Card list | P2 |
| `/paper-validation/run-sessions/[sessionId]` | **retain** | Session detail; record outcomes | Outcome recording is the payoff moment; deserves the best form UX | Detail panel; structured outcome form; "Journal it" follow-through (J3 link) | Full-screen push; bottom-anchored save | P1 |
| `/validation-priority` | **remove** (becomes queue sorting) | "Validation Priority" — prioritization list | A whole page for what is a sort order of the queue | Priority becomes the default sort + a visible score chip in the Queue stage; redirect kept | — | P2 |
| `/research-validation` | **hide** → Validate → Advanced | "Research Validation" — research-grade validation tooling | Specialist surface presented as a peer of the core flow | Advanced tab within Validate | Accessible via Menu, not bottom bar | P3 |
| `/backtests/[id]` | **retain** | Backtest result detail | Reached only by ID; fine as linked detail | Linked from Playbooks and Validate evidence; standard chart canvas (§8 of blueprint) | Full-screen, charts stacked | P2 |

## 5. Journal

Target group question: *"What did I trade, what did I learn, what am I teaching the
system?"*

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/journal` | **redesign** | Trade/lesson journal list + entry | Entry friction; not pre-filled from closed paper trades; stats mixed into nav siblings | Journal home: entries list + "Needs journaling" prompts; quick-entry composer pre-filled from closed trades (J3) | Quick-entry optimized: ≤ 2 min, one-handed | P1 |
| `/journal/import` | **simplify** | Import external trade history; reconciliation reports | Utilitarian but sound; wizard steps unclear | Import wizard (upload → map → reconcile → commit) as Journal tab | Supported but desktop-preferred; graceful | P3 |
| `/lessons` | **consolidate** → Journal → Lessons | Review pending lessons from journaling/analysis/coaching | Separate page splits the learning loop from the journal that feeds it | Lessons tab with pending-review queue and accept/edit/reject | Card queue, swipe-friendly | P2 |
| `/knowledge` | **redesign + rename** → Journal → Teach | "Knowledge Base" — stored observations/theses | Passive "base"; J7 (teach an observation/thesis/setup) has no guided capture; system's interpretation not confirmed | "Teach" tab: structured capture (type chips: Observation / Asset thesis / Setup rule), system echo-back confirmation, reviewable list | Full-screen capture sheet; ⌘K quick action equivalent | P1 |

## 6. Analyze

Target group question: *"How are I and the system performing?"* One hub with tabs
replaces six scattered analytics pages.

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/analytics` | **redesign** → Analyze hub | Setup statistics from proposals/paper trades | Thin, disconnected from journal statistics; no charting standard | Analyze landing: headline scorecards + links into tabs; charts per blueprint §8 | Stacked scorecards; charts full-width | P2 |
| `/journal/statistics` | **consolidate** → Analyze → Statistics | Aggregated journal statistics | Lives under Journal though it is analysis; duplicate of `/analytics` in spirit | Statistics tab: distributions (R-multiple histogram), sample sizes always shown | Scrollable chart stack | P2 |
| `/journal/comparison` | **retain** (promote) → Analyze → Human vs System | "Human vs System" comparison | Buried as a journal sub-page; this is a headline commercial feature (J4) | Side-by-side scorecards + divergence drill-down linking to journal entries | Stacked scorecards, swipe between Human/System | P1 |
| `/learning-analytics` | **consolidate** → Analyze → Learning | Validation-session outcomes, recurring themes | Overlaps coaching and statistics; three pages tell one story | Learning tab: outcome trends + recurring themes | Stacked cards | P2 |
| `/coaching` | **simplify** → Analyze → Coaching | Behavior patterns from validation sessions | Sparse page; unclear how it differs from learning analytics | Coaching tab: behavioral insights with linked evidence | Card list | P3 |
| `/strategy-quality` | **consolidate + rename** → Analyze → Evidence | Detector quality scores from validation outcomes | Island page; this data is what J5 (inspect setup evidence) needs in context | Evidence tab with per-detector score history; same data powers evidence panels in Signals/Validate/Playbooks | Score cards with trend sparklines | P2 |

## 7. Portfolio

Target group question: *"What do I hold, and what is my risk state?"*

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/portfolio` | **redesign** → Portfolio → Overview | Paper portfolio metrics | Metrics grid without hierarchy; no equity curve; separate from positions | Overview tab: equity curve, open risk, exposure by asset; freshness pill on every value | Snapshot cards; equity sparkline first | P1 |
| `/positions` | **consolidate** → Portfolio → Positions | Open paper positions list | Positions split from portfolio; two nav entries for one mental model | Positions tab: table with plan links, close action (confirm sheet) | Key-value position cards; close via bottom sheet | P1 |
| `/risk` | **consolidate** (split) | "Risk Settings" — limits and risk state | Mixes read-mostly *state* (budget used, cooldowns) with dangerous *configuration* on one page | Risk *state* → Portfolio → Risk & Cooldowns tab (read-only: budget consumed, cooldown countdown + cause, current limits). Risk *configuration* → Settings → Risk with confirmation flow | State tab one-thumb readable (J6); config desktop-preferred with confirm sheets | P1 |

## 8. Settings

Target group question: *"How is my account and platform configured?"* One settings
hub with tabs: Profile, Risk, Notifications, Team, Billing & Usage, Advanced.

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/settings` | **retain** (as hub) | Account/platform settings | Flat page; will gain sections as tabs consolidate here | Settings hub with left tab rail | Settings list → per-section pages | P2 |
| `/billing` | **retain** → Settings → Billing & Usage | Subscription and billing | Fine; separate nav entry inflates the sidebar | Billing & Usage tab (with usage) | Standard forms | P3 |
| `/usage` | **consolidate** → Settings → Billing & Usage | API/feature usage metering | Peer nav entry for a read-only meter | Usage panel within Billing & Usage tab | Read-only cards | P3 |
| `/invitations` | **consolidate** → Settings → Team | Team invitations | Single-purpose page; belongs with team management | Team tab: members + invitations | Standard list + invite sheet | P3 |
| `/audit` | **simplify** → Settings → Advanced → Audit | Audit event log | Raw log exposed as a primary nav peer | Audit log with filters + `Timeline` primitive; row → detail | Read-only, filterable list | P3 |
| `/exchange` | **hide** → Settings → Advanced → Diagnostics | "Exchange diagnostics" — connectivity/mode status | Diagnostics page in primary nav; alarming to non-operators | Diagnostics panel: mode (paper-internal etc.), connectivity, read-only | Read-only status cards | P3 |

## 9. Public (unauthenticated)

| Route | Disposition | Current purpose | Usability concern | Desktop | Mobile | Priority |
|---|---|---|---|---|---|---|
| `/login` | **retain** | Sign in | Functional; visual polish below commercial bar (first impression surface) | Polished auth card: brand mark, token-based styling | Same, full-height centered | P3 |
| `/register` | **retain** | Create account | Same as login; value proposition absent | Auth card + one-line product promise | Same | P3 |
| `/forgot-password` | **retain** | Request reset email | Fine | Match auth card pattern | Same | P3 |
| `/reset-password` | **retain** | Set new password | Fine | Match auth card pattern | Same | P3 |
| `/verify-email` | **retain** | Email verification landing | Fine | Match auth card pattern; clear next action | Same | P3 |

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

*End of AT-039 screen inventory v1.*
