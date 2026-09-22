# Canonical paper decision frontend

**Status:** decision pages bound to canonical GET APIs on `cursor/final_canonical_ux-1b0c`  
**Task:** AT-059 (follow-on to AT-057 / AT-ADR-037)  
**Branch:** `cursor/final_canonical_ux-1b0c`  
**ADR:** AT-ADR-037  
**Safety:** paper-only. No live execution control. Human approval cannot be skipped by AI.

This is the user-facing decision spine. Architecture docs call the later
frontend consolidation **Phase 12**. Canonical Candidate, eligibility,
execution receipt, learning record, and strategy-stats HTTP reads are bound.
Telegram enablement remains out of scope.

## User flow

Market assessment → Candidate → Action eligibility → TradePlan → Human paper
approval → Paper execution status → Outcome → Learning.

Screens:

| Route | Job |
|---|---|
| `/decision` | Canonical + compatibility queue, stepper, safety rail |
| `/decision/market` | Canonical USD-M evidence + freshness vs eligibility |
| `/decision/candidates` | Canonical Candidate list plus PVC compatibility items |
| `/decision/candidates/[id]` | Canonical Candidate workspace (setup, eligibility, learning) with PVC fallback |
| `/decision/plans/[planId]` | Compatibility TradePlan (entry/stop/target/sizing/risk/lineage) |
| `/decision/approvals/[approvalId]` | Explicit paper approval (authorization only) |
| `/decision/executions/[executionId]` | Canonical receipt first; compatibility paper-order fallback |
| `/decision/outcomes/[outcomeId]` | Journal + canonical learning record |
| `/decision/strategy` | Canonical LearningQueryService stats, continuous paper evaluation, plus compatibility analytics |

Legacy `/workspace`, `/proposals`, `/approvals`, and `/paper-validation/*`
remain compatibility views and are labeled as such.

## Bound HTTP (frontend may call)

- `GET /health`
- `GET /risk/kill-switch`
- `GET /canonical/evidence`
- `GET /canonical/market-status` (continuous USD-M monitor; replay is never a live mark)
- `GET /paper-validation/candidates` (compatibility)
- `POST /market/analyze` (legacy `/market` monitor only; not canonical current price)
- `GET /paper-validation/candidates` (compatibility)
- `GET /proposals`, `GET /proposals/{id}`, `GET /proposals/{id}/workflow` (compatibility)
- `GET /proposals/{id}/revisions` (compatibility nested revision read)
- `GET|POST /approvals*`
- `POST /execution/paper-plan` (canonical TradePlan execution; decision workflow only)
- `GET /execution/orders`, `GET /execution/orders/{id}` (compatibility)
- `GET /canonical/candidates`, `GET /canonical/candidates/{id}`
- `GET /canonical/setup-assessments/{id}`
- `GET /canonical/candidates/{id}/eligibility`
- `GET /canonical/executions/{receipt_id}`
- `GET /canonical/learning/records/{candidate_id}`
- `GET /canonical/learning/strategy-stats`
- `GET /canonical/paper-evaluation/summary`
- `GET /journal/entries/{id}`, journal list/prefill
- `GET /lessons/candidates`
- `GET /strategy-quality/summary`
- `GET /learning-analytics/summary`
- `GET /analytics/setups`

## Canonical HTTP

Canonical TradePlan execution uses `POST /execution/paper-plan` only.
`PaperApprovalPanel` does not fall back to legacy `POST /execution/paper`.
That path remains on the compatibility proposals/approvals views.

`PaperValidationCandidate` remains a downstream queue (AT-ADR-026) and is
labeled as a compatibility projection.

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
- `frontend/src/components/canonical-decision/MarketQualityCard.test.tsx`
- page tests under `frontend/src/app/(app)/decision/`
- `frontend/src/components/canonical-decision/PaperApprovalPanel.test.tsx`
- `frontend/e2e/decision-workflow.spec.ts`
- `/decision` added to readiness and iPhone WebKit route lists
