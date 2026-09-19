import type { BindingStatus } from "@/lib/canonical-decision/types";

export type BackendBinding = {
  id: string;
  title: string;
  status: BindingStatus;
  /** Existing or intended HTTP path. */
  path: string;
  owner: "backend" | "frontend";
  usedByFrontend: boolean;
  notes: string;
};

/**
 * Honest inventory of decision-workflow HTTP authority.
 * Bound paths may be called. Missing paths are typed contracts only.
 */
export const DECISION_BACKEND_BINDINGS: readonly BackendBinding[] = [
  {
    id: "health",
    title: "Runtime paper posture",
    status: "bound",
    path: "GET /health",
    owner: "backend",
    usedByFrontend: true,
    notes: "Fail-closed paper + real_trading_enabled truth for the safety rail.",
  },
  {
    id: "kill-switch",
    title: "Organization kill switch",
    status: "bound",
    path: "GET /risk/kill-switch",
    owner: "backend",
    usedByFrontend: true,
    notes: "Server-side kill switch; BLOCK is final. No UI override.",
  },
  {
    id: "market-analyze",
    title: "Market assessment",
    status: "bound",
    path: "POST /market/analyze",
    owner: "backend",
    usedByFrontend: true,
    notes: "Market quality / setup signals only. Does not grant action eligibility.",
  },
  {
    id: "paper-validation-candidates",
    title: "Legacy paper-validation candidates",
    status: "partial",
    path: "GET /paper-validation/candidates",
    owner: "backend",
    usedByFrontend: true,
    notes:
      "Compatibility queue only. Not canonical Candidate authority (AT-ADR-026). Labeled as such in the UI.",
  },
  {
    id: "canonical-candidates",
    title: "Canonical Candidate workspace API",
    status: "bound",
    path: "GET /canonical/candidates",
    owner: "backend",
    usedByFrontend: true,
    notes: "Read-only CandidateLifecycleService surface. Does not mint Candidate identity.",
  },
  {
    id: "setup-assessment",
    title: "SetupAssessment reads",
    status: "bound",
    path: "GET /canonical/setup-assessments/{id}",
    owner: "backend",
    usedByFrontend: true,
    notes: "Lineage projection of SetupAssessment identity. Setup truth is independent of eligibility.",
  },
  {
    id: "action-eligibility",
    title: "ActionEligibility evaluation API",
    status: "bound",
    path: "GET /canonical/candidates/{id}/eligibility",
    owner: "backend",
    usedByFrontend: true,
    notes: "Latest ActionEligibilityService evaluation. Live executable stays false.",
  },
  {
    id: "proposals",
    title: "Legacy trade proposals",
    status: "bound",
    path: "GET /proposals",
    owner: "backend",
    usedByFrontend: true,
    notes: "Compatibility TradePlan when CanonicalTradePlanContentV1 revision is absent.",
  },
  {
    id: "trade-plan-revisions",
    title: "Immutable TradePlan revisions",
    status: "bound",
    path: "GET /proposals/{id}/revisions",
    owner: "backend",
    usedByFrontend: true,
    notes: "Existing nested revision API. No standalone TradePlan list/create HTTP for the UI.",
  },
  {
    id: "approvals",
    title: "Human paper approvals",
    status: "bound",
    path: "GET|POST /approvals",
    owner: "backend",
    usedByFrontend: true,
    notes: "Human authorization only. APPROVE never places an order.",
  },
  {
    id: "paper-execution",
    title: "Canonical paper plan execution",
    status: "bound",
    path: "POST /execution/paper-plan",
    owner: "backend",
    usedByFrontend: true,
    notes:
      "Canonical TradePlan execution. Identity + idempotency only. Legacy POST /execution/paper is compatibility-only and must not execute a canonical TradePlan.",
  },
  {
    id: "legacy-paper-execution",
    title: "Legacy paper order placement",
    status: "partial",
    path: "POST /execution/paper",
    owner: "backend",
    usedByFrontend: false,
    notes: "Compatibility path for PVC/proposal paper orders. Not used for canonical TradePlan execution.",
  },
  {
    id: "paper-orders",
    title: "Paper order lifecycle",
    status: "bound",
    path: "GET /execution/orders",
    owner: "backend",
    usedByFrontend: true,
    notes: "Compatibility paper-order lifecycle. Canonical receipts use GET /canonical/executions/{receipt_id}.",
  },
  {
    id: "execution-receipts",
    title: "Canonical ExecutionReceipt",
    status: "bound",
    path: "GET /canonical/executions/{receipt_id}",
    owner: "backend",
    usedByFrontend: true,
    notes: "Paper execution receipt + projection. Live executable stays false.",
  },
  {
    id: "canonical-learning-stats",
    title: "Canonical strategy/pattern statistics",
    status: "bound",
    path: "GET /canonical/learning/strategy-stats",
    owner: "backend",
    usedByFrontend: true,
    notes: "LearningQueryService rollup. Slice 84 /learning-analytics remains a compatibility analytics view.",
  },
  {
    id: "canonical-learning-records",
    title: "Canonical learning records",
    status: "bound",
    path: "GET /canonical/learning/records/{candidate_id}",
    owner: "backend",
    usedByFrontend: true,
    notes: "Candidate-scoped LearningQueryService attribution. Review-only; no auto-promotion.",
  },
  {
    id: "positions",
    title: "Paper positions",
    status: "bound",
    path: "GET /positions",
    owner: "backend",
    usedByFrontend: true,
    notes: "Paper close remains on the legacy positions surface.",
  },
  {
    id: "journal",
    title: "Journal outcome linkage",
    status: "bound",
    path: "GET /journal/entries/{id}",
    owner: "backend",
    usedByFrontend: true,
    notes: "Prefill + linked_proposal_id / linked_position_id provide outcome lineage.",
  },
  {
    id: "lessons",
    title: "Learning / lesson candidates",
    status: "bound",
    path: "GET /lessons/candidates",
    owner: "backend",
    usedByFrontend: true,
    notes: "Review-only. No automatic strategy promotion.",
  },
  {
    id: "strategy-quality",
    title: "Strategy / pattern quality",
    status: "bound",
    path: "GET /strategy-quality/summary",
    owner: "backend",
    usedByFrontend: true,
    notes: "Existing detector quality API.",
  },
  {
    id: "learning-analytics",
    title: "Learning analytics",
    status: "bound",
    path: "GET /learning-analytics/summary",
    owner: "backend",
    usedByFrontend: true,
    notes: "Existing setup/outcome analytics.",
  },
  {
    id: "setup-analytics",
    title: "Setup performance",
    status: "bound",
    path: "GET /analytics/setups",
    owner: "backend",
    usedByFrontend: true,
    notes: "Existing setup statistics.",
  },
] as const;

export function missingBindings(): BackendBinding[] {
  return DECISION_BACKEND_BINDINGS.filter((item) => item.status === "missing");
}

export function partialBindings(): BackendBinding[] {
  return DECISION_BACKEND_BINDINGS.filter((item) => item.status === "partial");
}

export function boundBindings(): BackendBinding[] {
  return DECISION_BACKEND_BINDINGS.filter((item) => item.status === "bound");
}
