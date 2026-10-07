# Five-minute product demonstration

Show how AlphaTrade carries a decision from rules and evidence into a reviewable paper record. The tour uses all six workspaces in main `b58beda` (October 7, 2026). It demonstrates traceability and understandable control.

## Prepare an existing context

1. Use an existing authorized staging session, or a disposable local context from [local setup](local_setup.md). State **supervised staging**, **local mock/replay** or **frontend fixture** before discussing results.
2. Confirm the UI's paper posture and current source availability. A stale or unavailable source is a visible limitation, not a reason to invent a current price.
3. Open Dashboard, Strategies, Journal, Agent, Knowledge and Settings in advance. Locate the historical Nested BTC short if it is available in this session; select its exact strategy/trade context.
4. Check [current status](current_status.md) and the exact [CI #783 result](https://github.com/Fejjii/AlphaTrade-AI/actions/runs/37622005520). A pending run cannot be introduced as a pass.
5. Keep a local copy of the [architecture diagrams](architecture.md) and [recorded-evidence fallback](#recorded-evidence-fallback). Obtain fresh captures only through [the capture plan](screenshots_checklist.md).

The tour is observational: it does not need new strategy approval, a worker/Telegram arm, changed risk, a database repair, a seed or an order. The manual BloFin test's **Confirm and submit demo market order** control is outside this demonstration. Its [supervised acceptance guide](manual_blofin_demo_acceptance.md) governs that separate activity.

## Timed route and speaker wording

| Time | Workspace | What to show and say |
| --- | --- | --- |
| 0:00–0:45 | Dashboard `/` | “This is the paper account and today's attention. These source labels tell us whether we have usable market evidence.” |
| 0:45–1:30 | Strategies `/strategies` | Show an existing version, its actual rules and setup context. “Rules, approval and a confirmed setup are different stages.” |
| 1:30–2:30 | Journal `/journal` | Open the recorded BTC short. Compare planned entry/stop/targets with actual recorded fill and venue. “This fill is internal paper simulation. Missing target projection or outcome data remains visible.” |
| 2:30–3:45 | Agent `/agent` | Ask the two prompts below and inspect Stored evidence. “The answer follows this historical record, rather than substituting today's setup.” |
| 3:45–4:30 | Knowledge `/knowledge` | Show an existing playbook and source reference. If a file preview is already prepared, show extracted text without saving. “Preview is separate from ingestion.” |
| 4:30–5:00 | Settings `/settings` | Show risk and notification controls plus account context. “Demo account sync is a read result; native demo execution remains a separate acceptance gate.” |

Agent prompts with the recorded trade selected:

> Explain my recorded BTC short, including its plan, authorization, risk and execution venue.
>
> Would that same plan pass the current minimum reward to risk rule?

If multiple records match, choose the exact trade instead of guessing. The known historical 0.65R plan fails today's allocation-weighted gross 1R floor, but quote that comparison only when the selected record confirms those terms. Historical authorization does not grant a new entry under current policy. Targets in a plan are not evidence of venue protection or an exit fill.

For a short confirmation demonstration, inspect an **existing** supported draft and its Confirm/Reject controls. Explain that a separate request rechecks scope, content and action state. Leave the draft unconfirmed during the observational tour.

## Recorded-evidence fallback

| Condition | Use | Explain |
| --- | --- | --- |
| No fresh setup | Existing historical Nested trade and received Telegram notification, if accessible. | “This is a recorded event. We are reviewing it, not claiming a fresh signal.” |
| Market evidence unavailable | Existing Journal/strategy records and [governed workflow diagram](diagrams/governed-workflow.svg). | “Historical facts remain reviewable; current eligibility cannot be inferred from them.” |
| App/session unavailable | [README](../README.md), [system overview](diagrams/system-overview.svg), [Agent diagram](diagrams/agent-grounding.svg), [current status](current_status.md). | “This is the source-verified architecture and dated evidence, not a live UI demonstration.” |
| Technical proof requested offline | [Closed-loop acceptance JSON](evidence/full_paper_closed_loop_acceptance_001.json) and [verification JSON](evidence/full_paper_closed_loop_verification_001.json). | “These preserve an offline development rehearsal at base `8673d8f`; they are not the supplied live BTC event or native BloFin execution.” |

For the five-minute offline version: spend 45 seconds on the workspace table, 45 seconds on the overview, 60 seconds on governed workflow, 75 seconds on Agent grounding, 45 seconds on the recorded acceptance fields, and 30 seconds on the status/roadmap. The historical [product acceptance JSON](evidence/final_product_acceptance_001.json) records a BLOCKED verdict and later integration context; keep those qualifications visible.

No runtime recording of the supplied Telegram notification, BTC trade or account sync is checked into this repository. If those records cannot be opened, state the supplied observations and their verification limits. Use accurate diagrams, not fabricated screenshots or exchange receipts.

## Technical follow-up

Use [architecture](architecture.md) to discuss storage, provider boundaries, leases, fencing and immutable plans. Use [Agent](agent_workflow.md) and [retrieval](rag_system.md) to explain default lexical retrieval versus Qdrant indexing/search. Browser voice dictation/playback is implemented, but actual microphone/service/Safari/iOS acceptance is not established by fixture screenshots; text is the reliable presentation fallback.

For slide wording and notes, use [the reviewer presentation](reviewer_presentation.md). For claims still awaiting evidence, use [the evidence checklist](reviewer_evidence.md).
