# Canonical paper decision frontend

**Status:** integrated on `cursor/phase8_final_integration`  
**Task:** AT-057 (source PR #98 claimed AT-055)  
**Branch:** `cursor/phase8_final_integration`  
**ADR:** AT-ADR-037  
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
- `POST /execution/paper-plan` (canonical TradePlan execution)
- `GET /execution/orders`, `GET /execution/orders/{id}` (compatibility)
- `GET /canonical/candidates`, `GET /canonical/candidates/{id}`
- `GET /canonical/setup-assessments/{id}`
- `GET /canonical/candidates/{id}/eligibility`
- `GET /canonical/executions/{receipt_id}`
- `GET /canonical/learning/strategy-stats`
- `GET /journal/entries/{id}`, journal list/prefill
- `GET /lessons/candidates`
- `GET /strategy-quality/summary`
- `GET /learning-analytics/summary`
- `GET /analytics/setups`

## Canonical HTTP (bound on the Phase 8 RC)

Canonical TradePlan execution uses `POST /execution/paper-plan` only.
Legacy `POST /execution/paper` remains compatibility-only and must not
execute a canonical TradePlan.

`PaperValidationCandidate` remains a downstream queue (AT-ADR-026). The
candidate workspace still shows that compatibility projection beside the
canonical Candidate read API.

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
