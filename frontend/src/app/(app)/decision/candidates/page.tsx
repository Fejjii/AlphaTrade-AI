"use client";

import { useCallback, useMemo } from "react";

import { DecisionCaseCard } from "@/components/canonical-decision/DecisionCaseCard";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { composeDecisionCases } from "@/lib/canonical-decision/compose";
import { loadSource } from "@/components/workflows";

export default function DecisionCandidatesPage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const loader = useCallback(async () => {
    const [canonical, pvc] = await Promise.all([
      loadSource(api.canonical.listCandidates({ limit: 50 })),
      loadSource(api.strategies.candidates({ limit: 50 })),
    ]);
    return { canonical, pvc };
  }, []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  const snapshot = useMemo(
    () =>
      composeDecisionCases({
        canonicalCandidates: data?.canonical.data?.items ?? [],
        candidates: data?.pvc.data?.items ?? [],
        proposals: [],
        approvals: [],
        orders: [],
        journals: [],
        lessons: [],
        killSwitchActive,
        executionMode,
        realTradingEnabled,
      }),
    [data, killSwitchActive, executionMode, realTradingEnabled],
  );

  return (
    <DecisionChrome
      title="Candidates"
      description="Canonical Candidates from GET /canonical/candidates. Paper-validation items remain compatibility projections, not CandidateLifecycleService."
      current="candidate"
      eligibilityBlocked={killSwitchActive}
    >
      {loading ? <LoadingState label="Loading candidates…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {snapshot.cases.length ? (
        <section className="grid gap-4">
          {snapshot.cases.map((item) => (
            <DecisionCaseCard key={item.id} item={item} />
          ))}
        </section>
      ) : !loading && !error ? (
        <EmptyState
          title="No candidates yet"
          description="Canonical Candidates appear here when persisted. Paper-validation queue items remain compatibility-only and are never treated as canonical authority."
        />
      ) : null}
    </DecisionChrome>
  );
}
