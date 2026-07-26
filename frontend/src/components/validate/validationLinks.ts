/**
 * Contextual links between Validate stages using IDs the backend already provides.
 * Never invent relationships; missing IDs yield a safe list-route fallback.
 */

export type RelatedObjectKind =
  | "draft"
  | "candidate"
  | "run_plan"
  | "run_session"
  | "source_alert"
  | "backtest";

const LIST_FALLBACKS: Record<RelatedObjectKind, string> = {
  draft: "/paper-validation/drafts",
  candidate: "/paper-validation/candidates",
  run_plan: "/paper-validation/run-plans",
  run_session: "/paper-validation/run-sessions",
  source_alert: "/alerts/review",
  backtest: "/research-validation",
};

export function validateHubHref(): string {
  return "/paper-validation";
}

export function draftDetailHref(draftId: string | null | undefined): string {
  return relatedObjectHref("draft", draftId);
}

export function candidateDetailHref(candidateId: string | null | undefined): string {
  return relatedObjectHref("candidate", candidateId);
}

export function runPlanDetailHref(planId: string | null | undefined): string {
  return relatedObjectHref("run_plan", planId);
}

export function runSessionDetailHref(sessionId: string | null | undefined): string {
  return relatedObjectHref("run_session", sessionId);
}

export function sourceAlertHref(alertId: string | null | undefined): string {
  return relatedObjectHref("source_alert", alertId);
}

export function backtestDetailHref(backtestRunId: string | null | undefined): string {
  return relatedObjectHref("backtest", backtestRunId);
}

/**
 * Build a detail href when an ID exists; otherwise return the stage list fallback.
 * Does not create redirect loops — detail pages link to list/hub, not back to self via empty id.
 */
export function relatedObjectHref(
  kind: RelatedObjectKind,
  id: string | null | undefined,
): string {
  const trimmed = typeof id === "string" ? id.trim() : "";
  if (!trimmed) {
    return LIST_FALLBACKS[kind];
  }
  switch (kind) {
    case "draft":
      return `/paper-validation/drafts/${encodeURIComponent(trimmed)}`;
    case "candidate":
      return `/paper-validation/candidates/${encodeURIComponent(trimmed)}`;
    case "run_plan":
      return `/paper-validation/run-plans/${encodeURIComponent(trimmed)}`;
    case "run_session":
      return `/paper-validation/run-sessions/${encodeURIComponent(trimmed)}`;
    case "source_alert":
      return `/alerts/review?alert=${encodeURIComponent(trimmed)}`;
    case "backtest":
      return `/backtests/${encodeURIComponent(trimmed)}`;
    default: {
      const _exhaustive: never = kind;
      return _exhaustive;
    }
  }
}

export function relatedObjectAvailable(id: string | null | undefined): boolean {
  return typeof id === "string" && id.trim().length > 0;
}
