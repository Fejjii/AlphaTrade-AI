import Link from "next/link";

import { EvidenceSummary } from "@/components/workflows/EvidenceSummary";
import { WorkflowEmptyState } from "@/components/workflows/WorkflowEmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RiskBlock } from "@/components/ui/risk-block";
import type { PlanHierarchyModel } from "@/components/workflows/types";
import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import type { PlanSignalContext } from "@/components/workflows/planContext";
import { evidenceHrefForPlanContext } from "@/components/workflows/planContext";

type PlanSummaryProps = {
  plan: PlanHierarchyModel | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  posture: SafetyPostureDisplay;
  partialData?: boolean;
  unavailableSources?: string[];
  bothSourcesAvailable?: boolean;
  signalContext?: PlanSignalContext | null;
};

export function PlanSummary({
  plan,
  loading = false,
  error = null,
  onRetry,
  posture,
  partialData = false,
  unavailableSources = [],
  bothSourcesAvailable = true,
  signalContext = null,
}: PlanSummaryProps) {
  if (loading) {
    return (
      <section aria-labelledby="plan-summary-heading" data-testid="plan-summary">
        <h2 id="plan-summary-heading" className="text-lg font-semibold text-text-primary">
          Current draft or planned trade
        </h2>
        <p className="mt-2 text-sm text-text-muted" role="status">
          Loading plan hub…
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-labelledby="plan-summary-heading" data-testid="plan-summary">
        <h2 id="plan-summary-heading" className="text-lg font-semibold text-text-primary">
          Current draft or planned trade
        </h2>
        <div className="mt-3">
          <WorkflowEmptyState
            title="Plan data unavailable"
            description={error}
            actionLabel={onRetry ? "Retry" : undefined}
            onAction={onRetry}
            tone="error"
          />
        </div>
      </section>
    );
  }

  const runtimeBadgeVariant =
    posture.runtimeBadgeVariant === "paper"
      ? "paper"
      : posture.runtimeBadgeVariant === "danger"
        ? "danger"
        : posture.runtimeBadgeVariant === "warning"
          ? "warning"
          : "muted";

  return (
    <section aria-labelledby="plan-summary-heading" data-testid="plan-summary" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="plan-summary-heading" className="text-lg font-semibold text-text-primary">
            Current draft or planned trade
          </h2>
          {plan ? (
            <p className="mt-1 text-sm text-text-muted">
              {plan.symbol ?? "Symbol unavailable"} · {plan.direction ?? "—"} ·{" "}
              {plan.timeframe ?? "—"}
            </p>
          ) : (
            <p className="mt-1 text-sm text-text-muted">
              {bothSourcesAvailable
                ? "No in-flight proposal or approval selected."
                : "Plan context depends on available proposal/approval sources."}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {plan ? (
            <Badge variant="muted" data-testid="plan-approval-state">
              Approval: {plan.approvalState}
            </Badge>
          ) : null}
          <Badge variant={runtimeBadgeVariant} data-testid="plan-runtime-posture">
            {posture.runtimeBadgeLabel}
          </Badge>
        </div>
      </div>

      {signalContext ? (
        <div
          data-testid="plan-signal-context"
          className="rounded-control border border-border-subtle bg-surface-0/40 px-4 py-3 text-sm"
        >
          <p className="font-medium text-text-primary">Planning from signal</p>
          <p className="mt-1 min-w-0 text-text-secondary">
            <span>Source: {signalContext.source}</span>
            {signalContext.signalId ? (
              <>
                {" · "}
                <span className="inline">signal </span>
                <code
                  className="inline-block max-w-full truncate align-bottom font-mono text-caption"
                  title={signalContext.signalId}
                  data-testid="plan-signal-id"
                >
                  {signalContext.signalId}
                </code>
              </>
            ) : null}
            {signalContext.alertId ? (
              <>
                {" · "}
                <span className="inline">alert </span>
                <code
                  className="inline-block max-w-full truncate align-bottom font-mono text-caption"
                  title={signalContext.alertId}
                  data-testid="plan-alert-id"
                >
                  {signalContext.alertId}
                </code>
              </>
            ) : null}
          </p>
          <p className="mt-1 text-caption text-text-muted">
            Context is carried by the URL query only. No persisted backend association is claimed.
          </p>
          <Link
            href={evidenceHrefForPlanContext(signalContext)}
            className="mt-2 inline-flex underline text-text-secondary"
          >
            Back to evidence
          </Link>
        </div>
      ) : null}

      {partialData ? (
        <div
          role="status"
          data-testid="plan-partial-data"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial plan context</p>
          {unavailableSources.length ? (
            <p className="mt-1">Unavailable: {unavailableSources.join(", ")}.</p>
          ) : null}
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {!plan ? (
        <WorkflowEmptyState
          title={
            bothSourcesAvailable
              ? "No in-flight paper plan"
              : "Plan data incomplete"
          }
          description={
            bothSourcesAvailable
              ? "Create a plan from a signal or start a new paper trade ticket. Existing proposals and approvals remain reachable."
              : "One or more plan sources failed. Retry to load proposals and approvals before concluding none exist."
          }
          actionLabel={onRetry && !bothSourcesAvailable ? "Retry" : undefined}
          onAction={onRetry}
          tone={!bothSourcesAvailable ? "error" : "empty"}
        />
      ) : (
        <>
          {plan.riskBlocked ? (
            <RiskBlock
              reason={plan.blockReason ?? "Risk engine returned BLOCK for this proposal."}
              ruleReference={plan.proposalId ? `proposal:${plan.proposalId}` : undefined}
            />
          ) : null}

          <EvidenceSummary
            thesis={plan.thesis}
            items={[
              { label: "Entry", value: plan.entry },
              { label: "Invalidation", value: plan.invalidation },
              { label: "Stop loss", value: plan.stopLoss },
              { label: "Take profit", value: plan.takeProfit },
              {
                label: "Risk and size",
                value: `${plan.riskSummary ?? "—"} · size ${plan.size ?? "—"}`,
              },
              { label: "Approval state", value: plan.approvalState },
              {
                label: "Proposal paper-execution state",
                value: plan.paperExecutionState,
              },
              {
                label: "Runtime posture",
                value: posture.runtimeBadgeLabel,
              },
              {
                label: "Confidence",
                value: plan.confidence != null ? plan.confidence.toFixed(2) : "unavailable",
              },
            ]}
            limitations={[
              ...(plan.riskBlocked
                ? ["Risk BLOCK is final. No UI override is available."]
                : ["No live order actions are available from the Plan hub."]),
              "Approval state is separate from verified runtime paper availability.",
            ]}
          />

          <div className="flex flex-wrap gap-3 text-sm">
            {plan.proposalHref ? (
              <Link href={plan.proposalHref} className="underline text-text-secondary">
                Open proposal
              </Link>
            ) : null}
            {plan.approvalHref ? (
              <Link href={plan.approvalHref} className="underline text-text-secondary">
                Open approval
              </Link>
            ) : null}
            <Link href="/pre-trade" className="underline text-text-secondary">
              Pre-trade checks
            </Link>
            <Link href="/manual-levels" className="underline text-text-secondary">
              Manual levels
            </Link>
            <Link href="/strategy-lab" className="underline text-text-secondary">
              Strategy Lab
            </Link>
          </div>
        </>
      )}
    </section>
  );
}
