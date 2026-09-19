"use client";

import { useCallback, useMemo } from "react";
import { useParams } from "next/navigation";

import { CandidateWorkspace } from "@/components/canonical-decision/CandidateWorkspace";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { composeDecisionCases } from "@/lib/canonical-decision/compose";

export default function DecisionCandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const candidateId = params.candidateId;
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const loader = useCallback(() => api.strategies.getCandidate(candidateId), [candidateId]);
  const { data, loading, error, reload } = useAsyncData(loader, [candidateId]);

  const workspace = useMemo(() => {
    if (!data) return null;
    return composeDecisionCases({
      candidates: [data],
      proposals: [],
      approvals: [],
      orders: [],
      journals: [],
      lessons: [],
      killSwitchActive,
      executionMode,
      realTradingEnabled,
    }).cases[0]?.candidate ?? null;
  }, [data, killSwitchActive, executionMode, realTradingEnabled]);

  return (
    <DecisionChrome
      title="Candidate workspace"
      description="State, setup, evidence, confidence, and a separate eligibility gate."
      current={workspace?.eligibility.state === "blocked" ? "eligibility" : "candidate"}
      eligibilityBlocked={workspace?.eligibility.state !== "eligible"}
    >
      {loading ? <LoadingState label="Loading candidate…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {workspace ? <CandidateWorkspace candidate={workspace} /> : null}
    </DecisionChrome>
  );
}
