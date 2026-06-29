"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useParams } from "next/navigation";

import { ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationRunSessionStatus } from "@/lib/api/types";

export default function PaperValidationRunSessionDetailPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const [busy, setBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const loader = useCallback(() => api.strategies.getRunSession(sessionId), [sessionId]);
  const { data: session, loading, error, reload } = useAsyncData(loader, [sessionId]);

  async function handleStatusChange(nextStatus: PaperValidationRunSessionStatus) {
    setBusy(true);
    setStatusError(null);
    try {
      await api.strategies.updateRunSessionStatus(sessionId, { session_status: nextStatus });
      await reload();
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Failed to update status.");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !session) return <LoadingState label="Loading run session…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!session)
    return <ErrorState message="Run session not found." onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-run-session-detail">
      <div>
        <Link href="/paper-validation/run-sessions" className="text-xs text-zinc-400 underline">
          Back to run sessions
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Validation Run Session</h1>
        <p className="text-sm text-zinc-400" data-testid="paper-run-session-safety-copy">
          Record only. No live run. No order. No exchange. No proposal. No approval. No Telegram. No
          automation.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(session.condition ?? "unknown")}</Badge>
            <span>
              {session.symbol ?? "—"} · {session.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{session.session_status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-zinc-300">
          <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-2">
            <p>Direction: {session.direction ?? "—"}</p>
            <p>Risk mode: {session.risk_mode}</p>
            <p>Validation window: {session.validation_window ?? "—"}</p>
            <p>Observation timeframe: {session.observation_timeframe ?? "—"}</p>
            <p>Max duration: {session.max_duration_minutes ?? "—"} min</p>
            <p>Run plan: {session.run_plan_id}</p>
            <p>
              Started: {session.started_at ? new Date(session.started_at).toLocaleString() : "—"}
            </p>
            <p>Ended: {session.ended_at ? new Date(session.ended_at).toLocaleString() : "—"}</p>
          </div>

          {session.notes ? (
            <div className="space-y-2">
              <p className="font-medium text-zinc-200">Notes</p>
              <p>{session.notes}</p>
            </div>
          ) : null}

          {session.session_status === "running" ? (
            <div className="flex flex-wrap gap-2" data-testid="paper-run-session-actions">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => void handleStatusChange("completed")}
                data-testid="paper-run-session-mark-completed"
              >
                Mark completed
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => void handleStatusChange("cancelled")}
                data-testid="paper-run-session-mark-cancelled"
              >
                Cancel session
              </Button>
            </div>
          ) : null}
          {statusError ? <p className="text-sm text-red-400">{statusError}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
