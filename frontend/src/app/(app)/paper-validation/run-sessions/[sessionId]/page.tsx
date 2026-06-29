"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { setupConditionLabel } from "@/lib/alert-display";
import {
  RECORD_PAPER_VALIDATION_OBSERVATION,
  RECORD_PAPER_VALIDATION_OUTCOME,
  type PaperValidationObservationKind,
  type PaperValidationOutcome,
  type PaperValidationCriteriaMet,
  type PaperValidationEntryAssessment,
  type PaperValidationDisciplineAssessment,
  type PaperValidationRunSessionStatus,
  type PaperValidationSessionObservationItem,
  type PaperValidationSessionResultItem,
} from "@/lib/api/types";

const OBSERVATION_KINDS: PaperValidationObservationKind[] = [
  "approached_trigger",
  "hit_trigger",
  "hit_invalidation",
  "missed_entry",
  "price_moved_without_entry",
  "price_update",
  "general_note",
];

const OUTCOMES: PaperValidationOutcome[] = [
  "success",
  "failure",
  "invalidated",
  "missed_entry",
  "no_trade",
  "inconclusive",
];

const CRITERIA_OPTIONS: PaperValidationCriteriaMet[] = ["met", "not_met", "partial", "unknown"];

const ENTRY_ASSESSMENTS: PaperValidationEntryAssessment[] = [
  "entered_as_planned",
  "missed_entry",
  "price_moved_without_entry",
  "no_entry",
];

const DISCIPLINE_ASSESSMENTS: PaperValidationDisciplineAssessment[] = [
  "disciplined",
  "should_have_waited",
  "should_have_entered",
  "should_have_avoided",
];

export default function PaperValidationRunSessionDetailPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const [busy, setBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [observations, setObservations] = useState<PaperValidationSessionObservationItem[]>([]);
  const [sessionResult, setSessionResult] = useState<PaperValidationSessionResultItem | null>(
    null,
  );
  const [obsKind, setObsKind] = useState<PaperValidationObservationKind>("general_note");
  const [obsPrice, setObsPrice] = useState("");
  const [obsNote, setObsNote] = useState("");
  const [obsConfirm, setObsConfirm] = useState("");
  const [obsError, setObsError] = useState<string | null>(null);
  const [resultOutcome, setResultOutcome] = useState<PaperValidationOutcome>("inconclusive");
  const [successCriteria, setSuccessCriteria] = useState<PaperValidationCriteriaMet>("unknown");
  const [failureCriteria, setFailureCriteria] = useState<PaperValidationCriteriaMet>("unknown");
  const [invalidationHit, setInvalidationHit] = useState(false);
  const [entryAssessment, setEntryAssessment] =
    useState<PaperValidationEntryAssessment>("no_entry");
  const [disciplineAssessment, setDisciplineAssessment] =
    useState<PaperValidationDisciplineAssessment>("disciplined");
  const [lessons, setLessons] = useState("");
  const [resultConfirm, setResultConfirm] = useState("");
  const [resultError, setResultError] = useState<string | null>(null);

  const loader = useCallback(() => api.strategies.getRunSession(sessionId), [sessionId]);
  const { data: session, loading, error, reload } = useAsyncData(loader, [sessionId]);

  const loadExtras = useCallback(async () => {
    try {
      const [obsList, result] = await Promise.all([
        api.strategies.sessionObservations(sessionId),
        api.strategies.getSessionResult(sessionId).catch(() => null),
      ]);
      setObservations(obsList.items);
      setSessionResult(result);
    } catch {
      setObservations([]);
      setSessionResult(null);
    }
  }, [sessionId]);

  useEffect(() => {
    if (session) {
      void loadExtras();
    }
  }, [session, loadExtras]);

  async function handleStatusChange(nextStatus: PaperValidationRunSessionStatus) {
    setBusy(true);
    setStatusError(null);
    try {
      await api.strategies.updateRunSessionStatus(sessionId, { session_status: nextStatus });
      await reload();
      await loadExtras();
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Failed to update status.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRecordObservation() {
    setBusy(true);
    setObsError(null);
    try {
      await api.strategies.recordObservation(sessionId, {
        confirm: RECORD_PAPER_VALIDATION_OBSERVATION,
        observation_kind: obsKind,
        observed_price: obsPrice ? Number(obsPrice) : null,
        note: obsNote || null,
      });
      setObsConfirm("");
      setObsNote("");
      setObsPrice("");
      await loadExtras();
    } catch (err) {
      setObsError(err instanceof Error ? err.message : "Failed to record observation.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRecordResult() {
    setBusy(true);
    setResultError(null);
    try {
      const payload = {
        confirm: RECORD_PAPER_VALIDATION_OUTCOME,
        outcome: resultOutcome,
        success_criteria_met: successCriteria,
        failure_criteria_met: failureCriteria,
        invalidation_hit: invalidationHit,
        entry_assessment: entryAssessment,
        discipline_assessment: disciplineAssessment,
        lessons: lessons || null,
      };
      const response = await api.strategies.recordSessionResult(sessionId, payload);
      setSessionResult(response.result);
      setResultConfirm("");
    } catch (err) {
      setResultError(err instanceof Error ? err.message : "Failed to record outcome.");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !session) return <LoadingState label="Loading run session…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!session)
    return <ErrorState message="Run session not found." onRetry={() => void reload()} />;

  const isRunning = session.session_status === "running";
  const canComplete = isRunning && sessionResult !== null;

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

          {isRunning ? (
            <div className="flex flex-wrap gap-2" data-testid="paper-run-session-actions">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy || !canComplete}
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
          {isRunning && !sessionResult ? (
            <p className="text-xs text-amber-400" data-testid="paper-run-session-outcome-required">
              Record a session outcome before marking completed.
            </p>
          ) : null}
          {statusError ? <p className="text-sm text-red-400">{statusError}</p> : null}
        </CardContent>
      </Card>

      <Card data-testid="paper-run-session-observations">
        <CardHeader>
          <CardTitle className="text-base">Observation timeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {observations.length === 0 ? (
            <p className="text-zinc-400">No observations recorded yet.</p>
          ) : (
            <ul className="space-y-2">
              {observations.map((obs) => (
                <li
                  key={obs.observation_id}
                  className="rounded border border-zinc-800 p-3"
                  data-testid="paper-run-session-observation-item"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{obs.observation_kind}</Badge>
                    {obs.observed_price != null ? <span>{obs.observed_price}</span> : null}
                    <span className="text-xs text-zinc-500">
                      {obs.created_at ? new Date(obs.created_at).toLocaleString() : ""}
                    </span>
                  </div>
                  {obs.note ? <p className="mt-1 text-zinc-300">{obs.note}</p> : null}
                </li>
              ))}
            </ul>
          )}

          {isRunning ? (
            <div className="space-y-3 border-t border-zinc-800 pt-4" data-testid="paper-run-session-observation-form">
              <label className="block text-xs text-zinc-400">
                Kind
                <select
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={obsKind}
                  onChange={(e) => setObsKind(e.target.value as PaperValidationObservationKind)}
                >
                  {OBSERVATION_KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {kind}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                Observed price (optional)
                <input
                  type="number"
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={obsPrice}
                  onChange={(e) => setObsPrice(e.target.value)}
                />
              </label>
              <label className="block text-xs text-zinc-400">
                Note
                <textarea
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  rows={2}
                  value={obsNote}
                  onChange={(e) => setObsNote(e.target.value)}
                />
              </label>
              <label className="block text-xs text-zinc-400">
                Type {RECORD_PAPER_VALIDATION_OBSERVATION} to confirm
                <input
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={obsConfirm}
                  onChange={(e) => setObsConfirm(e.target.value)}
                  data-testid="paper-run-session-observation-confirm"
                />
              </label>
              <Button
                type="button"
                size="sm"
                disabled={busy || obsConfirm !== RECORD_PAPER_VALIDATION_OBSERVATION}
                onClick={() => void handleRecordObservation()}
                data-testid="paper-run-session-observation-submit"
              >
                Record observation
              </Button>
              {obsError ? <p className="text-sm text-red-400">{obsError}</p> : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card data-testid="paper-run-session-result">
        <CardHeader>
          <CardTitle className="text-base">Session outcome</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {sessionResult ? (
            <div className="space-y-2 text-zinc-300" data-testid="paper-run-session-result-summary">
              <p>
                Outcome: <Badge variant="muted">{sessionResult.outcome}</Badge>
              </p>
              <p>Success criteria: {sessionResult.success_criteria_met}</p>
              <p>Failure criteria: {sessionResult.failure_criteria_met}</p>
              <p>Entry assessment: {sessionResult.entry_assessment}</p>
              <p>Discipline: {sessionResult.discipline_assessment}</p>
              {sessionResult.lessons ? <p>Lessons: {sessionResult.lessons}</p> : null}
            </div>
          ) : isRunning ? (
            <div className="space-y-3" data-testid="paper-run-session-result-form">
              <label className="block text-xs text-zinc-400">
                Outcome
                <select
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={resultOutcome}
                  onChange={(e) => setResultOutcome(e.target.value as PaperValidationOutcome)}
                >
                  {OUTCOMES.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                Success criteria met
                <select
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={successCriteria}
                  onChange={(e) =>
                    setSuccessCriteria(e.target.value as PaperValidationCriteriaMet)
                  }
                >
                  {CRITERIA_OPTIONS.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                Failure criteria met
                <select
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={failureCriteria}
                  onChange={(e) =>
                    setFailureCriteria(e.target.value as PaperValidationCriteriaMet)
                  }
                >
                  {CRITERIA_OPTIONS.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-xs text-zinc-400">
                <input
                  type="checkbox"
                  checked={invalidationHit}
                  onChange={(e) => setInvalidationHit(e.target.checked)}
                />
                Invalidation hit
              </label>
              <label className="block text-xs text-zinc-400">
                Entry assessment
                <select
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={entryAssessment}
                  onChange={(e) =>
                    setEntryAssessment(e.target.value as PaperValidationEntryAssessment)
                  }
                >
                  {ENTRY_ASSESSMENTS.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                Discipline assessment
                <select
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={disciplineAssessment}
                  onChange={(e) =>
                    setDisciplineAssessment(e.target.value as PaperValidationDisciplineAssessment)
                  }
                >
                  {DISCIPLINE_ASSESSMENTS.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                Lessons
                <textarea
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  rows={3}
                  value={lessons}
                  onChange={(e) => setLessons(e.target.value)}
                />
              </label>
              <label className="block text-xs text-zinc-400">
                Type {RECORD_PAPER_VALIDATION_OUTCOME} to confirm
                <input
                  className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  value={resultConfirm}
                  onChange={(e) => setResultConfirm(e.target.value)}
                  data-testid="paper-run-session-result-confirm"
                />
              </label>
              <Button
                type="button"
                size="sm"
                disabled={busy || resultConfirm !== RECORD_PAPER_VALIDATION_OUTCOME}
                onClick={() => void handleRecordResult()}
                data-testid="paper-run-session-result-submit"
              >
                Record outcome
              </Button>
              {resultError ? <p className="text-sm text-red-400">{resultError}</p> : null}
            </div>
          ) : (
            <p className="text-zinc-400">No outcome recorded.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
