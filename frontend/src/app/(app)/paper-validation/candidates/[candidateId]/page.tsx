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

const CREATE_PAPER_VALIDATION_RUN_PLAN = "CREATE_PAPER_VALIDATION_RUN_PLAN";

const DEFAULT_PLAN = {
  validation_window: "intraday",
  observation_timeframe: "1h",
  max_duration_minutes: "240",
  planned_entry_rule: "Wait for price confirmation around trigger level.",
  planned_invalidation_rule: "Invalid if price closes beyond invalidation level.",
  planned_success_criteria: "Price moves toward first target area without invalidation.",
  planned_failure_criteria: "Invalidation level hit or thesis no longer valid.",
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
  const [planConfirm, setPlanConfirm] = useState("");
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [createdPlanId, setCreatedPlanId] = useState<string | null>(null);
  const [validationWindow, setValidationWindow] = useState(DEFAULT_PLAN.validation_window);
  const [observationTimeframe, setObservationTimeframe] = useState(
    DEFAULT_PLAN.observation_timeframe,
  );
  const [maxDurationMinutes, setMaxDurationMinutes] = useState(DEFAULT_PLAN.max_duration_minutes);
  const [plannedEntryRule, setPlannedEntryRule] = useState(DEFAULT_PLAN.planned_entry_rule);
  const [plannedInvalidationRule, setPlannedInvalidationRule] = useState(
    DEFAULT_PLAN.planned_invalidation_rule,
  );
  const [plannedSuccessCriteria, setPlannedSuccessCriteria] = useState(
    DEFAULT_PLAN.planned_success_criteria,
  );
  const [plannedFailureCriteria, setPlannedFailureCriteria] = useState(
    DEFAULT_PLAN.planned_failure_criteria,
  );

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

  async function handleCreatePlan() {
    setPlanning(true);
    setPlanError(null);
    try {
      const result = await api.strategies.createRunPlan(candidateId, {
        confirm: planConfirm,
        validation_window: validationWindow,
        observation_timeframe: observationTimeframe,
        max_duration_minutes: Number(maxDurationMinutes),
        planned_entry_rule: plannedEntryRule,
        planned_invalidation_rule: plannedInvalidationRule,
        planned_success_criteria: plannedSuccessCriteria,
        planned_failure_criteria: plannedFailureCriteria,
      });
      setCreatedPlanId(result.plan.plan_id);
      setPlanConfirm("");
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : "Failed to create run plan.");
    } finally {
      setPlanning(false);
    }
  }

  if (loading && !candidate) return <LoadingState label="Loading candidate…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!candidate) return <ErrorState message="Candidate not found." onRetry={() => void reload()} />;

  return (
    <div className="space-y-6" data-testid="paper-validation-candidate-detail">
      <div>
        <Link href="/paper-validation/candidates" className="text-xs text-zinc-400 underline">
          Back to paper validation queue
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

      {candidate.candidate_status === "reviewing" ? (
        <Card data-testid="paper-candidate-create-plan-section">
          <CardHeader>
            <CardTitle className="text-base">Create Run Plan</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-zinc-400" data-testid="paper-candidate-plan-safety-copy">
              Plan only. No run started. No order. No proposal. No approval. No Telegram.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block space-y-1 text-sm">
                <span className="text-zinc-300">Validation window</span>
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={validationWindow}
                  onChange={(event) => setValidationWindow(event.target.value)}
                  data-testid="paper-candidate-plan-validation-window"
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="text-zinc-300">Observation timeframe</span>
                <input
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={observationTimeframe}
                  onChange={(event) => setObservationTimeframe(event.target.value)}
                  data-testid="paper-candidate-plan-observation-timeframe"
                />
              </label>
              <label className="block space-y-1 text-sm sm:col-span-2">
                <span className="text-zinc-300">Max duration (minutes)</span>
                <input
                  type="number"
                  min={1}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={maxDurationMinutes}
                  onChange={(event) => setMaxDurationMinutes(event.target.value)}
                  data-testid="paper-candidate-plan-max-duration"
                />
              </label>
              <label className="block space-y-1 text-sm sm:col-span-2">
                <span className="text-zinc-300">Planned entry rule</span>
                <textarea
                  className="min-h-20 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={plannedEntryRule}
                  onChange={(event) => setPlannedEntryRule(event.target.value)}
                  data-testid="paper-candidate-plan-entry-rule"
                />
              </label>
              <label className="block space-y-1 text-sm sm:col-span-2">
                <span className="text-zinc-300">Planned invalidation rule</span>
                <textarea
                  className="min-h-20 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={plannedInvalidationRule}
                  onChange={(event) => setPlannedInvalidationRule(event.target.value)}
                  data-testid="paper-candidate-plan-invalidation-rule"
                />
              </label>
              <label className="block space-y-1 text-sm sm:col-span-2">
                <span className="text-zinc-300">Planned success criteria</span>
                <textarea
                  className="min-h-20 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={plannedSuccessCriteria}
                  onChange={(event) => setPlannedSuccessCriteria(event.target.value)}
                  data-testid="paper-candidate-plan-success-criteria"
                />
              </label>
              <label className="block space-y-1 text-sm sm:col-span-2">
                <span className="text-zinc-300">Planned failure criteria</span>
                <textarea
                  className="min-h-20 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                  value={plannedFailureCriteria}
                  onChange={(event) => setPlannedFailureCriteria(event.target.value)}
                  data-testid="paper-candidate-plan-failure-criteria"
                />
              </label>
            </div>
            <label className="block space-y-1 text-sm">
              <span className="text-zinc-300">
                Type <span className="font-mono text-zinc-100">{CREATE_PAPER_VALIDATION_RUN_PLAN}</span>{" "}
                to confirm
              </span>
              <input
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                value={planConfirm}
                onChange={(event) => setPlanConfirm(event.target.value)}
                data-testid="paper-candidate-plan-confirm"
              />
            </label>
            {planError ? <p className="text-sm text-red-400">{planError}</p> : null}
            {createdPlanId ? (
              <Link
                href={`/paper-validation/run-plans/${createdPlanId}`}
                className="inline-block text-sm text-emerald-400 underline"
                data-testid="paper-candidate-plan-link"
              >
                View run plan
              </Link>
            ) : null}
            <Button
              type="button"
              disabled={planning || planConfirm !== CREATE_PAPER_VALIDATION_RUN_PLAN}
              onClick={() => void handleCreatePlan()}
              data-testid="paper-candidate-plan-submit"
            >
              {planning ? "Creating plan…" : "Create run plan"}
            </Button>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
