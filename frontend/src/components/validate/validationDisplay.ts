import type {
  PaperValidationCandidateItem,
  PaperValidationDraftItem,
  PaperValidationRunPlanItem,
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";

export function formatConfidence(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "unavailable";
  return `${Math.round(value * 100)}%`;
}

export function formatLevel(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "unavailable";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) return null;
  return new Date(ms).toLocaleString();
}

export function elapsedLabel(
  startedAt: string | null | undefined,
  endedAt: string | null | undefined = null,
  nowMs: number = Date.now(),
): string {
  if (!startedAt) return "unavailable";
  const start = Date.parse(startedAt);
  if (!Number.isFinite(start)) return "unavailable";
  const end = endedAt ? Date.parse(endedAt) : nowMs;
  if (!Number.isFinite(end) || end < start) return "unavailable";
  const minutes = Math.floor((end - start) / 60_000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem ? `${hours}h ${rem}m` : `${hours}h`;
}

export function draftNextAction(draft: PaperValidationDraftItem): string {
  if (draft.is_ready_for_validation) {
    return "Open draft and confirm QUEUE_PAPER_VALIDATION_CANDIDATE to queue.";
  }
  if (draft.missing_checklist_items.length) {
    return "Complete missing checklist items, then mark ready for validation.";
  }
  if (draft.prep_status === "draft" || draft.prep_status === "needs_review") {
    return "Fill thesis, entry, and invalidation criteria before queueing.";
  }
  return "Review draft prep and decide whether to queue for validation.";
}

export function draftMissingStructure(draft: PaperValidationDraftItem): string[] {
  const missing: string[] = [...draft.missing_checklist_items];
  if (!draft.thesis?.trim()) missing.push("thesis");
  if (!draft.entry_criteria?.trim()) missing.push("entry_criteria");
  if (!draft.invalidation_criteria?.trim()) missing.push("invalidation_criteria");
  return missing;
}

export function candidateNextAction(candidate: PaperValidationCandidateItem): string {
  switch (candidate.candidate_status) {
    case "queued":
      return "Open candidate and move status to reviewing when ready.";
    case "reviewing":
      return "Confirm CREATE_PAPER_VALIDATION_RUN_PLAN to create a run plan.";
    case "archived":
      return "Archived — open detail for history only.";
    default:
      return "Review candidate detail.";
  }
}

export function candidateEvidenceCompleteness(candidate: PaperValidationCandidateItem): string {
  const checks = Object.values(candidate.checklist_snapshot ?? {});
  if (!checks.length) return "Checklist snapshot unavailable";
  const done = checks.filter(Boolean).length;
  return `${done}/${checks.length} checklist items complete`;
}

/** Detect incomplete/contradictory run-plan criteria without silently correcting them. */
export function runPlanCriteriaIssues(plan: PaperValidationRunPlanItem): string[] {
  const issues: string[] = [];
  if (!plan.planned_entry_rule?.trim() && !plan.entry_criteria?.trim()) {
    issues.push("Entry criteria missing");
  }
  if (!plan.planned_invalidation_rule?.trim() && !plan.invalidation_criteria?.trim()) {
    issues.push("Invalidation criteria missing");
  }
  if (!plan.planned_success_criteria?.trim()) {
    issues.push("Success criteria missing");
  }
  if (!plan.planned_failure_criteria?.trim()) {
    issues.push("Failure criteria missing");
  }
  if (!plan.observation_timeframe?.trim()) {
    issues.push("Observation timeframe missing");
  }
  if (!plan.validation_window?.trim()) {
    issues.push("Validation window missing");
  }
  if (plan.max_duration_minutes == null) {
    issues.push("Maximum duration missing");
  }
  const success = plan.planned_success_criteria?.trim().toLowerCase() ?? "";
  const failure = plan.planned_failure_criteria?.trim().toLowerCase() ?? "";
  if (success && failure && success === failure) {
    issues.push("Success and failure criteria are identical");
  }
  return issues;
}

export function runPlanNextAction(plan: PaperValidationRunPlanItem): string {
  const issues = runPlanCriteriaIssues(plan);
  if (plan.plan_status === "archived") {
    return "Archived — open detail for history only.";
  }
  if (plan.plan_status === "needs_revision" || issues.length) {
    return "Revise incomplete or contradictory criteria before starting a session.";
  }
  if (plan.plan_status === "planned") {
    return "Confirm START_PAPER_VALIDATION_RUN to start a paper observation session.";
  }
  return "Review run plan detail.";
}

export function runSessionNextAction(session: PaperValidationRunSessionItem): string {
  switch (session.session_status) {
    case "running":
      return "Record observations, then record an outcome before marking completed.";
    case "completed":
      return "Review recorded outcome and journal follow-through if needed.";
    case "cancelled":
      return "Cancelled — open detail for history only.";
    default:
      return "Review run session detail.";
  }
}

export function outcomeStatusLabel(
  result: PaperValidationSessionResultItem | null,
  options?: {
    resultAvailable?: boolean;
    resultNotRecorded?: boolean;
    resultState?: "loading" | "recorded" | "confirmed_not_recorded" | "unavailable";
  },
): string {
  if (result) return result.outcome.replaceAll("_", " ");
  if (options?.resultState === "loading") return "Loading outcome…";
  if (options?.resultState === "unavailable") return "Outcome source unavailable";
  if (options?.resultState === "confirmed_not_recorded") return "Outcome not recorded";
  if (options?.resultState === "recorded") return "Outcome recorded";
  if (options?.resultAvailable === false) return "Outcome source unavailable";
  if (options?.resultNotRecorded || options?.resultAvailable) return "Outcome not recorded";
  return "Outcome status unknown";
}

/** MFE/MAE are not on the paper-validation outcome API — never invent values. */
export function excursionAvailabilityLabel(): string {
  return "unavailable — not provided by validation outcome API";
}
