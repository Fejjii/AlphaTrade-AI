"use client";

import { useCallback, useMemo } from "react";

import { DecisionCaseCard } from "@/components/canonical-decision/DecisionCaseCard";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { composeDecisionCases } from "@/lib/canonical-decision/compose";

export default function DecisionCandidatesPage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const loader = useCallback(() => api.strategies.candidates({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  const snapshot = useMemo(
    () =>
      composeDecisionCases({
        candidates: data?.items ?? [],
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
      description="Compatibility candidate workspace from the paper-validation queue. Not canonical Candidate authority."
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
          title="No compatibility candidates"
          description="Canonical Candidate HTTP is unbound. Legacy paper-validation candidates will appear here when queued."
        />
      ) : null}
    </DecisionChrome>
  );
}
