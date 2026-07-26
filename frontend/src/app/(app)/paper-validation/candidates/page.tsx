"use client";

import { useCallback, useMemo } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  CandidateSummaryCard,
  ValidatePageChrome,
  buildCandidateRunPlanMap,
} from "@/components/validate";
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
  const runPlansAvailable = data?.runPlans.available ?? false;
  const items = available ? (data?.candidates.data?.items ?? []) : [];
  const planByCandidate = useMemo(
    () =>
      buildCandidateRunPlanMap(
        runPlansAvailable,
        data?.runPlans.data?.items,
        items.map((item) => item.candidate_id),
      ),
    [data?.runPlans.data?.items, items, runPlansAvailable],
  );

  const partialRunPlans = available && Boolean(data) && !runPlansAvailable;

  const freshnessSources = [
    {
      name: "Candidates",
      available,
      required: true,
      timestamp: items[0]?.created_at ?? null,
    },
    {
      name: "Run plans",
      available: runPlansAvailable,
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
      {partialRunPlans ? (
        <div
          role="status"
          data-testid="candidates-run-plans-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            Candidates are shown, but run-plan relationships are unavailable from the API.
          </p>
          {data?.runPlans.error ? (
            <p className="mt-1 text-caption">Run plans error: {data.runPlans.error}</p>
          ) : null}
          <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => void reload()}>
            Retry
          </Button>
        </div>
      ) : null}

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
          {items.map((candidate) => (
            <CandidateSummaryCard
              key={candidate.candidate_id}
              candidate={candidate}
              runPlanRelation={
                planByCandidate.get(candidate.candidate_id) ?? { kind: "none" }
              }
            />
          ))}
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
