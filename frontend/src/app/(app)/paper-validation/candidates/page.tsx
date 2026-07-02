"use client";

import Link from "next/link";
import { useCallback } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationCandidateItem } from "@/lib/api/types";

function formatLevel(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatConfidence(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function CandidateCard({ candidate }: { candidate: PaperValidationCandidateItem }) {
  return (
    <article
      className="rounded-lg border border-zinc-800 p-4 space-y-3"
      data-testid={`paper-candidate-${candidate.candidate_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">
              {setupConditionLabel(candidate.condition ?? "unknown")}
            </Badge>
            <span className="text-sm font-medium text-zinc-100">
              {candidate.symbol ?? "—"} · {candidate.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{candidate.direction ?? "—"}</Badge>
          </div>
          <p className="text-xs text-zinc-500">
            Queued {new Date(candidate.created_at).toLocaleString()}
          </p>
        </div>
        <Badge variant="muted">{candidate.candidate_status}</Badge>
      </div>

      <p className="text-sm text-zinc-300">{candidate.thesis ?? "No thesis provided."}</p>

      <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-4">
        <p>Confidence: {formatConfidence(candidate.confidence)}</p>
        <p>Trigger: {formatLevel(candidate.trigger_level)}</p>
        <p>Invalidation: {formatLevel(candidate.invalidation_level)}</p>
        <p>Latest: {formatLevel(candidate.latest_price)}</p>
      </div>

      <Link
        href={`/paper-validation/candidates/${candidate.candidate_id}`}
        className="inline-block text-xs text-zinc-400 underline"
      >
        View candidate detail
      </Link>
    </article>
  );
}

export default function PaperValidationCandidatesPage() {
  const loader = useCallback(
    () => api.strategies.candidates({ limit: 50 }),
    [],
  );
  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading && !data) return <LoadingState label="Loading paper validation queue…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-candidates-page">
      <div>
        <h1 className="text-2xl font-semibold">Paper Validation Queue</h1>
        <p className="text-sm text-zinc-400">
          Structured validation candidates from ready drafts. Queue only — no run started, no orders,
          no proposals, no Telegram.
        </p>
      </div>

      {data?.items.length ? (
        <div className="space-y-3" data-testid="paper-validation-candidates-list">
          {data.items.map((candidate) => (
            <CandidateCard key={candidate.candidate_id} candidate={candidate} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No validation candidates yet"
          description="Mark a draft ready for validation, then queue it from the draft detail page."
        />
      )}
    </div>
  );
}
