# Reviewer package evidence checklist

Baseline: main `b58beda`, October 7, 2026. This checklist makes the documentation package reviewable; it does not replace application release acceptance.

## Claims and their evidence

| Claim | Evidence | State |
| --- | --- | --- |
| Six workspaces | [Navigation configuration](../frontend/src/components/layout/navigation-config.ts). | Source verified. |
| Independent API and paper worker | [Render Blueprint](../render.yaml), [worker composition](../backend/src/app/workers/paper_worker.py). | Source verified; exact deployment supplied by release supervisor. |
| Governed setup-to-Journal path | [Watcher](../backend/src/app/workers/watcher_paper.py), [AutomatedPaperLoop](../backend/src/app/services/automated_paper_loop.py), [execution service](../backend/src/app/services/execution_service.py). | Source verified; historical internal paper fill/Journal supplied by user. |
| Agent prose and confirmation are separate | [Routes](../backend/src/app/api/routes/interactive_agent.py), [service](../backend/src/app/interactive_agent/service.py), [proposals](../backend/src/app/interactive_agent/proposals.py). | Source verified. |
| Lexical Agent retrieval differs from vector indexing/search | [Default Agent wiring](../backend/src/app/api/routes/interactive_agent.py), [retrieval](../backend/src/app/interactive_agent/retrieval.py), [RagService](../backend/src/app/services/rag_service.py). | Source verified; deployed provider health unknown. |
| Historical trade reads preserve plan/assessment identity | [Recorded-trade grounding](agent_recorded_trade_grounding.md), [historical setup explanation](agent_historical_setup_explanation.md). | Implemented and recorded development evidence; no fresh model/runtime conversation checked here. |
| Gross prospective 1R rule | [Policy implementation](../backend/src/app/services/planned_reward_risk.py). | Source verified; not a guaranteed net outcome. |
| BTC owner-confirmed manual demo capability | [Merged PR220](https://github.com/Fejjii/AlphaTrade-AI/pull/220), [manual service](../backend/src/app/services/manual_demo_service.py). | Implemented; native venue acceptance pending. |
| Real trading refused | [Paper safety](../backend/src/app/core/paper_safety.py). | Source verified; no execution flags changed. |
| Vercel success / full CI state | [Dated status](current_status.md), [snapshot](evidence/reviewer_status_2026-10-07.json). | GitHub checked; full CI pending at check. |
| Notification and account sync | [Supplied observations](current_status.md#deployment-and-demonstrated-evidence). | Reported received Telegram notification and successful demo account sync; no native order inference. |

## Documentation checks

- [x] Start an isolated documentation branch from verified current main.
- [x] Check capabilities, arrows and defaults against source/manifests.
- [x] Remove the obsolete synthetic screenshot from the main showcase; preserve historical captures.
- [x] Create the product-first README, four detailed Mermaid diagrams, 12-slide narrative and timed demo/fallback.
- [x] Parse and render all five diagram sources plus both additional Mermaid fences in the changed guides; validate standalone SVG XML/native labels.
- [x] Validate Markdown file/image links and heading anchors, including a simulated copied repository root.
- [x] Inspect README, architecture, presentation and diagram output in Chromium; verify image loads, all 12 slides, keyboard navigation, Notes/Demo controls and 12-page PDF.
- [x] Confirm the final diff contains only documentation/presentation assets. Publication is recorded in the documentation PR.

The link sweep covers 157 Markdown files; exact reference counts and final publication are recorded in the PR summary. The actual Turing College destination was not inspected; the verification copies the repository layout into a separate temporary root to check portable paths.

The PR summary records actual check results and the final commit. No application tests, migration, deployment, arming, order or new full backend workflow are required by this documentation change.

## Visual gaps and exact capture handoff

No suitable authenticated current-product capture or runtime recording was available to this documentation task. The [current capture plan](screenshots_checklist.md#current-product-capture-plan) specifies routes, context, redaction and filenames for Dashboard, historical Journal, grounded Agent, Knowledge and Settings. Use the rendered diagrams for the presentation until those actual captures exist. Do not substitute a synthetic balance, mock order receipt or an unavailable-service screen.

## Acceptance updates still needed

- [ ] Read the final existing CI #783 result on `b58beda`; do not dispatch another full run from this task.
- [ ] Record bounded fresh SFP recovery acceptance on the intended source policy.
- [ ] Verify the separately supervised historical Journal target repair.
- [ ] Establish native BloFin demo fill/protection acceptance through the owner-confirmed test procedure.
- [ ] Record resolved model/provider health and real-device voice/browser evidence where claimed.

Implementation gaps such as complete exchange exit/PnL/funding reconciliation and broader strategy/Agent execution scope stay on the [roadmap](limitations_roadmap.md); an acceptance update cannot make them implemented.
