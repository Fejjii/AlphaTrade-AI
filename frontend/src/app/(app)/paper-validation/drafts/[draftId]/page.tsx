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
import type {
  PaperValidationDraftChecklist,
  PaperValidationDraftItem,
  PaperValidationDraftPrepStatus,
} from "@/lib/api/types";

const PREP_STATUSES: PaperValidationDraftPrepStatus[] = [
  "draft",
  "needs_review",
  "ready_for_validation",
  "archived",
];

const CHECKLIST_FIELDS: Array<{ key: keyof PaperValidationDraftChecklist; label: string }> = [
  { key: "trend_checked", label: "Trend checked" },
  { key: "support_resistance_checked", label: "Support / resistance checked" },
  { key: "volume_checked", label: "Volume checked" },
  { key: "risk_reward_checked", label: "Risk / reward checked" },
  { key: "invalidation_checked", label: "Invalidation checked" },
  { key: "higher_timeframe_checked", label: "Higher timeframe checked" },
  { key: "news_or_funding_checked", label: "News or funding checked" },
];

const EMPTY_CHECKLIST: PaperValidationDraftChecklist = {
  trend_checked: false,
  support_resistance_checked: false,
  volume_checked: false,
  risk_reward_checked: false,
  invalidation_checked: false,
  higher_timeframe_checked: false,
  news_or_funding_checked: false,
};

const QUEUE_PAPER_VALIDATION_CANDIDATE = "QUEUE_PAPER_VALIDATION_CANDIDATE";

function formatLevel(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatChecklistLabel(key: string): string {
  return key.replaceAll("_", " ");
}

export default function PaperValidationDraftDetailPage() {
  const params = useParams<{ draftId: string }>();
  const draftId = params.draftId;

  const loader = useCallback(
    () => api.strategies.getDraft(draftId),
    [draftId],
  );
  const { data: draft, loading, error, reload } = useAsyncData(loader, [draftId]);

  const [thesis, setThesis] = useState("");
  const [entryCriteria, setEntryCriteria] = useState("");
  const [invalidationCriteria, setInvalidationCriteria] = useState("");
  const [riskNotes, setRiskNotes] = useState("");
  const [prepStatus, setPrepStatus] = useState<PaperValidationDraftPrepStatus>("draft");
  const [checklist, setChecklist] = useState<PaperValidationDraftChecklist>(EMPTY_CHECKLIST);
  const [prepDraft, setPrepDraft] = useState<PaperValidationDraftItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [queueConfirm, setQueueConfirm] = useState("");
  const [queuing, setQueuing] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [queuedCandidateId, setQueuedCandidateId] = useState<string | null>(null);

  useEffect(() => {
    if (!draft) return;
    setThesis(draft.thesis ?? "");
    setEntryCriteria(draft.entry_criteria ?? "");
    setInvalidationCriteria(draft.invalidation_criteria ?? "");
    setRiskNotes(draft.risk_notes ?? "");
    setPrepStatus(draft.prep_status ?? "draft");
    setChecklist(draft.checklist ?? EMPTY_CHECKLIST);
    setPrepDraft(draft);
  }, [draft]);

  const activeDraft = prepDraft ?? draft;

  async function handleSavePrep() {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.strategies.updateDraftPrep(draftId, {
        prep_status: prepStatus,
        thesis,
        entry_criteria: entryCriteria,
        invalidation_criteria: invalidationCriteria,
        risk_notes: riskNotes,
        checklist,
      });
      setPrepDraft(updated);
      await reload();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save prep.");
    } finally {
      setSaving(false);
    }
  }

  async function handleQueueCandidate() {
    setQueuing(true);
    setQueueError(null);
    try {
      const result = await api.strategies.queueDraft(draftId, {
        confirm: queueConfirm,
      });
      setQueuedCandidateId(result.candidate.candidate_id);
      setQueueConfirm("");
    } catch (err) {
      setQueueError(err instanceof Error ? err.message : "Failed to queue candidate.");
    } finally {
      setQueuing(false);
    }
  }

  if (loading && !draft) return <LoadingState label="Loading draft…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!draft || !activeDraft) {
    return <ErrorState message="Draft not found." onRetry={() => void reload()} />;
  }

  return (
    <div className="space-y-6" data-testid="paper-validation-draft-detail">
      <div>
        <Link href="/paper-validation/drafts" className="text-xs text-zinc-400 underline">
          Back to drafts
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Paper Draft Detail</h1>
        <p className="text-sm text-zinc-400" data-testid="paper-draft-safety-copy">
          Prep only. No order. No execution. No proposal. No approval.
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
            {activeDraft.is_ready_for_validation ? (
              <Badge variant="default" data-testid="paper-draft-ready-badge">
                Ready for validation
              </Badge>
            ) : null}
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

      <Card data-testid="paper-draft-prep-section">
        <CardHeader>
          <CardTitle className="text-base">Paper Validation Prep</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 text-sm text-zinc-300">
            <p data-testid="paper-draft-prep-score">
              Completion score:{" "}
              <span className="font-semibold text-zinc-100">
                {activeDraft.prep_completion_score}%
              </span>
            </p>
            <p>
              Prep status:{" "}
              <span className="font-semibold text-zinc-100">{activeDraft.prep_status}</span>
            </p>
          </div>

          {activeDraft.missing_checklist_items.length ? (
            <div className="text-xs text-zinc-400" data-testid="paper-draft-missing-items">
              Missing checklist:{" "}
              {activeDraft.missing_checklist_items.map(formatChecklistLabel).join(", ")}
            </div>
          ) : null}

          <label className="block space-y-1 text-sm">
            <span className="text-zinc-300">Prep status</span>
            <select
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              value={prepStatus}
              onChange={(event) =>
                setPrepStatus(event.target.value as PaperValidationDraftPrepStatus)
              }
              data-testid="paper-draft-prep-status"
            >
              {PREP_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-1 text-sm">
            <span className="text-zinc-300">Thesis</span>
            <textarea
              className="min-h-24 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              value={thesis}
              onChange={(event) => setThesis(event.target.value)}
              data-testid="paper-draft-thesis"
            />
          </label>

          <label className="block space-y-1 text-sm">
            <span className="text-zinc-300">Entry criteria</span>
            <textarea
              className="min-h-24 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              value={entryCriteria}
              onChange={(event) => setEntryCriteria(event.target.value)}
              data-testid="paper-draft-entry-criteria"
            />
          </label>

          <label className="block space-y-1 text-sm">
            <span className="text-zinc-300">Invalidation criteria</span>
            <textarea
              className="min-h-24 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              value={invalidationCriteria}
              onChange={(event) => setInvalidationCriteria(event.target.value)}
              data-testid="paper-draft-invalidation-criteria"
            />
          </label>

          <label className="block space-y-1 text-sm">
            <span className="text-zinc-300">Risk notes</span>
            <textarea
              className="min-h-20 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              value={riskNotes}
              onChange={(event) => setRiskNotes(event.target.value)}
              data-testid="paper-draft-risk-notes"
            />
          </label>

          <div className="space-y-2" data-testid="paper-draft-checklist">
            <p className="text-sm font-medium text-zinc-200">Checklist</p>
            {CHECKLIST_FIELDS.map(({ key, label }) => (
              <label key={key} className="flex items-center gap-2 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={checklist[key]}
                  onChange={(event) =>
                    setChecklist((current) => ({ ...current, [key]: event.target.checked }))
                  }
                  data-testid={`paper-draft-checklist-${key}`}
                />
                {label}
              </label>
            ))}
          </div>

          {saveError ? <p className="text-sm text-red-400">{saveError}</p> : null}

          <Button
            type="button"
            onClick={() => void handleSavePrep()}
            disabled={saving}
            data-testid="paper-draft-save-prep"
          >
            {saving ? "Saving prep…" : "Save prep"}
          </Button>
        </CardContent>
      </Card>

      {activeDraft.is_ready_for_validation ? (
        <Card data-testid="paper-draft-queue-section">
          <CardHeader>
            <CardTitle className="text-base">Queue for Paper Validation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-zinc-400" data-testid="paper-draft-queue-safety-copy">
              Queue only. No run started. No order. No proposal. No approval. No Telegram.
            </p>
            <label className="block space-y-1 text-sm">
              <span className="text-zinc-300">
                Type <span className="font-mono text-zinc-100">{QUEUE_PAPER_VALIDATION_CANDIDATE}</span>{" "}
                to confirm
              </span>
              <input
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
                value={queueConfirm}
                onChange={(event) => setQueueConfirm(event.target.value)}
                data-testid="paper-draft-queue-confirm"
              />
            </label>
            {queueError ? <p className="text-sm text-red-400">{queueError}</p> : null}
            {queuedCandidateId ? (
              <Link
                href={`/paper-validation/candidates/${queuedCandidateId}`}
                className="inline-block text-sm text-emerald-400 underline"
                data-testid="paper-draft-candidate-link"
              >
                View validation candidate
              </Link>
            ) : null}
            <Button
              type="button"
              disabled={queuing || queueConfirm !== QUEUE_PAPER_VALIDATION_CANDIDATE}
              onClick={() => void handleQueueCandidate()}
              data-testid="paper-draft-queue-submit"
            >
              {queuing ? "Queueing…" : "Queue for paper validation"}
            </Button>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
