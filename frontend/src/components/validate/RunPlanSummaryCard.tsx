import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationRunPlanItem } from "@/lib/api/types";
import {
  formatConfidence,
  formatTimestamp,
  runPlanCriteriaIssues,
  runPlanNextAction,
} from "@/components/validate/validationDisplay";
import {
  candidateDetailHref,
  relatedObjectAvailable,
  runPlanDetailHref,
} from "@/components/validate/validationLinks";

type RunPlanSummaryCardProps = {
  plan: PaperValidationRunPlanItem;
};

export function RunPlanSummaryCard({ plan }: RunPlanSummaryCardProps) {
  const issues = runPlanCriteriaIssues(plan);
  const created = formatTimestamp(plan.created_at);
  const entry = plan.planned_entry_rule ?? plan.entry_criteria ?? null;
  const invalidation = plan.planned_invalidation_rule ?? plan.invalidation_criteria ?? null;

  return (
    <article
      className="rounded-control border border-border-subtle bg-surface-0/40 px-4 py-3 space-y-3"
      data-testid={`paper-run-plan-${plan.plan_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(plan.condition ?? "unknown")}</Badge>
            <span className="text-sm font-medium text-text-primary">
              {plan.symbol ?? "—"} · {plan.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{plan.direction ?? "—"}</Badge>
          </div>
          <p className="text-caption text-text-muted">Planned {created ?? "unavailable"}</p>
        </div>
        <Badge variant="muted" data-testid={`paper-run-plan-status-${plan.plan_id}`}>
          {plan.plan_status}
        </Badge>
      </div>

      <dl className="grid gap-2 text-caption text-text-muted sm:grid-cols-2">
        <div>
          <dt className="font-medium text-text-secondary">Entry criteria</dt>
          <dd className="mt-0.5 text-text-primary">{entry?.trim() || "missing"}</dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Invalidation criteria</dt>
          <dd className="mt-0.5 text-text-primary">{invalidation?.trim() || "missing"}</dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Success criteria</dt>
          <dd className="mt-0.5 text-text-primary">
            {plan.planned_success_criteria?.trim() || "missing"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Failure criteria</dt>
          <dd className="mt-0.5 text-text-primary">
            {plan.planned_failure_criteria?.trim() || "missing"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Observation timeframe</dt>
          <dd className="mt-0.5 text-text-primary">{plan.observation_timeframe ?? "missing"}</dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Validation window</dt>
          <dd className="mt-0.5 text-text-primary">{plan.validation_window ?? "missing"}</dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Maximum duration</dt>
          <dd className="mt-0.5 text-text-primary">
            {plan.max_duration_minutes == null ? "missing" : `${plan.max_duration_minutes} min`}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Confidence</dt>
          <dd className="mt-0.5 text-text-primary">{formatConfidence(plan.confidence)}</dd>
        </div>
      </dl>

      {issues.length ? (
        <div
          role="status"
          data-testid={`paper-run-plan-issues-${plan.plan_id}`}
          className="rounded-control border border-warning-border bg-warning-muted/30 px-3 py-2 text-caption text-warning"
        >
          Incomplete or contradictory criteria: {issues.join("; ")}
        </div>
      ) : null}

      <p className="text-caption text-text-muted" data-testid={`paper-run-plan-next-${plan.plan_id}`}>
        Next action: <span className="text-text-primary">{runPlanNextAction(plan)}</span>
      </p>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href={runPlanDetailHref(plan.plan_id)}
          className="inline-flex min-h-11 items-center underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          View run plan detail
        </Link>
        {relatedObjectAvailable(plan.candidate_id) ? (
          <Link
            href={candidateDetailHref(plan.candidate_id)}
            className="inline-flex min-h-11 items-center text-text-secondary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Related candidate
          </Link>
        ) : (
          <span className="inline-flex min-h-11 items-center text-text-muted">
            Related candidate unavailable
          </span>
        )}
      </div>
    </article>
  );
}
