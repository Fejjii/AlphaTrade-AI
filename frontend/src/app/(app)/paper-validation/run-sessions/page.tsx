"use client";

import { useCallback } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { RunSessionSummaryCard, ValidatePageChrome } from "@/components/validate";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

type RunSessionsPageData = {
  runSessions: SourceResult<Awaited<ReturnType<typeof api.strategies.runSessions>>>;
};

export default function PaperValidationRunSessionsPage() {
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<RunSessionsPageData> => {
    return { runSessions: await loadSource(api.strategies.runSessions({ limit: 50 })) };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);
  const available = data?.runSessions.available ?? false;
  const items = available ? (data?.runSessions.data?.items ?? []) : [];

  const freshnessSources = [
    {
      name: "Run sessions",
      available,
      required: true,
      timestamp: items[0]?.started_at ?? items[0]?.created_at ?? null,
    },
  ];

  if (loading && !data) return <LoadingState label="Loading run sessions…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <ValidatePageChrome
      title="Paper Validation Run Sessions"
      description="Manually started observation sessions from planned run plans. Record only — no live run, no orders, no proposals, no approvals, no Telegram, no automation."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="paper-validation-run-sessions-page"
      activeHref="/paper-validation/run-sessions"
    >
      {!available ? (
        <ErrorState
          message={
            data?.runSessions.error ??
            "Run session source unavailable. Count is not shown as zero."
          }
          onRetry={() => void reload()}
        />
      ) : items.length ? (
        <div className="space-y-3" data-testid="paper-validation-run-sessions-list">
          {items.map((session) => (
            <RunSessionSummaryCard
              key={session.session_id}
              session={session}
              paperConfirmed={posture.paperConfirmed}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No run sessions yet"
          description="Open a planned run plan and start a run session from the run plan detail page. Available session source returned an empty list."
        />
      )}
    </ValidatePageChrome>
  );
}
