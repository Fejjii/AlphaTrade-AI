"use client";

import Link from "next/link";
import { useCallback } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";
import type { PaperValidationRunPlanItem } from "@/lib/api/types";

function formatConfidence(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function RunPlanCard({ plan }: { plan: PaperValidationRunPlanItem }) {
  return (
    <article
      className="rounded-lg border border-zinc-800 p-4 space-y-3"
      data-testid={`paper-run-plan-${plan.plan_id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(plan.condition ?? "unknown")}</Badge>
            <span className="text-sm font-medium text-zinc-100">
              {plan.symbol ?? "—"} · {plan.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{plan.direction ?? "—"}</Badge>
          </div>
          <p className="text-xs text-zinc-500">
            Planned {new Date(plan.created_at).toLocaleString()}
          </p>
        </div>
        <Badge variant="muted">{plan.plan_status}</Badge>
      </div>

      <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-3">
        <p>Window: {plan.validation_window ?? "—"}</p>
        <p>Observation: {plan.observation_timeframe ?? "—"}</p>
        <p>Max duration: {plan.max_duration_minutes ?? "—"} min</p>
        <p>Confidence: {formatConfidence(plan.confidence)}</p>
      </div>

      <Link
        href={`/paper-validation/run-plans/${plan.plan_id}`}
        className="inline-block text-xs text-zinc-400 underline"
      >
        View run plan detail
      </Link>
    </article>
  );
}

export default function PaperValidationRunPlansPage() {
  const loader = useCallback(() => api.strategies.runPlans({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading && !data) return <LoadingState label="Loading run plans…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-run-plans-page">
      <div>
        <h1 className="text-2xl font-semibold">Paper Validation Run Plans</h1>
        <p className="text-sm text-zinc-400">
          Structured run plans from reviewing candidates. Plan only — no run started, no orders, no
          proposals, no Telegram.
        </p>
      </div>

      {data?.items.length ? (
        <div className="space-y-3" data-testid="paper-validation-run-plans-list">
          {data.items.map((plan) => (
            <RunPlanCard key={plan.plan_id} plan={plan} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No run plans yet"
          description="Mark a candidate as reviewing, then create a run plan from the candidate detail page."
        />
      )}
    </div>
  );
}
