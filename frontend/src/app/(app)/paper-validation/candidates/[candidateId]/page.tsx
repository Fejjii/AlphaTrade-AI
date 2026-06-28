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
import type { PaperValidationCandidateStatus } from "@/lib/api/types";

const CHECKLIST_LABELS: Record<string, string> = {
  trend_checked: "Trend checked",
  support_resistance_checked: "Support / resistance checked",
  volume_checked: "Volume checked",
  risk_reward_checked: "Risk / reward checked",
  invalidation_checked: "Invalidation checked",
  higher_timeframe_checked: "Higher timeframe checked",
  news_or_funding_checked: "News or funding checked",
};

function formatLevel(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export default function PaperValidationCandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const candidateId = params.candidateId;
  const [busy, setBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const loader = useCallback(
    () => api.strategies.getCandidate(candidateId),
    [candidateId],
  );
  const { data: candidate, loading, error, reload } = useAsyncData(loader, [candidateId]);

  async function handleStatusChange(nextStatus: PaperValidationCandidateStatus) {
    setBusy(true);
    setStatusError(null);
    try {
      await api.strategies.updateCandidateStatus(candidateId, { candidate_status: nextStatus });
      await reload();
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Failed to update status.");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !candidate) return <LoadingState label="Loading candidate…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!candidate) return <ErrorState message="Candidate not found." onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-candidate-detail">
      <div>
        <Link href="/paper-validation/candidates" className="text-xs text-zinc-400 underline">
          Back to validation queue
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Validation Candidate</h1>
        <p className="text-sm text-zinc-400" data-testid="paper-candidate-safety-copy">
          Queue only. No run started. No order. No proposal. No approval. No Telegram.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(candidate.condition ?? "unknown")}</Badge>
            <span>
              {candidate.symbol ?? "—"} · {candidate.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{candidate.candidate_status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-zinc-300">
          <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-2">
            <p>Direction: {candidate.direction ?? "—"}</p>
            <p>Risk mode: {candidate.risk_mode}</p>
            <p>Trigger: {formatLevel(candidate.trigger_level)}</p>
            <p>Invalidation: {formatLevel(candidate.invalidation_level)}</p>
            <p>Latest price: {formatLevel(candidate.latest_price)}</p>
            <p>Draft: {candidate.draft_id}</p>
          </div>

          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Thesis</p>
            <p>{candidate.thesis ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Entry criteria</p>
            <p>{candidate.entry_criteria ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Invalidation criteria</p>
            <p>{candidate.invalidation_criteria ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Risk notes</p>
            <p>{candidate.risk_notes ?? "—"}</p>
          </div>

          <div className="space-y-2" data-testid="paper-candidate-checklist">
            <p className="font-medium text-zinc-200">Checklist snapshot</p>
            <ul className="space-y-1 text-xs text-zinc-400">
              {Object.entries(candidate.checklist_snapshot ?? {}).map(([key, value]) => (
                <li key={key}>
                  {CHECKLIST_LABELS[key] ?? key}: {value ? "Yes" : "No"}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-wrap gap-2">
            {candidate.candidate_status === "queued" ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => void handleStatusChange("reviewing")}
                data-testid="paper-candidate-mark-reviewing"
              >
                Mark reviewing
              </Button>
            ) : null}
            {candidate.candidate_status !== "archived" ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => void handleStatusChange("archived")}
                data-testid="paper-candidate-mark-archived"
              >
                Archive
              </Button>
            ) : null}
          </div>
          {statusError ? <p className="text-sm text-red-400">{statusError}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
