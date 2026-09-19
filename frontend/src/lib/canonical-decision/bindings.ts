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
    status: "missing",
    path: "GET /canonical/candidates",
    owner: "backend",
    usedByFrontend: false,
    notes:
      "Phase 6 CandidateLifecycleService has no HTTP surface. Frontend contract: CanonicalCandidateContract.",
  },
  {
    id: "setup-assessment",
    title: "SetupAssessment reads",
    status: "missing",
    path: "GET /canonical/setup-assessments/{id}",
    owner: "backend",
    usedByFrontend: false,
    notes: "Setup truth is independent of eligibility. No public read API yet.",
  },
  {
    id: "action-eligibility",
    title: "ActionEligibility evaluation API",
    status: "missing",
    path: "GET /canonical/candidates/{id}/eligibility",
    owner: "backend",
    usedByFrontend: false,
    notes:
      "ActionEligibilityService is in-memory only. Frontend projects a labeled compatibility view from kill switch, risk_result, approval, and health.",
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
    title: "Paper order placement",
    status: "bound",
    path: "POST /execution/paper",
    owner: "backend",
    usedByFrontend: true,
    notes: "Requires prior human approval. Paper-only. No live execution route is exposed.",
  },
  {
    id: "paper-orders",
    title: "Paper order lifecycle",
    status: "bound",
    path: "GET /execution/orders",
    owner: "backend",
    usedByFrontend: true,
    notes: "Compatibility execution status. Canonical ExecutionReceipt HTTP is missing.",
  },
  {
    id: "execution-receipts",
    title: "Canonical ExecutionReceipt",
    status: "missing",
    path: "GET /canonical/executions/{receipt_id}",
    owner: "backend",
    usedByFrontend: false,
    notes: "Phase 1 ExecutionReceipt/transition HTTP is not mounted for the UI.",
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
