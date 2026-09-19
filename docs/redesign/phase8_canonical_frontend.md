# Canonical paper decision frontend

**Status:** implemented on the frontend; several backend HTTP bindings remain missing  
**Task:** AT-055  
**Branch:** `cursor/phase8_canonical_frontend`  
**ADR:** AT-ADR-035  
**Safety:** paper-only. No live execution control. Human approval cannot be skipped by AI.

This is the user-facing decision spine. Architecture docs call the later
frontend consolidation **Phase 12**. The implementing branch name is
`phase8_canonical_frontend`. Backend Phase 8 remains Telegram and is out of
scope here.

## User flow

Market assessment → Candidate → Action eligibility → TradePlan → Human paper
approval → Paper execution status → Outcome → Learning.

Screens:

| Route | Job |
|---|---|
| `/decision` | Queue + stepper + safety rail |
| `/decision/market` | Market quality vs eligibility |
| `/decision/candidates` | Compatibility candidate list |
| `/decision/candidates/[id]` | Candidate workspace (state, setup, evidence, confidence) |
| `/decision/plans/[planId]` | TradePlan (entry/stop/target/sizing/risk/lineage) |
| `/decision/approvals/[approvalId]` | Explicit paper approval (authorization only) |
| `/decision/executions/[executionId]` | Paper order lifecycle |
| `/decision/outcomes/[outcomeId]` | Journal + lesson linkage |
| `/decision/strategy` | Strategy/pattern performance from existing APIs |

Legacy `/workspace`, `/proposals`, `/approvals`, and `/paper-validation/*`
remain functional.

## Bound HTTP (frontend may call)

- `GET /health`
- `GET /risk/kill-switch`
- `POST /market/analyze`
- `GET /paper-validation/candidates`
- `GET /proposals`, `GET /proposals/{id}`, `GET /proposals/{id}/workflow`
- `GET /proposals/{id}/revisions` (existing; newly wired in the frontend client)
- `GET|POST /approvals*`
- `POST /execution/paper`, `GET /execution/orders`, `GET /execution/orders/{id}`
- `GET /journal/entries/{id}`, journal list/prefill
- `GET /lessons/candidates`
- `GET /strategy-quality/summary`
- `GET /learning-analytics/summary`
- `GET /analytics/setups`

## Missing backend HTTP (typed frontend contracts only)

These contracts live in `frontend/src/lib/canonical-decision/types.ts`.
The UI labels them as unbound and does **not** treat compatibility data as
canonical authority.

| Contract | Intended path | Owner |
|---|---|---|
| `CanonicalCandidateContract` | `GET /canonical/candidates` | backend |
| SetupAssessment read | `GET /canonical/setup-assessments/{id}` | backend |
| `CanonicalActionEligibilityContract` | `GET /canonical/candidates/{id}/eligibility` | backend |
| `CanonicalExecutionReceiptContract` | `GET /canonical/executions/{receipt_id}` | backend |

`PaperValidationCandidate` remains a downstream queue (AT-ADR-026). The
candidate workspace is a **compatibility projection**.

Canonical `TradePlanRevision` already has a nested read API under proposals.
There is still no standalone TradePlan create HTTP for the UI; this slice
does not invent one.

## Safety copy the UI must keep

- Market quality does not grant eligibility.
- Kill switch and risk BLOCK are final; no override.
- Human approval is mandatory. AI cannot approve or execute.
- Approval records authorization only and does not place an order.
- Paper execution is simulated. Live execution controls are absent.
- Lessons are review-only and never auto-promote a strategy.

## Tests

- `frontend/src/lib/canonical-decision/canonical-decision.test.ts`
- page tests under `frontend/src/app/(app)/decision/`
- `frontend/e2e/decision-workflow.spec.ts`
- `/decision` added to readiness and iPhone WebKit route lists
