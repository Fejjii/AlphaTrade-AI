"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { JournalEntryCard } from "@/components/JournalEntryCard";
import { DisciplineAnalysisPanel } from "@/components/journal/DisciplineAnalysisPanel";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { StrategyId } from "@/lib/api/types";
import {
  EMOTION_TAG_SUGGESTIONS,
  MISTAKE_TAG_SUGGESTIONS,
  SETUP_TYPE_OPTIONS,
} from "@/lib/setup-types";

export default function JournalPage() {
  const searchParams = useSearchParams();
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [strategyId, setStrategyId] = useState<StrategyId | "">("");
  const [rationale, setRationale] = useState("");
  const [lessons, setLessons] = useState("");
  const [improvementRule, setImprovementRule] = useState("");
  const [emotions, setEmotions] = useState("");
  const [mistakes, setMistakes] = useState("");
  const [linkedProposalId, setLinkedProposalId] = useState<string | undefined>();
  const [linkedPositionId, setLinkedPositionId] = useState<string | undefined>();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [disciplineId, setDisciplineId] = useState<string | null>(null);
  const [discipline, setDiscipline] = useState<Awaited<
    ReturnType<typeof api.journalDiscipline.analyze>
  > | null>(null);
  const [disciplineError, setDisciplineError] = useState<string | null>(null);
  const loader = useCallback(() => api.journal.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  useEffect(() => {
    const proposalId = searchParams.get("proposal_id");
    const positionId = searchParams.get("position_id");
    if (!proposalId && !positionId) return;
    void (async () => {
      try {
        const prefill = await api.journal.prefill({
          linked_proposal_id: proposalId ?? undefined,
          linked_position_id: positionId ?? undefined,
        });
        setSymbol(prefill.symbol);
        setStrategyId((prefill.strategy_id as StrategyId) ?? "");
        setRationale(prefill.entry_rationale);
        setLinkedProposalId(prefill.linked_proposal_id ?? undefined);
        setLinkedPositionId(prefill.linked_position_id ?? undefined);
      } catch {
        /* prefill optional */
      }
    })();
  }, [searchParams]);

  async function createEntry() {
    if (!rationale.trim()) return;
    setBusy(true);
    setMessage(null);
    try {
      await api.journal.create({
        symbol,
        timeframe: "1h",
        direction: "long",
        entry_rationale: rationale,
        lessons: lessons.trim() || undefined,
        improvement_rule: improvementRule.trim() || undefined,
        strategy_id: strategyId || undefined,
        linked_proposal_id: linkedProposalId,
        linked_position_id: linkedPositionId,
        emotions: emotions
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        mistakes: mistakes
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
      });
      setRationale("");
      setLessons("");
      setImprovementRule("");
      setEmotions("");
      setMistakes("");
      setMessage("Journal entry saved. Lessons sync to the knowledge base when enabled.");
      await reload();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save entry");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Journal</h1>
        <p className="text-sm text-zinc-400">
          Capture rationale, setup type, emotions, mistakes, lessons, and improvement rules. Use
          ?proposal_id= or ?position_id= to prefill from a trade.
        </p>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="journal-symbol">Symbol</Label>
            <Input
              id="journal-symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="journal-setup">Setup type</Label>
            <select
              id="journal-setup"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={strategyId}
              onChange={(e) => setStrategyId(e.target.value as StrategyId | "")}
            >
              <option value="">Select setup…</option>
              {SETUP_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="journal-rationale">Entry rationale</Label>
          <Textarea
            id="journal-rationale"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="journal-lessons">Lessons learned</Label>
          <Textarea id="journal-lessons" value={lessons} onChange={(e) => setLessons(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="journal-improvement">Improvement rule</Label>
          <Textarea
            id="journal-improvement"
            value={improvementRule}
            onChange={(e) => setImprovementRule(e.target.value)}
            placeholder="e.g. No entries until 15m close confirms bias"
          />
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="journal-emotions">Emotion tags (comma-separated)</Label>
            <Input id="journal-emotions" value={emotions} onChange={(e) => setEmotions(e.target.value)} />
            <p className="text-xs text-zinc-500">{EMOTION_TAG_SUGGESTIONS.join(", ")}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="journal-mistakes">Mistake tags (comma-separated)</Label>
            <Input id="journal-mistakes" value={mistakes} onChange={(e) => setMistakes(e.target.value)} />
            <p className="text-xs text-zinc-500">{MISTAKE_TAG_SUGGESTIONS.join(", ")}</p>
          </div>
        </div>
        <Button disabled={busy || !rationale.trim()} onClick={() => void createEntry()}>
          {busy ? "Saving…" : "Create journal entry"}
        </Button>
        {message ? (
          <p className={`text-sm ${message.includes("saved") ? "text-emerald-300" : "text-red-300"}`}>
            {message}
          </p>
        ) : null}
      </div>

      {loading ? <LoadingState label="Loading journal entries…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      <div className="grid gap-4">
        {data?.items.length ? (
          data.items.map((entry) => (
            <div key={entry.id} className="space-y-2">
              <JournalEntryCard entry={entry} />
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={async () => {
                  setDisciplineId(entry.id);
                  setDisciplineError(null);
                  try {
                    const result = await api.journalDiscipline.analyze(entry.id);
                    setDiscipline(result);
                  } catch (err) {
                    setDisciplineError(err instanceof Error ? err.message : "Analysis failed");
                    setDiscipline(null);
                  }
                }}
              >
                Discipline analysis
              </Button>
              {disciplineId === entry.id ? (
                <DisciplineAnalysisPanel
                  comparison={discipline?.comparison ?? null}
                  error={disciplineError}
                  lessonCandidateIds={discipline?.lesson_candidate_ids ?? []}
                  journalEntryId={entry.id}
                  onCreateLesson={
                    discipline?.lesson_candidate_ids?.length
                      ? undefined
                      : async () => {
                          const lesson =
                            discipline?.comparison.missed_runner?.recommended_lesson ??
                            discipline?.comparison.stop_loss_analysis?.lesson;
                          if (!lesson) return;
                          setBusy(true);
                          try {
                            await api.lessons.createCandidate({
                              source_type: "journal",
                              related_journal_entry_id: entry.id,
                              related_trade_id: entry.id,
                              lesson_text: lesson,
                              mistake_type: discipline?.comparison.missed_runner?.early_exit_flag
                                ? "early_exit"
                                : "discipline",
                              severity: "medium",
                            });
                            const result = await api.journalDiscipline.analyze(entry.id);
                            setDiscipline(result);
                          } finally {
                            setBusy(false);
                          }
                        }
                  }
                  createBusy={busy}
                />
              ) : null}
              <Button
                variant="destructive"
                size="sm"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api.journal.delete(entry.id);
                    await reload();
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Delete entry
              </Button>
            </div>
          ))
        ) : (
          <EmptyState
            title="No journal entries"
            description="Record trades and lessons to build your personal learning loop."
          />
        )}
      </div>
    </div>
  );
}
