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
import type { PaperValidationRunPlanStatus } from "@/lib/api/types";

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

export default function PaperValidationRunPlanDetailPage() {
  const params = useParams<{ planId: string }>();
  const planId = params.planId;
  const [busy, setBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const loader = useCallback(() => api.strategies.getRunPlan(planId), [planId]);
  const { data: plan, loading, error, reload } = useAsyncData(loader, [planId]);

  async function handleStatusChange(nextStatus: PaperValidationRunPlanStatus) {
    setBusy(true);
    setStatusError(null);
    try {
      await api.strategies.updateRunPlanStatus(planId, { plan_status: nextStatus });
      await reload();
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Failed to update status.");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !plan) return <LoadingState label="Loading run plan…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!plan) return <ErrorState message="Run plan not found." onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-run-plan-detail">
      <div>
        <Link href="/paper-validation/run-plans" className="text-xs text-zinc-400 underline">
          Back to run plans
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Validation Run Plan</h1>
        <p className="text-sm text-zinc-400" data-testid="paper-run-plan-safety-copy">
          Plan only. No run started. No order. No proposal. No approval. No Telegram.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex flex-wrap items-center gap-2">
            <Badge variant="info">{setupConditionLabel(plan.condition ?? "unknown")}</Badge>
            <span>
              {plan.symbol ?? "—"} · {plan.timeframe ?? "—"}
            </span>
            <Badge variant="muted">{plan.plan_status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-zinc-300">
          <div className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-2">
            <p>Direction: {plan.direction ?? "—"}</p>
            <p>Risk mode: {plan.risk_mode}</p>
            <p>Validation window: {plan.validation_window ?? "—"}</p>
            <p>Observation timeframe: {plan.observation_timeframe ?? "—"}</p>
            <p>Max duration: {plan.max_duration_minutes ?? "—"} min</p>
            <p>Trigger: {formatLevel(plan.trigger_level)}</p>
            <p>Invalidation: {formatLevel(plan.invalidation_level)}</p>
            <p>Candidate: {plan.candidate_id}</p>
          </div>

          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Planned entry rule</p>
            <p>{plan.planned_entry_rule ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Planned invalidation rule</p>
            <p>{plan.planned_invalidation_rule ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Planned success criteria</p>
            <p>{plan.planned_success_criteria ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Planned failure criteria</p>
            <p>{plan.planned_failure_criteria ?? "—"}</p>
          </div>
          <div className="space-y-2">
            <p className="font-medium text-zinc-200">Thesis</p>
            <p>{plan.thesis ?? "—"}</p>
          </div>

          <div className="space-y-2" data-testid="paper-run-plan-checklist">
            <p className="font-medium text-zinc-200">Checklist snapshot</p>
            <ul className="space-y-1 text-xs text-zinc-400">
              {Object.entries(plan.checklist_snapshot ?? {}).map(([key, value]) => (
                <li key={key}>
                  {CHECKLIST_LABELS[key] ?? key}: {value ? "Yes" : "No"}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-wrap gap-2">
            {plan.plan_status === "planned" ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => void handleStatusChange("needs_revision")}
                data-testid="paper-run-plan-mark-needs-revision"
              >
                Mark needs revision
              </Button>
            ) : null}
            {plan.plan_status !== "archived" ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => void handleStatusChange("archived")}
                data-testid="paper-run-plan-mark-archived"
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
