import type {
  PaperValidationCandidateItem,
  PaperValidationDraftItem,
  PaperValidationRunPlanItem,
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";

import { summarizeOutcomeCoverage } from "@/components/validate/sessionExtras";
import {
  draftNextAction,
  runPlanCriteriaIssues,
  runPlanNextAction,
  runSessionNextAction,
} from "@/components/validate/validationDisplay";
import { runSessionDetailHref } from "@/components/validate/validationLinks";
import {
  VALIDATION_STAGE_DEFINITIONS,
  VALIDATION_STAGE_ORDER,
  type OutcomeCoverageModel,
  type RecentOutcomeSummary,
  type ValidateHubSources,
  type ValidationAttentionItem,
  type ValidationCount,
  type ValidationPipelineModel,
  type ValidationStageId,
  type ValidationStageModel,
} from "@/components/validate/types";

function countOrNull(available: boolean, count: number | null | undefined): ValidationCount {
  if (!available) return null;
  return count ?? 0;
}

function newestTimestamp(values: Array<string | null | undefined>): string | null {
  let best: string | null = null;
  let bestMs = Number.NEGATIVE_INFINITY;
  for (const value of values) {
    if (!value) continue;
    const ms = Date.parse(value);
    if (!Number.isFinite(ms)) continue;
    if (ms > bestMs) {
      bestMs = ms;
      best = value;
    }
  }
  return best;
}

function stageCount(
  id: ValidationStageId,
  sources: ValidateHubSources,
): ValidationCount {
  switch (id) {
    case "draft":
      return countOrNull(sources.drafts.available, sources.drafts.data?.total);
    case "candidate":
      return countOrNull(sources.candidates.available, sources.candidates.data?.total);
    case "run_plan":
      return countOrNull(sources.runPlans.available, sources.runPlans.data?.total);
    case "run_session":
      return countOrNull(sources.runSessions.available, sources.runSessions.data?.total);
    case "observation": {
      if (!sources.runSessions.available) return null;
      const running =
        sources.runSessions.data?.items.filter((s) => s.session_status === "running").length ?? 0;
      return running;
    }
    case "outcome": {
      if (!sources.runSessions.available) return null;
      const coverage = summarizeOutcomeCoverage(sources.recentResults);
      // No completed sessions probed → honest zero only when sessions source is available.
      if (coverage.completedSessionsProbed === 0) return 0;
      // All result requests failed → never display a confirmed zero.
      if (
        coverage.resultsUnavailable === coverage.completedSessionsProbed &&
        coverage.resultsLoaded === 0 &&
        coverage.resultsNotRecorded === 0
      ) {
        return null;
      }
      // Loaded recorded outcomes only; confirmed not-recorded are not counted as loaded results.
      return coverage.resultsLoaded;
    }
    default: {
      const _exhaustive: never = id;
      return _exhaustive;
    }
  }
}

function stageStatus(
  id: ValidationStageId,
  sources: ValidateHubSources,
  count: ValidationCount,
): { statusLabel: string; nextAction: string; blocker: string | null; timestamp: string | null } {
  const def = VALIDATION_STAGE_DEFINITIONS.find((s) => s.id === id)!;
  // Outcome may have null count when result probes failed while sessions remain available.
  const unavailable =
    count == null && !(id === "outcome" && sources.runSessions.available);

  if (unavailable) {
    return {
      statusLabel: "Source unavailable",
      nextAction: `Retry ${def.name.toLowerCase()} source, then continue the pipeline.`,
      blocker: `${def.name} data is unavailable from the API.`,
      timestamp: null,
    };
  }

  switch (id) {
    case "draft": {
      const items = sources.drafts.data?.items ?? [];
      const ready = items.filter((d) => d.is_ready_for_validation).length;
      return {
        statusLabel: ready > 0 ? `${ready} ready to queue` : count === 0 ? "No drafts" : `${count} in prep`,
        nextAction:
          ready > 0
            ? "Queue a ready draft with typed confirmation."
            : count === 0
              ? "Create a paper draft from Setup Review or Signals."
              : "Complete draft checklist and criteria.",
        blocker: null,
        timestamp: newestTimestamp(items.map((d) => d.created_at)),
      };
    }
    case "candidate": {
      const items = sources.candidates.data?.items ?? [];
      const reviewing = items.filter((c) => c.candidate_status === "reviewing").length;
      const queued = items.filter((c) => c.candidate_status === "queued").length;
      return {
        statusLabel:
          count === 0
            ? "No candidates"
            : `${queued} queued · ${reviewing} reviewing`,
        nextAction:
          reviewing > 0
            ? "Create a run plan from a reviewing candidate."
            : queued > 0
              ? "Move a queued candidate to reviewing."
              : "Queue a ready draft to create a candidate.",
        blocker: null,
        timestamp: newestTimestamp(items.map((c) => c.created_at)),
      };
    }
    case "run_plan": {
      const items = sources.runPlans.data?.items ?? [];
      const planned = items.filter((p) => p.plan_status === "planned").length;
      const needsRevision = items.filter(
        (p) => p.plan_status === "needs_revision" || runPlanCriteriaIssues(p).length > 0,
      ).length;
      return {
        statusLabel:
          count === 0
            ? "No run plans"
            : `${planned} planned · ${needsRevision} need attention`,
        nextAction:
          planned > 0
            ? "Start a paper run session from a planned run plan."
            : "Create a run plan from a reviewing candidate.",
        blocker: needsRevision > 0 ? "Some plans have incomplete or contradictory criteria." : null,
        timestamp: newestTimestamp(items.map((p) => p.created_at)),
      };
    }
    case "run_session": {
      const items = sources.runSessions.data?.items ?? [];
      const running = items.filter((s) => s.session_status === "running").length;
      return {
        statusLabel:
          count === 0 ? "No sessions" : `${running} active · ${count} total`,
        nextAction:
          running > 0
            ? "Record observations and outcomes on active sessions."
            : "Start a session from a planned run plan.",
        blocker: null,
        timestamp: newestTimestamp(items.map((s) => s.started_at ?? s.created_at)),
      };
    }
    case "observation": {
      const running =
        sources.runSessions.data?.items.filter((s) => s.session_status === "running") ?? [];
      return {
        statusLabel: count === 0 ? "No active observation windows" : `${count} sessions collecting`,
        nextAction:
          count === 0
            ? "Start a run session to begin recording observations."
            : "Open an active session and record observations with confirmation.",
        blocker: null,
        timestamp: newestTimestamp(running.map((s) => s.started_at ?? s.created_at)),
      };
    }
    case "outcome": {
      const completed =
        sources.runSessions.data?.items.filter((s) => s.session_status === "completed") ?? [];
      const coverage = summarizeOutcomeCoverage(sources.recentResults);
      const probed = coverage.completedSessionsProbed;
      let statusLabel = "No completed sessions";
      let blocker: string | null = null;
      if (probed === 0) {
        statusLabel = "No completed sessions";
      } else if (
        coverage.resultsUnavailable === probed &&
        coverage.resultsLoaded === 0 &&
        coverage.resultsNotRecorded === 0
      ) {
        statusLabel = "Outcome results unavailable";
        blocker = "All recent outcome result requests failed.";
      } else if (coverage.resultsUnavailable > 0) {
        statusLabel = `${coverage.resultsLoaded} of ${probed} recent outcomes loaded`;
        blocker = `${coverage.resultsUnavailable} recent outcome result request(s) failed.`;
      } else {
        statusLabel = `${coverage.resultsLoaded} of ${probed} recent outcomes loaded`;
      }
      return {
        statusLabel,
        nextAction:
          probed === 0
            ? "Complete a running session after recording an outcome."
            : "Review recent outcomes and journal lessons if needed.",
        blocker,
        timestamp: newestTimestamp([
          ...completed.map((s) => s.ended_at ?? s.created_at),
          ...sources.recentResults.map((r) => r.data?.recorded_at ?? r.data?.created_at),
        ]),
      };
    }
    default: {
      const _exhaustive: never = id;
      return _exhaustive;
    }
  }
}

function buildStages(sources: ValidateHubSources): ValidationStageModel[] {
  return VALIDATION_STAGE_ORDER.map((id) => {
    const def = VALIDATION_STAGE_DEFINITIONS.find((s) => s.id === id)!;
    const count = stageCount(id, sources);
    const meta = stageStatus(id, sources, count);
    const coverage = summarizeOutcomeCoverage(sources.recentResults);
    const outcomeResultsAvailable =
      sources.runSessions.available &&
      (coverage.completedSessionsProbed === 0 ||
        coverage.resultsUnavailable < coverage.completedSessionsProbed);
    const available =
      id === "draft"
        ? sources.drafts.available
        : id === "candidate"
          ? sources.candidates.available
          : id === "run_plan"
            ? sources.runPlans.available
            : id === "outcome"
              ? outcomeResultsAvailable
              : sources.runSessions.available;
    const sourceName =
      id === "draft"
        ? "Drafts"
        : id === "candidate"
          ? "Candidates"
          : id === "run_plan"
            ? "Run plans"
            : id === "run_session"
              ? "Run sessions"
              : id === "observation"
                ? "Run sessions (active)"
                : "Outcome results";
    return {
      id,
      name: def.name,
      purpose: def.purpose,
      href: def.href,
      count,
      statusLabel: meta.statusLabel,
      nextAction: meta.nextAction,
      blocker: meta.blocker,
      timestamp: meta.timestamp,
      available,
      sourceName,
    };
  });
}

function buildAttention(sources: ValidateHubSources): ValidationAttentionItem[] {
  const items: ValidationAttentionItem[] = [];

  if (sources.drafts.available) {
    for (const draft of sources.drafts.data?.items ?? []) {
      if (draft.is_ready_for_validation) {
        items.push({
          id: `draft-ready-${draft.draft_id}`,
          title: `${draft.symbol ?? "Setup"} draft ready to queue`,
          detail: draftNextAction(draft),
          href: `/paper-validation/drafts/${draft.draft_id}`,
          stageId: "draft",
          urgency: "high",
        });
      }
    }
  }

  if (sources.candidates.available) {
    for (const candidate of sources.candidates.data?.items ?? []) {
      if (candidate.candidate_status === "queued") {
        items.push({
          id: `candidate-queued-${candidate.candidate_id}`,
          title: `${candidate.symbol ?? "Setup"} candidate awaiting review`,
          detail: "Move to reviewing when you are ready to plan validation.",
          href: `/paper-validation/candidates/${candidate.candidate_id}`,
          stageId: "candidate",
          urgency: "medium",
        });
      } else if (candidate.candidate_status === "reviewing") {
        items.push({
          id: `candidate-reviewing-${candidate.candidate_id}`,
          title: `${candidate.symbol ?? "Setup"} candidate ready for run plan`,
          detail: "Create a run plan with typed confirmation.",
          href: `/paper-validation/candidates/${candidate.candidate_id}`,
          stageId: "candidate",
          urgency: "high",
        });
      }
    }
  }

  if (sources.runPlans.available) {
    for (const plan of sources.runPlans.data?.items ?? []) {
      const issues = runPlanCriteriaIssues(plan);
      if (plan.plan_status === "needs_revision" || issues.length) {
        items.push({
          id: `plan-issues-${plan.plan_id}`,
          title: `${plan.symbol ?? "Setup"} run plan needs criteria review`,
          detail: issues[0] ?? runPlanNextAction(plan),
          href: `/paper-validation/run-plans/${plan.plan_id}`,
          stageId: "run_plan",
          urgency: "high",
        });
      } else if (plan.plan_status === "planned") {
        items.push({
          id: `plan-planned-${plan.plan_id}`,
          title: `${plan.symbol ?? "Setup"} run plan ready to start`,
          detail: runPlanNextAction(plan),
          href: `/paper-validation/run-plans/${plan.plan_id}`,
          stageId: "run_plan",
          urgency: "medium",
        });
      }
    }
  }

  if (sources.runSessions.available) {
    for (const session of sources.runSessions.data?.items ?? []) {
      if (session.session_status === "running") {
        items.push({
          id: `session-running-${session.session_id}`,
          title: `${session.symbol ?? "Setup"} session is active`,
          detail: runSessionNextAction(session),
          href: runSessionDetailHref(session.session_id),
          stageId: "run_session",
          urgency: "high",
        });
      }
    }
  }

  const urgencyRank = { high: 0, medium: 1, low: 2 } as const;
  return items.sort((a, b) => urgencyRank[a.urgency] - urgencyRank[b.urgency]);
}

function buildRecentOutcomes(sources: ValidateHubSources): RecentOutcomeSummary[] {
  if (!sources.runSessions.available) return [];
  const completedById = new Map(
    (sources.runSessions.data?.items ?? [])
      .filter((s) => s.session_status === "completed")
      .map((s) => [s.session_id, s]),
  );

  return sources.recentResults.map((resultSource) => {
    const session = completedById.get(resultSource.sessionId);
    const result =
      resultSource.available && !resultSource.resultNotRecorded ? resultSource.data : null;
    return {
      sessionId: resultSource.sessionId,
      symbol: session?.symbol ?? null,
      condition: session?.condition ?? null,
      sessionStatus: session?.session_status ?? "completed",
      outcome: result?.outcome ?? null,
      recordedAt:
        result?.recorded_at ?? result?.created_at ?? session?.ended_at ?? session?.created_at ?? null,
      href: runSessionDetailHref(resultSource.sessionId),
      resultAvailable: resultSource.available,
      resultNotRecorded: resultSource.resultNotRecorded,
      resultError: resultSource.error,
    };
  });
}

function buildLimitations(
  sources: ValidateHubSources,
  coverage: OutcomeCoverageModel,
): string[] {
  const limitations: string[] = [
    "Paper validation only — no exchange orders, no autonomous execution, no live trading.",
    "Drafts, candidates, plans, and sessions advance only through explicit confirmed actions.",
    "Risk BLOCK remains final with no UI override.",
    "MFE/MAE are not calculated on Validate outcome records unless the API provides them.",
  ];
  if (!sources.drafts.available) limitations.push("Draft source unavailable — draft counts hidden.");
  if (!sources.candidates.available) {
    limitations.push("Candidate source unavailable — candidate counts hidden.");
  }
  if (!sources.runPlans.available) {
    limitations.push("Run plan source unavailable — plan counts hidden.");
  }
  if (!sources.runSessions.available) {
    limitations.push("Run session source unavailable — session and outcome summaries limited.");
  }
  if (coverage.resultsUnavailable > 0) {
    limitations.push(
      `${coverage.resultsUnavailable} recent outcome result request(s) unavailable — coverage incomplete.`,
    );
  }
  return limitations;
}

export function buildValidationPipeline(sources: ValidateHubSources): ValidationPipelineModel {
  const outcomeCoverage = summarizeOutcomeCoverage(sources.recentResults);
  const stages = buildStages(sources);
  const counts = Object.fromEntries(stages.map((s) => [s.id, s.count])) as Record<
    ValidationStageId,
    ValidationCount
  >;
  const activeSessions = sources.runSessions.available
    ? (sources.runSessions.data?.items.filter((s) => s.session_status === "running") ?? [])
    : [];

  return {
    stages,
    counts,
    attention: buildAttention(sources),
    activeSessions,
    recentOutcomes: buildRecentOutcomes(sources),
    outcomeCoverage,
    limitations: buildLimitations(sources, outcomeCoverage),
  };
}

export function countOrNullExport(
  available: boolean,
  count: number | null | undefined,
): ValidationCount {
  return countOrNull(available, count);
}

/** Helpers exported for stage list pages that already hold typed items. */
export type {
  PaperValidationCandidateItem,
  PaperValidationDraftItem,
  PaperValidationRunPlanItem,
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
};
