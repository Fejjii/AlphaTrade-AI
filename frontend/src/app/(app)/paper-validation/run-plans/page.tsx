"use client";

import { useCallback } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { RunPlanSummaryCard, ValidatePageChrome } from "@/components/validate";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

type RunPlansPageData = {
  runPlans: SourceResult<Awaited<ReturnType<typeof api.strategies.runPlans>>>;
};

export default function PaperValidationRunPlansPage() {
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<RunPlansPageData> => {
    return { runPlans: await loadSource(api.strategies.runPlans({ limit: 50 })) };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);
  const available = data?.runPlans.available ?? false;
  const items = available ? (data?.runPlans.data?.items ?? []) : [];

  const freshnessSources = [
    {
      name: "Run plans",
      available,
      required: true,
      timestamp: items[0]?.created_at ?? null,
    },
  ];

  if (loading && !data) return <LoadingState label="Loading run plans…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <ValidatePageChrome
      title="Paper Validation Run Plans"
      description="Structured run plans from reviewing candidates. Plan only — no run started, no orders, no proposals, no Telegram."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="paper-validation-run-plans-page"
      activeHref="/paper-validation/run-plans"
    >
      {!available ? (
        <ErrorState
          message={
            data?.runPlans.error ?? "Run plan source unavailable. Count is not shown as zero."
          }
          onRetry={() => void reload()}
        />
      ) : items.length ? (
        <div className="space-y-3" data-testid="paper-validation-run-plans-list">
          {items.map((plan) => (
            <RunPlanSummaryCard key={plan.plan_id} plan={plan} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No run plans yet"
          description="Mark a candidate as reviewing, then create a run plan from the candidate detail page. Available run-plan source returned an empty list."
        />
      )}
    </ValidatePageChrome>
  );
}
