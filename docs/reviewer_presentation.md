# AlphaTrade AI — reviewer presentation

**Audience:** a nontechnical reviewer and a technical interviewer. **Format:** 12 slides, approximately 10–12 minutes, followed by the five-minute demonstration below. **Evidence baseline:** October 7, 2026, main `b58beda`; see [current status](current_status.md).

**Present from the [offline slide deck](reviewer_presentation.html) or [12-page PDF](reviewer_presentation.pdf):** use Previous/Next or arrow keys; toggle Notes for the speaker text and Demo script for the timed route/fallback. The deck uses local diagram assets and needs no live application or external fonts. Keep the adjacent `diagrams/` directory when copying it.

Opening sentence: “AlphaTrade brings a trader's market evidence, rules, paper decisions and review into one personal AI workspace.” Explain the user experience first, then the engineering that makes the record trustworthy.

## Slide 1 — Keep the reason with the trade

**Key message:** Traders need continuity between preparation, action and review.

- Charts, chats and notes fragment the decision.
- Entry rationale and risk rules are easy to lose.
- Outcomes alone do not explain decision quality.

**Visual:** A simple three-column diagram: “Prepare → Act → Review,” with “Evidence and rules” spanning all three. This is a concept diagram, not a product screenshot.

**Speaker notes:** “The problem is not a shortage of information. It is keeping the right context attached to a decision. I built AlphaTrade to make that context available before and after a paper trade.”

## Slide 2 — A personal AI trading operating system

**Key message:** The product connects the trader's workflow around durable context.

- One place for strategies, knowledge and Journal history.
- An Agent that explains stored facts and drafts supported actions.
- Paper-first decisions with explicit authority.
- A vision of better assistance, grounded in today's bounded product.

**Visual:** [System overview](diagrams/system-overview.svg), or a six-workspace concept map.

**Speaker notes:** “Operating system describes the product direction: the work is connected rather than spread across isolated tools. The implemented foundation is a paper workspace. Broader assistance and evaluated long-term learning remain roadmap work.”

## Slide 3 — Follow one decision

**Key message:** A reviewable record connects a setup to its eventual learning.

- Inspect strategy rules and market evidence.
- Follow a confirmed opportunity into eligibility and plan authority.
- Compare planned terms with recorded fills in the Journal.
- Ask the Agent to explain the decision and missing evidence.

**Visual:** [Governed workflow](diagrams/governed-workflow.svg); for a large screen, crop only the strategy-to-Journal branch and retain its labels.

**Speaker notes:** “A Candidate is a recorded opportunity, not an order. The historical Nested BTC short gives us an existing example to discuss even when the market has no new setup. Its fill is internal paper simulation.”

## Slide 4 — Six connected workspaces

**Key message:** Each destination answers a practical trader question.

- Dashboard: what needs attention? Agent: what does the record mean?
- Strategies: what are my rules? Knowledge: where is my reference material?
- Journal: what happened and what can I learn?
- Settings: what are my risk, account and notification boundaries?

**Visual:** A sanitized current six-workspace capture using [capture A](screenshots_checklist.md#current-product-capture-plan). Until available, use the workspace table in the [README](../README.md).

**Speaker notes:** “These are six user destinations. Technical and operational tools stay contextual or under Settings. The structure keeps the everyday workflow accessible without requiring the reviewer to understand the backend.”

## Slide 5 — An assistant that can show its sources

**Key message:** Agent explanations are tied to recorded facts and scoped reference material.

- Reads exact strategy, trade and assessment context.
- Separates planned terms from actual fills and protection.
- Shows source references and missing evidence.
- Produces drafts with separate Confirm/Reject controls.

**Visual:** [Agent grounding diagram](diagrams/agent-grounding.svg), or sanitized Agent reply and Stored evidence using capture C.

**Speaker notes:** “The current Agent retrieves bounded SQL text lexically. The Knowledge service separately embeds and searches vectors with Qdrant. They are distinct paths. A fluent answer neither verifies a missing fact nor authorizes a trade.”

## Slide 6 — Control belongs to application services

**Key message:** Deterministic checks govern an action after the assistant has explained it.

- Exact immutable plan revision and content hash.
- Eligibility, account exposure and deterministic risk checks.
- Freshness, expiry, permissions and kill-switch enforcement.
- Durable command identity, reservations and worker fencing.

**Visual:** The authorization-to-execution portion of [governed workflow](diagrams/governed-workflow.svg).

**Speaker notes:** “The same facts and policy should yield the same risk decision. New entry authority needs at least allocation-weighted gross 1R. That is a planned price-distance rule, not a promise about net returns. Real-money execution is refused by the current source.”

## Slide 7 — One web app, an independent worker

**Key message:** Interactive requests and background monitoring share durable records but have separate lifecycles.

- Next.js on Vercel; FastAPI on Render.
- Independent Render paper worker for Watcher and Telegram.
- PostgreSQL for durable facts; Redis for applicable security/cache.
- Public Binance/Bybit evidence and separately governed external channels.

**Visual:** [System overview](diagrams/system-overview.svg), with the [complete external architecture](diagrams/system-architecture.svg) available for technical questions.

**Speaker notes:** “The browser calls the API over authenticated HTTPS. The worker is not inside a browser request. Shared PostgreSQL records coordinate decisions; Redis and Qdrant serve different purposes. The hosting boxes describe the deployment design, while the evidence table states which observations were verified.”

## Slide 8 — Memory that supports review

**Key message:** Persisted history supports learning proposals without silently changing authority.

- Conversations, playbooks and strategy versions preserve context.
- Journal facts retain decision and execution lineage.
- Review distinguishes observations, inference and suggestions.
- Promotion needs validation, paper evidence and a human decision.

**Visual:** [Persistence and learning](diagrams/persistence-learning.svg).

**Speaker notes:** “This is stored application memory, not online model training. A suggested improvement must move through governed validation and promotion. Manual demo tests contribute risk and execution facts, but they are excluded from strategy validation and learning attribution.”

## Slide 9 — Evidence we can describe precisely

**Key message:** Deployment, notification receipt, simulation and exchange orders establish different things.

- Supplied: Render API/worker verified on `b58beda`; migration `a6manualdemo001` applied.
- Supplied: Watcher Telegram notification received; Nested BTC internal paper fill and Journal exist.
- Supplied: BloFin demo account sync succeeded; native order acceptance is still pending.
- GitHub checked: Vercel success; full acceptance CI #783 in progress at the recorded check.

**Visual:** [Evidence table](current_status.md#deployment-and-demonstrated-evidence); add a sanitized receipt only if an authentic capture is available.

**Speaker notes:** “The release supervisor supplied the operational observations; this documentation pass independently checked GitHub. Account sync is a read success. A paper fill is simulation. Neither establishes a protected native demo order. Read the current CI result before presenting and update only from that result.”

## Slide 10 — Engineering quality through explicit contracts

**Key message:** Quality is demonstrated by scoped checks and inspectable failure behavior.

- Typed API and action contracts; tenant/user scoping.
- Immutable evidence and auditable plan/execution identities.
- Backend unit/integration checks and frontend/browser checks.
- Focused development CI separated from full release acceptance.

**Visual:** [Reviewer evidence checklist](reviewer_evidence.md), plus the exact CI run rather than a generic green badge.

**Speaker notes:** “The repository contains Pytest, Ruff, mypy, Vitest, TypeScript and Playwright checks. Historical acceptance records apply to their own bases. This PR only runs documentation checks; it does not launch another complete backend campaign or claim all operational paths passed.”

## Slide 11 — Bounded execution, honest limitations

**Key message:** The current scope is narrow enough to explain and test.

- SFP research/detection exists; automatic SFP execution is unsupported.
- PR220: owner-confirmed BTC MARKET demo entry, one full target.
- No limit entry or complete demo exit/PnL/funding reconciliation in that capability.
- Fresh SFP, Journal repair and native demo acceptance remain separate gates.

**Visual:** The [limitations table](limitations_roadmap.md), or a two-column “Available foundation / next acceptance” diagram.

**Speaker notes:** “The manual test is a separate origin, not a fabricated strategy setup. It has real native dispatch code and simulated protocol tests, but native compatibility and protection still need supervised acceptance. Broader Agent autonomy and complete venue lifecycle support are not today's claims.”

## Slide 12 — Grow from evidence

**Key message:** The next steps improve completeness and evaluated assistance.

- Complete exact-release and fresh operational acceptance.
- Finish supported exchange outcomes before expanding execution scope.
- Evaluate grounding, context continuity and real-device voice.
- Add validated strategy families and governed learning evidence.

**Visual:** Four-stage roadmap: “Accept → Reconcile → Evaluate → Expand.”

**Speaker notes:** “The value today is a connected decision record with understandable assistance and deterministic control. The roadmap grows that foundation through evidence. The next five minutes show how a trader moves through it.”

## Five-minute demonstration script

Use [the full preparation and fallback guide](demo_script.md). Open the six destinations in advance with an existing authorized session and the recorded BTC trade selected. Do not make shared-state changes for the presentation.

| Time | Action | Say |
| --- | --- | --- |
| 0:00–0:45 | Dashboard: paper account, daily attention and market state. | “This is the trader's starting point. Source freshness and paper mode tell us what we can responsibly discuss.” |
| 0:45–1:30 | Strategies: existing Nested version, rules and recorded setup context. | “An approved rule set and a confirmed setup are different stages. This is the version attached to the record.” |
| 1:30–2:30 | Journal: recorded BTC short, plan and internal paper fill; inspect targets if available. | “The Journal keeps intended terms beside recorded execution. This example is internal simulation; any missing projection stays visible.” |
| 2:30–3:45 | Agent: ask “Explain my recorded BTC short, including its plan, authorization, risk and execution venue.” Then “Would that same plan pass the current minimum reward to risk rule?” | “The Agent reads the historical record. Historical authorization and today's entry policy are different questions. Stored evidence lets us inspect its answer.” |
| 3:45–4:30 | Knowledge: an existing playbook and source reference; show preview workflow only if already prepared. | “My reference material is searchable. Preview is a review step; saving and indexing require an explicit action.” |
| 4:30–5:00 | Settings: risk, notification and account context. | “Account sync, paper fills and a native demo order each need their own evidence. The manual demo capability remains separately gated.” |

If the prompt matches multiple trades, select the intended record or use its existing UI context. Do not force the Agent to guess. The documented historical 0.65R example fails today's gross 1R floor **only if the selected stored plan is that example**; let the record establish the terms.

## Fallback: the market is quiet or the app is unavailable

**No fresh setup:** use the historical trade and existing received notification, if they are accessible in the authorized session. State that the event is historical. No new signal, approval or order is needed.

**No authorized runtime access:** open the checked-in architecture diagrams, [dated status](current_status.md) and [full paper closed-loop acceptance record](evidence/full_paper_closed_loop_acceptance_001.json). That record is an offline development rehearsal at base `8673d8f`, not the user's live BTC event or a BloFin fill. Its [verification companion](evidence/full_paper_closed_loop_verification_001.json) records the original test campaign. Show the traceability fields and explain their role without turning recorded tests into current operational acceptance.

The older [product acceptance record](evidence/final_product_acceptance_001.json) includes a BLOCKED verdict and later integration context; preserve both rather than showing only successful fields. The [historical screenshots](screenshots/README.md) may be discussed as dated fixtures in technical Q&A, but are not the main showcase.

No ready-to-play recording of the supplied Telegram/BTC/account-sync observations was available in this checkout. Describe those observations as supplied evidence unless an authentic sanitized recording is provided. Never stage a fictional live setup or imply native order execution from an account screenshot.
