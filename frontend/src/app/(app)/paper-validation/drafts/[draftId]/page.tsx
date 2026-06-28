"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useParams } from "next/navigation";

import { ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";

function formatLevel(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export default function PaperValidationDraftDetailPage() {
  const params = useParams<{ draftId: string }>();
  const draftId = params.draftId;

  const loader = useCallback(
    () => api.strategies.getDraft(draftId),
    [draftId],
  );
  const { data: draft, loading, error, reload } = useAsyncData(loader, [draftId]);

  if (loading && !draft) return <LoadingState label="Loading draft…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!draft) return <ErrorState message="Draft not found." onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-draft-detail">
      <div>
        <Link href="/paper-validation/drafts" className="text-xs text-zinc-400 underline">
          Back to drafts
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Paper Draft Detail</h1>
        <p className="text-sm text-zinc-400">
          Draft only. No order. No Telegram. No execution.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(draft.condition ?? "unknown")}</Badge>
            <span>
              {draft.symbol ?? "—"} · {draft.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{draft.status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-zinc-300">
          <p>{draft.reason ?? "No reason provided."}</p>
          <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-2">
            <p>Direction: {draft.direction ?? "—"}</p>
            <p>Risk mode: {draft.risk_mode}</p>
            <p>Trigger: {formatLevel(draft.trigger_level)}</p>
            <p>Invalidation: {formatLevel(draft.invalidation_level)}</p>
            <p>Latest price: {formatLevel(draft.latest_price)}</p>
            <p>Source alert: {draft.source_alert_id}</p>
          </div>
          <p className="text-xs text-zinc-500">
            Created {new Date(draft.created_at).toLocaleString()}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
