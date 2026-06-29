"use client";

import Link from "next/link";
import { useCallback } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationRunSessionItem } from "@/lib/api/types";

function RunSessionCard({ session }: { session: PaperValidationRunSessionItem }) {
  return (
    <article
      className="rounded-lg border border-zinc-800 p-4 space-y-3"
      data-testid={`paper-run-session-${session.session_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(session.condition ?? "unknown")}</Badge>
            <span className="text-sm font-medium text-zinc-100">
              {session.symbol ?? "—"} · {session.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{session.direction ?? "—"}</Badge>
          </div>
          <p className="text-xs text-zinc-500">
            Started {session.started_at ? new Date(session.started_at).toLocaleString() : "—"}
          </p>
        </div>
        <Badge variant="muted">{session.session_status}</Badge>
      </div>

      <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-3">
        <p>Window: {session.validation_window ?? "—"}</p>
        <p>Observation: {session.observation_timeframe ?? "—"}</p>
        <p>Max duration: {session.max_duration_minutes ?? "—"} min</p>
      </div>

      <Link
        href={`/paper-validation/run-sessions/${session.session_id}`}
        className="inline-block text-xs text-zinc-400 underline"
      >
        View run session detail
      </Link>
    </article>
  );
}

export default function PaperValidationRunSessionsPage() {
  const loader = useCallback(() => api.strategies.runSessions({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading && !data) return <LoadingState label="Loading run sessions…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-run-sessions-page">
      <div>
        <h1 className="text-2xl font-semibold">Paper Validation Run Sessions</h1>
        <p className="text-sm text-zinc-400">
          Manually started observation sessions from planned run plans. Record only — no live run,
          no orders, no proposals, no approvals, no Telegram, no automation.
        </p>
      </div>

      {data?.items.length ? (
        <div className="space-y-3" data-testid="paper-validation-run-sessions-list">
          {data.items.map((session) => (
            <RunSessionCard key={session.session_id} session={session} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No run sessions yet"
          description="Open a planned run plan and start a run session from the run plan detail page."
        />
      )}
    </div>
  );
}
