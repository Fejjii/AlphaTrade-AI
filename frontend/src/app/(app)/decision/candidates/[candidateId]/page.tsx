"use client";

import { useCallback, useMemo } from "react";
import { useParams } from "next/navigation";

import { CandidateWorkspace } from "@/components/canonical-decision/CandidateWorkspace";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { OutcomeLearning } from "@/components/canonical-decision/OutcomeLearning";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import type {
  CanonicalCandidateRead,
  CanonicalEligibilityRead,
  CanonicalLearningRecordRead,
  CanonicalSetupAssessmentRead,
  PaperValidationCandidateItem,
} from "@/lib/api/types";
import {
  composeDecisionCases,
  learningFromCanonicalRecord,
  outcomeFromCanonicalRecord,
  workspaceFromCanonicalCandidate,
} from "@/lib/canonical-decision/compose";
import { loadSource } from "@/components/workflows";

type CandidateBundle =
  | {
      kind: "canonical";
      candidate: CanonicalCandidateRead;
      eligibility: CanonicalEligibilityRead | null;
      assessment: CanonicalSetupAssessmentRead | null;
      learning: CanonicalLearningRecordRead | null;
    }
  | { kind: "compatibility"; candidate: PaperValidationCandidateItem };

async function loadCandidateBundle(candidateId: string): Promise<CandidateBundle> {
  try {
    const candidate = await api.canonical.getCandidate(candidateId);
    const [eligibility, assessment, learning] = await Promise.all([
      loadSource(api.canonical.getEligibility(candidateId)),
      loadSource(api.canonical.getSetupAssessment(candidate.candidate.assessment_id)),
      loadSource(api.canonical.getLearningRecord(candidateId)),
    ]);
    return {
      kind: "canonical",
      candidate,
      eligibility: eligibility.data,
      assessment: assessment.data,
      learning: learning.data,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { kind: "compatibility", candidate: await api.strategies.getCandidate(candidateId) };
    }
    throw error;
  }
}

export default function DecisionCandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const candidateId = params.candidateId;
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const loader = useCallback(() => loadCandidateBundle(candidateId), [candidateId]);
  const { data, loading, error, reload } = useAsyncData(loader, [candidateId]);

  const workspace = useMemo(() => {
    if (!data) return null;
    const facts = { killSwitchActive, executionMode, realTradingEnabled };
    if (data.kind === "canonical") {
      return workspaceFromCanonicalCandidate(data.candidate, facts, {
        eligibility: data.eligibility,
        assessment: data.assessment,
      });
    }
    return (
      composeDecisionCases({
        candidates: [data.candidate],
        proposals: [],
        approvals: [],
        orders: [],
        journals: [],
        lessons: [],
        ...facts,
      }).cases[0]?.candidate ?? null
    );
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
      {data?.kind === "canonical" && data.learning ? (
        <OutcomeLearning
          outcome={outcomeFromCanonicalRecord(data.learning)}
          learning={learningFromCanonicalRecord(data.learning)}
        />
      ) : null}
    </DecisionChrome>
  );
}
