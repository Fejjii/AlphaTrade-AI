"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";

import { ErrorState, LimitationsState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  RunSessionSummaryCard,
  ValidatePageChrome,
  ValidationAttentionQueue,
  ValidationPipeline,
  ValidationSourceAvailability,
  ValidationSummaryCard,
  buildValidationPipeline,
  loadRecentSessionResults,
  validateHubHref,
  type RecentResultLoad,
  type ValidateHubSources,
} from "@/components/validate";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

type ValidateHubData = {
  drafts: SourceResult<Awaited<ReturnType<typeof api.strategies.drafts>>>;
  candidates: SourceResult<Awaited<ReturnType<typeof api.strategies.candidates>>>;
  runPlans: SourceResult<Awaited<ReturnType<typeof api.strategies.runPlans>>>;
  runSessions: SourceResult<Awaited<ReturnType<typeof api.strategies.runSessions>>>;
  recentResults: RecentResultLoad[];
};

export default function ValidateHubPage() {
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<ValidateHubData> => {
    const [drafts, candidates, runPlans, runSessions] = await Promise.all([
      loadSource(api.strategies.drafts({ limit: 50 })),
      loadSource(api.strategies.candidates({ limit: 50 })),
      loadSource(api.strategies.runPlans({ limit: 50 })),
      loadSource(api.strategies.runSessions({ limit: 50 })),
    ]);
    const recentResults = runSessions.available
      ? await loadRecentSessionResults(
          runSessions.data?.items ?? [],
          (sessionId) => api.strategies.getSessionResult(sessionId),
        )
      : [];
    return { drafts, candidates, runPlans, runSessions, recentResults };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const sources: ValidateHubSources | null = useMemo(() => {
    if (!data) return null;
    return {
      drafts: data.drafts,
      candidates: data.candidates,
      runPlans: data.runPlans,
      runSessions: data.runSessions,
      recentResults: data.recentResults,
    };
  }, [data]);

  const pipeline = useMemo(
    () => (sources ? buildValidationPipeline(sources) : null),
    [sources],
  );

  const outcomeCoverage = pipeline?.outcomeCoverage;
  const outcomesSourceAvailable =
    !data?.runSessions.available
      ? false
      : !outcomeCoverage
        ? true
        : outcomeCoverage.completedSessionsProbed === 0 ||
          outcomeCoverage.resultsUnavailable < outcomeCoverage.completedSessionsProbed;

  const sourceStatuses = useMemo(() => {
    if (!data) return [];
    const coverage = pipeline?.outcomeCoverage;
    return [
      {
        name: "Drafts",
        available: data.drafts.available,
        error: data.drafts.error,
        timestamp: data.drafts.data?.items[0]?.created_at ?? null,
        required: true,
      },
      {
        name: "Candidates",
        available: data.candidates.available,
        error: data.candidates.error,
        timestamp: data.candidates.data?.items[0]?.created_at ?? null,
        required: true,
      },
      {
        name: "Run plans",
        available: data.runPlans.available,
        error: data.runPlans.error,
        timestamp: data.runPlans.data?.items[0]?.created_at ?? null,
        required: true,
      },
      {
        name: "Run sessions",
        available: data.runSessions.available,
        error: data.runSessions.error,
        timestamp:
          data.runSessions.data?.items[0]?.started_at ??
          data.runSessions.data?.items[0]?.created_at ??
          null,
        required: true,
      },
      {
        name: "Outcomes",
        available: outcomesSourceAvailable,
        error:
          coverage && coverage.resultsUnavailable > 0
            ? `${coverage.resultsUnavailable} of ${coverage.completedSessionsProbed} recent outcome result request(s) failed`
            : null,
        timestamp:
          data.recentResults.find((r) => r.data?.recorded_at)?.data?.recorded_at ??
          data.recentResults.find((r) => r.data?.created_at)?.data?.created_at ??
          null,
        required: Boolean(coverage && coverage.completedSessionsProbed > 0),
      },
    ];
  }, [data, outcomesSourceAvailable, pipeline?.outcomeCoverage]);

  const freshnessSources = sourceStatuses.map((source) => ({
    name: source.name,
    available: source.available,
    required: source.required ?? true,
    timestamp: source.timestamp,
  }));

  const unavailableSources = sourceStatuses
    .filter((source) => !source.available)
    .map((source) => source.name);
  const allFailed =
    Boolean(data) &&
    sourceStatuses.filter((s) => s.required).length > 0 &&
    sourceStatuses.filter((s) => s.required).every((s) => !s.available);
  const partialData = Boolean(data) && unavailableSources.length > 0 && !allFailed;
  const outcomeHint =
    outcomeCoverage && outcomeCoverage.completedSessionsProbed > 0
      ? `${outcomeCoverage.resultsLoaded} of ${outcomeCoverage.completedSessionsProbed} recent outcomes loaded`
      : "From completed sessions";

  if (loading && !data) {
    return <LoadingState label="Loading Validate pipeline…" />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={() => void reload()} />;
  }

  return (
    <ValidatePageChrome
      title="Validate"
      description="What setup am I validating, and what must happen next? Paper validation pipeline only."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="validate-hub-page"
      activeHref={validateHubHref()}
    >
      {allFailed ? (
        <ErrorState
          message="All Validate sources are unavailable. Counts are not shown as zero."
          onRetry={() => void reload()}
        />
      ) : null}

      {partialData ? (
        <div
          role="status"
          data-testid="validate-hub-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            {unavailableSources.join(", ")} unavailable. Showing available stages only
            {unavailableSources.includes("Outcomes")
              ? "; recent outcome coverage is incomplete"
              : ""}
            .
          </p>
          <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => void reload()}>
            Retry
          </Button>
        </div>
      ) : null}

      {pipeline ? (
        <>
          <section
            aria-labelledby="validate-counts-heading"
            className="space-y-3"
            data-testid="validate-stage-counts"
          >
            <h2 id="validate-counts-heading" className="text-lg font-semibold text-text-primary">
              Counts by stage
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <ValidationSummaryCard
                label="Drafts"
                count={pipeline.counts.draft}
                href="/paper-validation/drafts"
                hint="Prep before queue"
              />
              <ValidationSummaryCard
                label="Candidates"
                count={pipeline.counts.candidate}
                href="/paper-validation/candidates"
                hint="Review and compare"
              />
              <ValidationSummaryCard
                label="Run plans"
                count={pipeline.counts.run_plan}
                href="/paper-validation/run-plans"
                hint="Criteria before session"
              />
              <ValidationSummaryCard
                label="Run sessions"
                count={pipeline.counts.run_session}
                href="/paper-validation/run-sessions"
                hint="Active and historical"
              />
              <ValidationSummaryCard
                label="Active observations"
                count={pipeline.counts.observation}
                href="/paper-validation/run-sessions"
                hint="Running sessions only"
              />
              <ValidationSummaryCard
                label="Recent outcomes"
                count={pipeline.counts.outcome}
                href="/paper-validation/run-sessions"
                hint={outcomeHint}
                testId="validation-summary-recent-outcomes"
              />
            </div>
            {outcomeCoverage && outcomeCoverage.completedSessionsProbed > 0 ? (
              <p
                className="text-caption text-text-muted"
                data-testid="validate-outcome-coverage"
              >
                Completed sessions probed: {outcomeCoverage.completedSessionsProbed}. Results
                loaded: {outcomeCoverage.resultsLoaded}. Not recorded:{" "}
                {outcomeCoverage.resultsNotRecorded}. Unavailable:{" "}
                {outcomeCoverage.resultsUnavailable}.
              </p>
            ) : null}
          </section>

          <ValidationPipeline stages={pipeline.stages} />

          <ValidationAttentionQueue
            items={pipeline.attention}
            partialData={partialData}
            unavailableSources={unavailableSources}
            onRetry={() => void reload()}
          />

          <section
            aria-labelledby="validate-active-sessions-heading"
            className="space-y-3"
            data-testid="validate-active-sessions"
          >
            <h2
              id="validate-active-sessions-heading"
              className="text-lg font-semibold text-text-primary"
            >
              Current active validation sessions
            </h2>
            {!data?.runSessions.available ? (
              <p role="status" className="text-sm text-warning">
                Run session source unavailable — active sessions cannot be listed.
              </p>
            ) : pipeline.activeSessions.length === 0 ? (
              <p className="text-sm text-text-muted">
                No running paper validation sessions from the available session source.
              </p>
            ) : (
              <div className="space-y-3">
                {pipeline.activeSessions.map((session) => (
                  <RunSessionSummaryCard
                    key={session.session_id}
                    session={session}
                    paperConfirmed={posture.paperConfirmed}
                  />
                ))}
              </div>
            )}
          </section>

          <section
            aria-labelledby="validate-recent-outcomes-heading"
            className="space-y-3"
            data-testid="validate-recent-outcomes"
          >
            <h2
              id="validate-recent-outcomes-heading"
              className="text-lg font-semibold text-text-primary"
            >
              Recent outcomes
            </h2>
            {!data?.runSessions.available ? (
              <p role="status" className="text-sm text-warning">
                Outcome list unavailable because run sessions failed to load.
              </p>
            ) : pipeline.recentOutcomes.length === 0 ? (
              <p className="text-sm text-text-muted">
                No completed sessions available to summarize outcomes.
              </p>
            ) : (
              <ul className="space-y-2">
                {pipeline.recentOutcomes.map((outcome) => (
                  <li
                    key={outcome.sessionId}
                    className="rounded-control border border-border-subtle px-4 py-3 text-sm"
                    data-testid={`validate-recent-outcome-${outcome.sessionId}`}
                  >
                    <p className="font-medium text-text-primary">
                      {outcome.symbol ?? "Setup"} · {outcome.condition ?? "condition unavailable"}
                    </p>
                    <p className="mt-1 text-text-secondary">
                      Outcome:{" "}
                      {!outcome.resultAvailable
                        ? "result unavailable"
                        : outcome.resultNotRecorded
                          ? "not recorded"
                          : (outcome.outcome?.replaceAll("_", " ") ?? "recorded")}
                    </p>
                    <Link
                      href={outcome.href}
                      className="mt-2 inline-flex min-h-11 items-center underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      Open session
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="validate-limitations-heading" data-testid="validate-limitations">
            <h2
              id="validate-limitations-heading"
              className="text-lg font-semibold text-text-primary"
            >
              Validation limitations
            </h2>
            <div className="mt-3">
              <LimitationsState
                title="Honest Validate coverage"
                message="Validate is a paper observation pipeline. It does not place orders or guarantee edge."
                items={pipeline.limitations}
              />
            </div>
          </section>

          <ValidationSourceAvailability sources={sourceStatuses} onRetry={() => void reload()} />
        </>
      ) : null}
    </ValidatePageChrome>
  );
}
