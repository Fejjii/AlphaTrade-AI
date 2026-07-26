"use client";

import { useCallback, useMemo } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { CandidateSummaryCard, ValidatePageChrome } from "@/components/validate";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

type CandidatesPageData = {
  candidates: SourceResult<Awaited<ReturnType<typeof api.strategies.candidates>>>;
  runPlans: SourceResult<Awaited<ReturnType<typeof api.strategies.runPlans>>>;
};

export default function PaperValidationCandidatesPage() {
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<CandidatesPageData> => {
    const [candidates, runPlans] = await Promise.all([
      loadSource(api.strategies.candidates({ limit: 50 })),
      loadSource(api.strategies.runPlans({ limit: 50 })),
    ]);
    return { candidates, runPlans };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);
  const available = data?.candidates.available ?? false;
  const items = available ? (data?.candidates.data?.items ?? []) : [];
  const planByCandidate = useMemo(() => {
    const map = new Map<string, { planId: string; status: string }>();
    if (!data?.runPlans.available) return map;
    for (const plan of data.runPlans.data?.items ?? []) {
      if (!map.has(plan.candidate_id)) {
        map.set(plan.candidate_id, { planId: plan.plan_id, status: plan.plan_status });
      }
    }
    return map;
  }, [data]);

  const freshnessSources = [
    {
      name: "Candidates",
      available,
      required: true,
      timestamp: items[0]?.created_at ?? null,
    },
    {
      name: "Run plans",
      available: data?.runPlans.available ?? false,
      required: false,
      timestamp: data?.runPlans.data?.items[0]?.created_at ?? null,
    },
  ];

  if (loading && !data) return <LoadingState label="Loading paper validation queue…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <ValidatePageChrome
      title="Paper Validation Queue"
      description="Structured validation candidates from ready drafts. Queue only — no run started, no orders, no proposals, no Telegram."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="paper-validation-candidates-page"
      activeHref="/paper-validation/candidates"
    >
      {!available ? (
        <ErrorState
          message={
            data?.candidates.error ??
            "Candidate source unavailable. Count is not shown as zero."
          }
          onRetry={() => void reload()}
        />
      ) : items.length ? (
        <div className="space-y-3" data-testid="paper-validation-candidates-list">
          {items.map((candidate) => {
            const plan = planByCandidate.get(candidate.candidate_id);
            return (
              <CandidateSummaryCard
                key={candidate.candidate_id}
                candidate={candidate}
                runPlanId={plan?.planId ?? null}
                runPlanStatus={plan?.status ?? null}
              />
            );
          })}
        </div>
      ) : (
        <EmptyState
          title="No validation candidates yet"
          description="Mark a draft ready for validation, then queue it from the draft detail page. Available candidate source returned an empty list."
        />
      )}
    </ValidatePageChrome>
  );
}
