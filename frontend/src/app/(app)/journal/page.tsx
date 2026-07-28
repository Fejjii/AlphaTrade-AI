"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  buildNeedsJournalingQueue,
  JournalHubChrome,
  JournalQuickEntry,
  JournalSourceAvailability,
  NeedsJournalingQueue,
  parseJournalQuery,
  RecentJournalEntries,
  type JournalPrefillState,
} from "@/components/journal";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { JournalEntry, PaginatedJournalEntries, PaginatedPositions } from "@/lib/api/types";

type JournalHubData = {
  entries: SourceResult<PaginatedJournalEntries>;
  closedPositions: SourceResult<PaginatedPositions>;
};

type RelatedSessionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; sessionId: string }
  | { status: "invalid"; message: string };

export default function JournalPage() {
  const searchParams = useSearchParams();
  const context = useMemo(() => parseJournalQuery(searchParams), [searchParams]);
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<JournalHubData> => {
    const [entries, closedPositions] = await Promise.all([
      loadSource(api.journal.list({ limit: 50 })),
      loadSource(api.positions.list({ status: "closed", limit: 50 })),
    ]);
    return { entries, closedPositions };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const [prefill, setPrefill] = useState<JournalPrefillState>({ status: "idle" });
  const [relatedSession, setRelatedSession] = useState<RelatedSessionState>({ status: "idle" });
  const [busy, setBusy] = useState(false);
  const [disciplineId, setDisciplineId] = useState<string | null>(null);
  const [discipline, setDiscipline] = useState<Awaited<
    ReturnType<typeof api.journalDiscipline.analyze>
  > | null>(null);
  const [disciplineError, setDisciplineError] = useState<string | null>(null);
  const [savedHighlightId, setSavedHighlightId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const proposalId = context.proposalId;
  const positionId = context.positionId;
  const sessionId = context.sessionId;

  useEffect(() => {
    if (!proposalId && !positionId) {
      setPrefill({ status: "idle" });
      return;
    }

    let cancelled = false;
    setPrefill({ status: "loading" });
    void (async () => {
      try {
        const result = await api.journal.prefill({
          linked_proposal_id: proposalId ?? undefined,
          linked_position_id: positionId ?? undefined,
        });
        if (cancelled) return;
        setPrefill({
          status: "ready",
          symbol: result.symbol,
          timeframe: result.timeframe,
          direction: result.direction,
          strategyId: result.strategy_id,
          entryRationale: result.entry_rationale,
          linkedProposalId: result.linked_proposal_id,
          linkedPositionId: result.linked_position_id,
          tags: result.tags,
        });
      } catch (err) {
        if (cancelled) return;
        setPrefill({
          status: "invalid",
          message:
            err instanceof Error
              ? `Prefill context is invalid or stale: ${err.message}. Quick entry was not silently linked to an unrelated record.`
              : "Prefill context is invalid or stale. Quick entry was not silently linked to an unrelated record.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [proposalId, positionId]);

  useEffect(() => {
    if (!sessionId) {
      setRelatedSession({ status: "idle" });
      return;
    }
    let cancelled = false;
    setRelatedSession({ status: "loading" });
    void (async () => {
      try {
        const session = await api.strategies.getRunSession(sessionId);
        if (cancelled) return;
        setRelatedSession({ status: "ready", sessionId: session.session_id });
      } catch (err) {
        if (cancelled) return;
        setRelatedSession({
          status: "invalid",
          message:
            err instanceof Error
              ? `Validation session context is invalid or stale: ${err.message}. No related validation link is shown.`
              : "Validation session context is invalid or stale. No related validation link is shown.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const queue = useMemo(
    () => buildNeedsJournalingQueue(data?.closedPositions, data?.entries),
    [data?.closedPositions, data?.entries],
  );

  const entriesAvailable = Boolean(data?.entries.available);
  const positionsAvailable = Boolean(data?.closedPositions.available);
  const allFailed = Boolean(data) && !entriesAvailable && !positionsAvailable;
  const partialData = Boolean(data) && !allFailed && (!entriesAvailable || !positionsAvailable);

  const sourceStatuses = useMemo(() => {
    if (!data) return [];
    return [
      {
        name: "Journal entries",
        available: data.entries.available,
        error: data.entries.error,
        timestamp: data.entries.data?.items[0]?.created_at ?? null,
        required: true,
      },
      {
        name: "Closed positions",
        available: data.closedPositions.available,
        error: data.closedPositions.error,
        timestamp:
          data.closedPositions.data?.items[0]?.closed_at ??
          data.closedPositions.data?.items[0]?.opened_at ??
          null,
        required: true,
      },
    ];
  }, [data]);

  const freshnessSources = sourceStatuses.map((source) => ({
    name: source.name,
    available: source.available,
    required: source.required ?? true,
    timestamp: source.timestamp,
  }));

  const highlightedEntryId = savedHighlightId ?? context.entryId;
  const staleEntryMessage = useMemo(() => {
    if (!context.entryId) return null;
    if (!data) return null;
    if (!data.entries.available) {
      return "Entry deep-link cannot be verified while journal entries are unavailable.";
    }
    const found = data.entries.data?.items.some((entry) => entry.id === context.entryId);
    if (found) return null;
    const windowSize = data.entries.data?.limit ?? 50;
    return `Journal entry ${context.entryId} was not found in the most recent ${windowSize} journal entries. No unrelated entry was opened.`;
  }, [context.entryId, data]);

  const unsupportedTradeMessage = context.tradeId
    ? `Canonical journal trade deep link (trade_id=${context.tradeId}) is not resolved by this hub. No fabricated trade relationship was opened.`
    : null;

  const nextAction = useMemo(() => {
    const firstConfirmed = queue.items?.find((item) => item.verification === "confirmed");
    if (queue.countDefinitive && firstConfirmed) {
      return {
        label: "Journal next closed trade",
        href: firstConfirmed.href,
      };
    }
    return {
      label: "Start a new journal entry",
      href: "#journal-quick-entry-heading",
    };
  }, [queue]);

  async function handleAnalyze(entryId: string) {
    setDisciplineId(entryId);
    setDisciplineError(null);
    setBusy(true);
    try {
      const result = await api.journalDiscipline.analyze(entryId);
      setDiscipline(result);
    } catch (err) {
      setDiscipline(null);
      setDisciplineError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateLesson(entry: JournalEntry) {
    const lesson =
      discipline?.comparison.missed_runner?.recommended_lesson ??
      discipline?.comparison.stop_loss_analysis?.lesson;
    if (!lesson) return;
    setBusy(true);
    setMutationError(null);
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
    } catch (err) {
      setMutationError(
        err instanceof Error
          ? `Create lesson failed: ${err.message}`
          : "Create lesson failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(entryId: string) {
    setBusy(true);
    setMutationError(null);
    try {
      await api.journal.delete(entryId);
      await reload();
    } catch (err) {
      setMutationError(
        err instanceof Error
          ? `Delete entry failed: ${err.message}`
          : "Delete entry failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) {
    return <LoadingState label="Loading Journal hub…" />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={() => void reload()} />;
  }

  return (
    <JournalHubChrome
      title="Journal"
      description="What did I trade, what did I learn, and what still needs journaling? Paper journaling workflow."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
    >
      <div
        className="flex flex-wrap items-center gap-2"
        data-testid="journal-fastest-next-action"
      >
        <p className="text-sm text-text-secondary">Fastest next action:</p>
        <a
          href={nextAction.href}
          className="inline-flex h-10 items-center rounded-control border border-border bg-surface-1 px-4 text-sm font-medium text-text-primary hover:bg-surface-2"
        >
          {nextAction.label}
        </a>
        {partialData ? (
          <Button type="button" size="sm" variant="outline" onClick={() => void reload()}>
            Retry
          </Button>
        ) : null}
      </div>

      {allFailed ? (
        <ErrorState
          message="All Journal sources are unavailable. Counts are not shown as zero."
          onRetry={() => void reload()}
        />
      ) : null}

      {partialData ? (
        <div
          role="status"
          data-testid="journal-hub-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            {[
              !entriesAvailable ? "Journal entries" : null,
              !positionsAvailable ? "Closed positions" : null,
            ]
              .filter(Boolean)
              .join(", ")}{" "}
            unavailable. Showing available sections only.
          </p>
        </div>
      ) : null}

      <NeedsJournalingQueue queue={queue} onRetry={() => void reload()} />

      <RecentJournalEntries
        entries={entriesAvailable ? (data?.entries.data?.items ?? []) : null}
        available={entriesAvailable}
        error={data?.entries.error}
        highlightedEntryId={highlightedEntryId}
        staleEntryMessage={staleEntryMessage}
        mutationError={mutationError}
        onRetry={() => void reload()}
        busy={busy}
        disciplineId={disciplineId}
        discipline={discipline}
        disciplineError={disciplineError}
        onAnalyze={(entryId) => void handleAnalyze(entryId)}
        onCreateLesson={(entry) => void handleCreateLesson(entry)}
        onDelete={(entryId) => void handleDelete(entryId)}
      />

      <JournalQuickEntry
        context={context}
        prefill={prefill}
        relatedSession={relatedSession}
        unsupportedTradeMessage={unsupportedTradeMessage}
        onSaved={(entry) => {
          setSavedHighlightId(entry.id);
          void reload();
        }}
      />

      <JournalSourceAvailability
        sources={sourceStatuses}
        onRetry={() => void reload()}
        limitations={[
          ...(queue.coverageMessage ? [queue.coverageMessage] : []),
          ...queue.limitations.filter((item) => item !== queue.coverageMessage),
          "Needs-journaling uses closed positions (status=closed) and linked_position_id on loaded journal entries only.",
          "Validation session query context can show a related link when verified, but is not persisted on journal entries.",
          "Canonical JournalTrade detail routes are out of scope for this hub.",
        ]}
      />
    </JournalHubChrome>
  );
}
