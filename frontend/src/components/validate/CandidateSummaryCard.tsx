import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationCandidateItem } from "@/lib/api/types";
import {
  candidateEvidenceCompleteness,
  candidateNextAction,
  formatConfidence,
  formatTimestamp,
} from "@/components/validate/validationDisplay";
import {
  backtestDetailHref,
  candidateDetailHref,
  draftDetailHref,
  relatedObjectAvailable,
} from "@/components/validate/validationLinks";

type CandidateSummaryCardProps = {
  candidate: PaperValidationCandidateItem;
  /** Optional known run-plan id if already discovered from API; never invented. */
  runPlanId?: string | null;
  runPlanStatus?: string | null;
};

export function CandidateSummaryCard({
  candidate,
  runPlanId = null,
  runPlanStatus = null,
}: CandidateSummaryCardProps) {
  const queued = formatTimestamp(candidate.created_at);
  const hasRunPlan = relatedObjectAvailable(runPlanId);

  return (
    <article
      className="rounded-control border border-border-subtle bg-surface-0/40 px-4 py-3 space-y-3"
      data-testid={`paper-candidate-${candidate.candidate_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">
              {setupConditionLabel(candidate.condition ?? "unknown")}
            </Badge>
            <span className="text-sm font-medium text-text-primary">
              {candidate.symbol ?? "—"} · {candidate.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{candidate.direction ?? "—"}</Badge>
          </div>
          <p className="text-caption text-text-muted">
            Queued {queued ?? "unavailable"}
            {candidate.promotion_source ? ` · Source: ${candidate.promotion_source}` : ""}
          </p>
        </div>
        <Badge variant="muted" data-testid={`paper-candidate-status-${candidate.candidate_id}`}>
          {candidate.candidate_status}
        </Badge>
      </div>

      <p className="text-sm text-text-secondary">{candidate.thesis ?? "No thesis provided."}</p>

      <dl className="grid gap-2 text-caption text-text-muted sm:grid-cols-2">
        <div>
          <dt className="sr-only">Confidence</dt>
          <dd>Confidence: {formatConfidence(candidate.confidence)}</dd>
        </div>
        <div>
          <dt className="sr-only">Evidence</dt>
          <dd>Evidence: {candidateEvidenceCompleteness(candidate)}</dd>
        </div>
        <div>
          <dt className="sr-only">Run plan</dt>
          <dd data-testid={`paper-candidate-run-plan-${candidate.candidate_id}`}>
            Run plan:{" "}
            {hasRunPlan
              ? `${runPlanStatus ?? "linked"} (${runPlanId!.slice(0, 8)}…)`
              : "not linked on this list — open detail or Run plans"}
          </dd>
        </div>
        <div>
          <dt className="sr-only">Next action</dt>
          <dd data-testid={`paper-candidate-next-${candidate.candidate_id}`}>
            Next: {candidateNextAction(candidate)}
          </dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href={candidateDetailHref(candidate.candidate_id)}
          className="inline-flex min-h-11 items-center underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          View candidate detail
        </Link>
        {relatedObjectAvailable(candidate.draft_id) ? (
          <Link
            href={draftDetailHref(candidate.draft_id)}
            className="inline-flex min-h-11 items-center text-text-secondary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Related draft
          </Link>
        ) : null}
        {relatedObjectAvailable(candidate.backtest_run_id) ? (
          <Link
            href={backtestDetailHref(candidate.backtest_run_id)}
            className="inline-flex min-h-11 items-center text-text-secondary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Related backtest
          </Link>
        ) : null}
      </div>
    </article>
  );
}
