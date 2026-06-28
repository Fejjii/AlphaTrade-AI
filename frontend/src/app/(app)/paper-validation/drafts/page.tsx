"use client";

import Link from "next/link";
import { useCallback } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationDraftItem } from "@/lib/api/types";

function formatLevel(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatConfidence(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function DraftCard({ draft }: { draft: PaperValidationDraftItem }) {
  return (
    <article
      className="rounded-lg border border-zinc-800 p-4 space-y-3"
      data-testid={`paper-draft-${draft.draft_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(draft.condition ?? "unknown")}</Badge>
            <span className="text-sm font-medium text-zinc-100">
              {draft.symbol ?? "—"} · {draft.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{draft.direction ?? "—"}</Badge>
            {draft.is_ready_for_validation ? (
              <Badge variant="default" data-testid={`paper-draft-ready-${draft.draft_id}`}>
                Ready
              </Badge>
            ) : null}
          </div>
          <p className="text-xs text-zinc-500">
            Created {new Date(draft.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant="muted">{draft.status}</Badge>
          <span className="text-xs text-zinc-500">Prep: {draft.prep_status ?? "draft"}</span>
          <span className="text-xs text-zinc-500">
            Score: {draft.prep_completion_score ?? 0}%
          </span>
        </div>
      </div>

      <p className="text-sm text-zinc-300">{draft.reason ?? "No reason provided."}</p>

      <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-4">
        <p>Confidence: {formatConfidence(draft.confidence)}</p>
        <p>Trigger: {formatLevel(draft.trigger_level)}</p>
        <p>Invalidation: {formatLevel(draft.invalidation_level)}</p>
        <p>Latest: {formatLevel(draft.latest_price)}</p>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-zinc-400">
        <span>Risk mode: {draft.risk_mode}</span>
        <span>Source alert: {draft.source_alert_id.slice(0, 8)}…</span>
      </div>

      <Link
        href={`/paper-validation/drafts/${draft.draft_id}`}
        className="inline-block text-xs text-zinc-400 underline"
      >
        View draft detail
      </Link>
    </article>
  );
}

export default function PaperValidationDraftsPage() {
  const loader = useCallback(
    () => api.strategies.drafts({ limit: 50 }),
    [],
  );
  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading && !data) return <LoadingState label="Loading paper drafts…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-drafts-page">
      <div>
        <h1 className="text-2xl font-semibold">Paper Validation Drafts</h1>
        <p className="text-sm text-zinc-400">
          Non-executable paper-trade ideas from reviewed setup alerts. Drafts never place orders,
          send Telegram messages, or trigger execution.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Draft summary</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-300">
          <p>
            Active drafts: <span className="font-semibold text-zinc-100">{data?.total ?? 0}</span>
          </p>
        </CardContent>
      </Card>

      {data?.items.length ? (
        <div className="space-y-3" data-testid="paper-validation-drafts-list">
          {data.items.map((draft) => (
            <DraftCard key={draft.draft_id} draft={draft} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No paper drafts yet"
          description="Mark a setup alert as watching or important, then create a paper draft from the review page."
        />
      )}
    </div>
  );
}
