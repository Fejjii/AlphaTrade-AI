import Link from "next/link";

import { EvidenceSummary } from "@/components/workflows/EvidenceSummary";
import { WorkflowEmptyState } from "@/components/workflows/WorkflowEmptyState";
import { Badge } from "@/components/ui/badge";
import { RiskBlock } from "@/components/ui/risk-block";
import type { PlanHierarchyModel } from "@/components/workflows/types";

type PlanSummaryProps = {
  plan: PlanHierarchyModel | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
};

export function PlanSummary({ plan, loading = false, error = null, onRetry }: PlanSummaryProps) {
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

  if (!plan) {
    return (
      <section aria-labelledby="plan-summary-heading" data-testid="plan-summary" className="space-y-3">
        <h2 id="plan-summary-heading" className="text-lg font-semibold text-text-primary">
          Current draft or planned trade
        </h2>
        <WorkflowEmptyState
          title="No in-flight paper plan"
          description="Create a plan from a signal or start a new paper trade ticket. Existing proposals and approvals remain reachable."
        />
      </section>
    );
  }

  return (
    <section aria-labelledby="plan-summary-heading" data-testid="plan-summary" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="plan-summary-heading" className="text-lg font-semibold text-text-primary">
            Current draft or planned trade
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            {plan.symbol ?? "Symbol unavailable"} · {plan.direction ?? "—"} ·{" "}
            {plan.timeframe ?? "—"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="muted">Approval: {plan.approvalState}</Badge>
          <Badge variant="paper">Paper only</Badge>
        </div>
      </div>

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
          { label: "Risk and size", value: `${plan.riskSummary ?? "—"} · size ${plan.size ?? "—"}` },
          { label: "Approval state", value: plan.approvalState },
          { label: "Paper-only execution state", value: plan.paperExecutionState },
          {
            label: "Confidence",
            value: plan.confidence != null ? plan.confidence.toFixed(2) : "unavailable",
          },
        ]}
        limitations={
          plan.riskBlocked
            ? ["Risk BLOCK is final. No UI override is available."]
            : ["No live order actions are available from the Plan hub."]
        }
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
    </section>
  );
}
