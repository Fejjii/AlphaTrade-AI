"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { JournalHubChrome } from "@/components/journal/JournalHubChrome";
import {
  buildLessonsAttentionQueue,
  buildRecentReviewedLessons,
  LessonAcceptPanel,
  LessonReviewCard,
  LessonsAttentionQueue,
  LessonsSourceAvailability,
  latestLessonTimestamp,
  parseLessonsQuery,
  RecentReviewedLessons,
  type AcceptPath,
} from "@/components/lessons";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { LessonCandidate, PaginatedLessonCandidates, ProposedRuleUpdate } from "@/lib/api/types";

type LessonsHubData = {
  pending: SourceResult<PaginatedLessonCandidates>;
  accepted: SourceResult<PaginatedLessonCandidates>;
  rejected: SourceResult<PaginatedLessonCandidates>;
};

export default function LessonsPage() {
  const searchParams = useSearchParams();
  const context = useMemo(() => parseLessonsQuery(searchParams), [searchParams]);
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<LessonsHubData> => {
    const [pending, accepted, rejected] = await Promise.all([
      loadSource(api.lessons.listCandidates({ status: "pending_review" })),
      loadSource(api.lessons.listAccepted()),
      loadSource(api.lessons.listCandidates({ status: "rejected" })),
    ]);
    return { pending, accepted, rejected };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const [busyId, setBusyId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [mutationErrors, setMutationErrors] = useState<Record<string, string>>({});
  const [deepLinkLesson, setDeepLinkLesson] = useState<SourceResult<LessonCandidate> | null>(null);
  const [deepLinkLoading, setDeepLinkLoading] = useState(false);

  useEffect(() => {
    if (!context.candidateId) {
      setDeepLinkLesson(null);
      setDeepLinkLoading(false);
      return;
    }

    let cancelled = false;
    setDeepLinkLoading(true);
    void (async () => {
      const result = await loadSource(api.lessons.getCandidate(context.candidateId!));
      if (cancelled) return;
      setDeepLinkLesson(result);
      setDeepLinkLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [context.candidateId]);

  const attentionQueue = useMemo(
    () =>
      buildLessonsAttentionQueue({
        pending: data?.pending,
        loading,
        sourceFilter: context.sourceFilter,
      }),
    [context.sourceFilter, data?.pending, loading],
  );

  const recentReviewed = useMemo(
    () =>
      buildRecentReviewedLessons({
        accepted: data?.accepted,
        rejected: data?.rejected,
        loading,
        sourceFilter: context.sourceFilter,
      }),
    [context.sourceFilter, data?.accepted, data?.rejected, loading],
  );

  const pendingAvailable = Boolean(data?.pending.available);
  const acceptedAvailable = Boolean(data?.accepted.available);
  const rejectedAvailable = Boolean(data?.rejected.available);
  const allFailed =
    Boolean(data) && !pendingAvailable && !acceptedAvailable && !rejectedAvailable;
  const partialData =
    Boolean(data) &&
    !allFailed &&
    (!pendingAvailable || !acceptedAvailable || !rejectedAvailable);

  const sourceStatuses = useMemo(() => {
    if (!data) return [];
    return [
      {
        name: "Pending lessons",
        available: data.pending.available,
        error: data.pending.error,
        timestamp: latestLessonTimestamp(data.pending.data?.items ?? []),
        required: true,
      },
      {
        name: "Accepted lessons",
        available: data.accepted.available,
        error: data.accepted.error,
        timestamp: latestLessonTimestamp(data.accepted.data?.items ?? []),
        required: false,
      },
      {
        name: "Rejected lessons",
        available: data.rejected.available,
        error: data.rejected.error,
        timestamp: latestLessonTimestamp(data.rejected.data?.items ?? []),
        required: false,
      },
    ];
  }, [data]);

  const freshnessSources = sourceStatuses.map((source) => ({
    name: source.name,
    available: source.available,
    required: source.required ?? true,
    timestamp: source.timestamp,
  }));

  const loadedLessonIds = useMemo(() => {
    const ids = new Set<string>();
    for (const lesson of data?.pending.data?.items ?? []) ids.add(lesson.id);
    for (const lesson of data?.accepted.data?.items ?? []) ids.add(lesson.id);
    for (const lesson of data?.rejected.data?.items ?? []) ids.add(lesson.id);
    return ids;
  }, [data?.accepted.data?.items, data?.pending.data?.items, data?.rejected.data?.items]);

  const highlightedLessonId = useMemo(() => {
    if (!context.candidateId) return null;
    if (loadedLessonIds.has(context.candidateId)) return context.candidateId;
    if (deepLinkLesson?.available && deepLinkLesson.data?.id === context.candidateId) {
      return context.candidateId;
    }
    return null;
  }, [context.candidateId, deepLinkLesson, loadedLessonIds]);

  const staleCandidateMessage = useMemo(() => {
    if (!context.candidateId) return null;
    if (loading || deepLinkLoading) return null;
    if (highlightedLessonId) return null;
    if (deepLinkLesson && !deepLinkLesson.available) {
      return `Lesson candidate ${context.candidateId} could not be verified (${deepLinkLesson.error ?? "unavailable"}). No unrelated lesson was opened.`;
    }
    if (deepLinkLesson?.available && deepLinkLesson.data?.id !== context.candidateId) {
      return `Lesson candidate ${context.candidateId} did not match the loaded record. No unrelated lesson was opened.`;
    }
    return `Lesson candidate ${context.candidateId} was not found in loaded review queues. No unrelated lesson was opened.`;
  }, [context.candidateId, deepLinkLesson, deepLinkLoading, highlightedLessonId, loading]);

  const deepLinkOnlyLesson =
    highlightedLessonId &&
    context.candidateId &&
    !loadedLessonIds.has(context.candidateId) &&
    deepLinkLesson?.available
      ? deepLinkLesson.data
      : null;

  const handleAcceptSubmit = async (
    id: string,
    payload: {
      path: AcceptPath;
      reviewerNotes: string;
      ruleUpdate: ProposedRuleUpdate | null;
      strategyId: string | null;
    },
  ) => {
    setBusyId(id);
    setMutationErrors((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      await api.lessons.accept(id, {
        reviewer_notes: payload.reviewerNotes,
        accepted_rule_update: payload.ruleUpdate ?? undefined,
        attach_rule_to_strategy: payload.path === "attach_rule",
        create_strategy_version: payload.path === "create_version",
        related_strategy_id: payload.strategyId ?? undefined,
      });
      setAcceptingId(null);
      await reload();
    } catch (err) {
      throw err;
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (lesson: LessonCandidate) => {
    if (busyId) return;
    setBusyId(lesson.id);
    setMutationErrors((prev) => {
      const next = { ...prev };
      delete next[lesson.id];
      return next;
    });
    try {
      await api.lessons.reject(lesson.id, { reviewer_notes: notes[lesson.id] ?? "" });
      await reload();
    } catch (err) {
      setMutationErrors((prev) => ({
        ...prev,
        [lesson.id]: err instanceof Error ? err.message : "Reject failed",
      }));
    } finally {
      setBusyId(null);
    }
  };

  const nextAction = useMemo(() => {
    const firstPending = attentionQueue.items?.[0];
    if (firstPending) {
      return {
        label: "Review next pending lesson",
        href: `#lessons-attention-item-${firstPending.id}`,
      };
    }
    return {
      label: "Browse recently reviewed lessons",
      href: "#lessons-recent-reviewed-heading",
    };
  }, [attentionQueue.items]);

  if (loading && !data) {
    return <LoadingState label="Loading Lessons review hub…" />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={() => void reload()} />;
  }

  return (
    <JournalHubChrome
      title="Lessons"
      description="What lesson requires my attention, where did it come from, and what should I do with it? Paper review workflow."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="lessons-hub-page"
      activeHref="/lessons"
    >
      <div className="flex flex-wrap items-center gap-2" data-testid="lessons-fastest-next-action">
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

      <div
        className="flex flex-wrap items-center gap-2 text-xs"
        role="group"
        aria-label="Source filter"
        data-testid="lessons-source-filter"
      >
        <span className="text-zinc-500">Show:</span>
        <Link
          href="/lessons"
          data-testid="lessons-source-all"
          aria-current={context.sourceFilter === "all" ? "true" : undefined}
          className={
            context.sourceFilter === "all"
              ? "rounded bg-zinc-100 px-3 py-1 font-medium text-zinc-900"
              : "rounded border border-zinc-700 px-3 py-1 text-zinc-300"
          }
        >
          All sources
        </Link>
        <Link
          href="/lessons?source=coaching"
          data-testid="lessons-source-coaching"
          aria-current={context.sourceFilter === "coaching" ? "true" : undefined}
          className={
            context.sourceFilter === "coaching"
              ? "rounded bg-zinc-100 px-3 py-1 font-medium text-zinc-900"
              : "rounded border border-zinc-700 px-3 py-1 text-zinc-300"
          }
        >
          From coaching
        </Link>
        {context.sourceFilter === "coaching" ? (
          <Link href="/coaching" className="text-zinc-400 underline">
            Back to coaching
          </Link>
        ) : null}
      </div>

      {allFailed ? (
        <ErrorState
          message="All lesson sources are unavailable. Counts are not shown as zero."
          onRetry={() => void reload()}
        />
      ) : null}

      {partialData ? (
        <div
          role="status"
          data-testid="lessons-hub-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            {[
              !pendingAvailable ? "Pending lessons" : null,
              !acceptedAvailable ? "Accepted lessons" : null,
              !rejectedAvailable ? "Rejected lessons" : null,
            ]
              .filter(Boolean)
              .join(", ")}{" "}
            unavailable. Showing available sections only.
          </p>
        </div>
      ) : null}

      {staleCandidateMessage ? (
        <div
          role="alert"
          data-testid="lessons-candidate-stale"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {staleCandidateMessage}
        </div>
      ) : null}

      {deepLinkOnlyLesson && deepLinkOnlyLesson.status === "pending_review" ? (
        <section
          aria-labelledby="lessons-deeplink-heading"
          data-testid="lessons-deeplink-only"
          className="space-y-3"
        >
          <h2 id="lessons-deeplink-heading" className="text-lg font-semibold text-text-primary">
            Deep-linked lesson
          </h2>
          {acceptingId === deepLinkOnlyLesson.id ? (
            <LessonAcceptPanel
              lesson={deepLinkOnlyLesson}
              busy={busyId === deepLinkOnlyLesson.id}
              onAccept={(payload) => handleAcceptSubmit(deepLinkOnlyLesson.id, payload)}
              onCancel={() => setAcceptingId(null)}
            />
          ) : (
            <LessonReviewCard
              lesson={deepLinkOnlyLesson}
              highlighted
              busy={busyId === deepLinkOnlyLesson.id}
              mutationError={mutationErrors[deepLinkOnlyLesson.id] ?? null}
              reviewerNotes={notes[deepLinkOnlyLesson.id]}
              onReviewerNotesChange={(value: string) =>
                setNotes((prev) => ({ ...prev, [deepLinkOnlyLesson.id]: value }))
              }
              onAccept={() => setAcceptingId(deepLinkOnlyLesson.id)}
              onReject={() => void handleReject(deepLinkOnlyLesson)}
            />
          )}
        </section>
      ) : null}

      <LessonsAttentionQueue
        queue={attentionQueue}
        highlightedLessonId={highlightedLessonId}
        acceptingId={acceptingId}
        busyId={busyId}
        mutationErrors={mutationErrors}
        notes={notes}
        onNotesChange={(lessonId, value) => setNotes((prev) => ({ ...prev, [lessonId]: value }))}
        onAccept={(lesson) => setAcceptingId(lesson.id)}
        onAcceptSubmit={handleAcceptSubmit}
        onAcceptCancel={() => setAcceptingId(null)}
        onReject={(lesson) => void handleReject(lesson)}
        onRetry={() => void reload()}
        sourceFilter={context.sourceFilter}
      />

      <RecentReviewedLessons
        result={recentReviewed}
        highlightedLessonId={highlightedLessonId}
        onRetry={() => void reload()}
        sourceFilter={context.sourceFilter}
      />

      <LessonsSourceAvailability
        sources={sourceStatuses}
        onRetry={() => void reload()}
        limitations={[
          "Attention queue includes pending_review status only — not accepted or rejected history.",
          "Journal links require related_journal_entry_id; related_trade_id is never treated as a journal-entry link.",
          "Validation session links use coaching analysis_metadata.source_session_ids when present.",
          "Deep link ?candidate= verifies the ID before highlight; invalid IDs do not open unrelated lessons.",
          posture.paperConfirmed
            ? "Runtime posture verified as paper-only for this session."
            : "Paper posture is not fully verified — treat execution labels as conservative guidance only.",
        ]}
      />
    </JournalHubChrome>
  );
}
