import type { PaperValidationRunPlanItem } from "@/lib/api/types";

export type CandidateRunPlanRelation =
  | { kind: "source_unavailable" }
  | { kind: "none" }
  | {
      kind: "active" | "historical";
      planId: string;
      status: PaperValidationRunPlanItem["plan_status"];
      createdAt: string;
    };

const ACTIVE_STATUSES = new Set<PaperValidationRunPlanItem["plan_status"]>([
  "planned",
  "needs_revision",
]);

function createdAtMs(plan: PaperValidationRunPlanItem): number {
  const ms = Date.parse(plan.created_at);
  return Number.isFinite(ms) ? ms : Number.NEGATIVE_INFINITY;
}

/**
 * Prefer an active plan (planned / needs_revision). Archived plans never replace
 * an active plan. Among peers, prefer newest by created_at (explicit sort).
 */
export function selectRunPlanForCandidate(
  candidateId: string,
  runPlansAvailable: boolean,
  plans: PaperValidationRunPlanItem[] | null | undefined,
): CandidateRunPlanRelation {
  if (!runPlansAvailable) {
    return { kind: "source_unavailable" };
  }
  const related = (plans ?? []).filter((plan) => plan.candidate_id === candidateId);
  if (!related.length) {
    return { kind: "none" };
  }

  const active = related
    .filter((plan) => ACTIVE_STATUSES.has(plan.plan_status))
    .sort((a, b) => createdAtMs(b) - createdAtMs(a));
  if (active[0]) {
    return {
      kind: "active",
      planId: active[0].plan_id,
      status: active[0].plan_status,
      createdAt: active[0].created_at,
    };
  }

  const historical = related
    .filter((plan) => plan.plan_status === "archived")
    .sort((a, b) => createdAtMs(b) - createdAtMs(a));
  if (historical[0]) {
    return {
      kind: "historical",
      planId: historical[0].plan_id,
      status: historical[0].plan_status,
      createdAt: historical[0].created_at,
    };
  }

  // Unexpected statuses: still pick newest explicitly labelled historical fallback.
  const newest = [...related].sort((a, b) => createdAtMs(b) - createdAtMs(a))[0]!;
  return {
    kind: "historical",
    planId: newest.plan_id,
    status: newest.plan_status,
    createdAt: newest.created_at,
  };
}

export function buildCandidateRunPlanMap(
  runPlansAvailable: boolean,
  plans: PaperValidationRunPlanItem[] | null | undefined,
  candidateIds: string[],
): Map<string, CandidateRunPlanRelation> {
  const map = new Map<string, CandidateRunPlanRelation>();
  for (const candidateId of candidateIds) {
    map.set(candidateId, selectRunPlanForCandidate(candidateId, runPlansAvailable, plans));
  }
  return map;
}
