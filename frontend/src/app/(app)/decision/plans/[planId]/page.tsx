"use client";

import { useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { PaperApprovalPanel } from "@/components/canonical-decision/PaperApprovalPanel";
import { TradePlanView } from "@/components/canonical-decision/TradePlanView";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { projectActionEligibility } from "@/lib/canonical-decision/eligibility";
import { tradePlanFromProposal } from "@/lib/canonical-decision/trade-plan";
import { ActionEligibilityCard } from "@/components/canonical-decision/ActionEligibilityCard";

type PlanBundle = {
  proposal: Awaited<ReturnType<typeof api.proposals.get>>;
  workflow: Awaited<ReturnType<typeof api.proposals.workflow>>;
  revisions: Awaited<ReturnType<typeof api.proposals.listRevisions>>;
};

export default function DecisionPlanPage() {
  const params = useParams<{ planId: string }>();
  const planId = params.planId;
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();

  const loader = useCallback(async (): Promise<PlanBundle> => {
    const [proposal, workflow, revisions] = await Promise.all([
      api.proposals.get(planId),
      api.proposals.workflow(planId),
      api.proposals.listRevisions(planId).catch(() => []),
    ]);
    return { proposal, workflow, revisions };
  }, [planId]);

  const { data, loading, error, reload } = useAsyncData(loader, [planId]);
  const revision = data?.revisions.at(-1) ?? null;
  const plan = useMemo(
    () => (data ? tradePlanFromProposal(data.proposal, revision) : null),
    [data, revision],
  );
  const eligibility = useMemo(
    () =>
      data
        ? projectActionEligibility({
            killSwitchActive,
            executionMode,
            realTradingEnabled,
            proposal: data.proposal,
            approval: data.workflow.approval,
          })
        : null,
    [data, killSwitchActive, executionMode, realTradingEnabled],
  );

  return (
    <DecisionChrome
      title="TradePlan"
      description="Entry, stop, target, sizing, risk, and lineage. Human approval is still required."
      current="trade_plan"
      eligibilityBlocked={eligibility?.state !== "eligible"}
    >
      {loading ? <LoadingState label="Loading TradePlan…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {plan && eligibility && data ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <TradePlanView plan={plan} />
          <div className="space-y-4">
            <ActionEligibilityCard eligibility={eligibility} />
            {data.workflow.approval ? (
              <PaperApprovalPanel
                approval={data.workflow.approval}
                proposal={data.proposal}
                onRefresh={() => void reload()}
              />
            ) : (
              <p className="text-sm text-text-secondary">
                No approval record yet.{" "}
                <Link href="/approvals" className="text-accent underline">
                  Open legacy approvals
                </Link>
              </p>
            )}
          </div>
        </div>
      ) : null}
    </DecisionChrome>
  );
}
