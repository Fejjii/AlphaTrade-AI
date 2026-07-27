import Link from "next/link";

import type { AttentionQueueResult } from "@/components/lessons/buildLessonsAttention";
import {
  LessonAcceptPanel,
  type AcceptPath,
} from "@/components/lessons/LessonAcceptPanel";
import { LessonReviewCard } from "@/components/lessons/LessonReviewCard";
import { Button } from "@/components/ui/button";
import type { LessonCandidate, ProposedRuleUpdate } from "@/lib/api/types";

type LessonsAttentionQueueProps = {
  queue: AttentionQueueResult;
  highlightedLessonId?: string | null;
  acceptingId?: string | null;
  busyId?: string | null;
  mutationLocked?: boolean;
  mutationErrors?: Record<string, string>;
  notes?: Record<string, string>;
  onNotesChange?: (lessonId: string, value: string) => void;
  onAccept?: (lesson: LessonCandidate) => void;
  onAcceptSubmit?: (
    lessonId: string,
    payload: {
      path: AcceptPath;
      reviewerNotes: string;
      ruleUpdate: ProposedRuleUpdate | null;
      strategyId: string | null;
    },
  ) => Promise<void>;
  onAcceptCancel?: () => void;
  onReject?: (lesson: LessonCandidate) => void;
  onRetry?: () => void;
  sourceFilter: "all" | "coaching";
};

export function LessonsAttentionQueue({
  queue,
  highlightedLessonId,
  acceptingId,
  busyId,
  mutationLocked = false,
  mutationErrors = {},
  notes = {},
  onNotesChange,
  onAccept,
  onAcceptSubmit,
  onAcceptCancel,
  onReject,
  onRetry,
  sourceFilter,
}: LessonsAttentionQueueProps) {
  const showItems = queue.queueStatus === "available" && queue.items && queue.items.length > 0;

  return (
    <section
      aria-labelledby="lessons-attention-heading"
      data-testid="lessons-attention-queue"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="lessons-attention-heading" className="text-lg font-semibold text-text-primary">
            Lessons requiring attention
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Pending observations with status pending_review only. These are not accepted trading
            rules.
          </p>
        </div>
        {!queue.sourceAvailable ? (
          <p className="text-sm text-text-muted" data-testid="lessons-attention-count-unavailable">
            Count unavailable
          </p>
        ) : queue.countDefinitive ? (
          <p className="text-sm text-text-secondary" data-testid="lessons-attention-count">
            {queue.items?.length ?? 0} pending
          </p>
        ) : queue.countAvailable ? (
          <p
            className="text-sm text-text-secondary"
            data-testid="lessons-attention-count-loaded"
          >
            {queue.items?.length ?? 0} of {queue.totalPendingCount} pending lessons loaded
          </p>
        ) : (
          <p className="text-sm text-text-muted" data-testid="lessons-attention-count-unavailable">
            Count unavailable
          </p>
        )}
      </div>

      {queue.coverageMessage ? (
        <div
          role="status"
          data-testid="lessons-attention-coverage"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {queue.coverageMessage}
        </div>
      ) : null}

      {queue.queueStatus === "loading" ? (
        <p className="text-sm text-text-muted" data-testid="lessons-attention-loading">
          Loading lessons requiring attention…
        </p>
      ) : null}

      {queue.queueStatus === "unavailable" ? (
        <div
          role="alert"
          data-testid="lessons-attention-unavailable"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p>{queue.reasonUnavailable}</p>
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {queue.queueStatus === "empty" ? (
        <div
          role="status"
          data-testid="lessons-attention-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No pending lessons currently require review.
        </div>
      ) : null}

      {queue.queueStatus === "filtered_empty" ? (
        <div
          role="status"
          data-testid="lessons-attention-filtered-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No coaching-source pending lessons in this view.
          {sourceFilter === "coaching" ? (
            <>
              {" "}
              <Link href="/coaching" className="underline">
                Back to coaching
              </Link>
            </>
          ) : null}
        </div>
      ) : null}

      {queue.queueStatus === "truncated_empty" ? (
        <div
          role="status"
          data-testid="lessons-attention-truncated-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No pending lessons appear in the loaded page, but {queue.totalPendingCount} pending
          lesson(s) exist in total. Coverage is incomplete — an all-clear cannot be confirmed.
        </div>
      ) : null}

      {queue.queueStatus === "truncated_filtered_empty" ? (
        <div
          role="status"
          data-testid="lessons-attention-truncated-filtered-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No coaching-source pending lessons were found in the loaded page. Additional pending
          lessons may exist outside this page.
          {sourceFilter === "coaching" ? (
            <>
              {" "}
              <Link href="/coaching" className="underline">
                Back to coaching
              </Link>
            </>
          ) : null}
        </div>
      ) : null}

      {showItems ? (
        <ul className="grid gap-3" data-testid="lessons-attention-list">
          {queue.items!.map((item) => (
            <li key={item.id} data-testid={`lessons-attention-item-${item.id}`}>
              {acceptingId === item.id && onAcceptSubmit && onAcceptCancel ? (
                <LessonAcceptPanel
                  lesson={item}
                  busy={busyId === item.id}
                  onAccept={(payload) => onAcceptSubmit(item.id, payload)}
                  onCancel={onAcceptCancel}
                />
              ) : (
                <LessonReviewCard
                  lesson={item}
                  highlighted={highlightedLessonId === item.id}
                  busy={busyId === item.id}
                  mutationLocked={mutationLocked}
                  mutationError={mutationErrors[item.id] ?? null}
                  reviewerNotes={notes[item.id]}
                  onReviewerNotesChange={
                    onNotesChange ? (value) => onNotesChange(item.id, value) : undefined
                  }
                  onAccept={onAccept ? () => onAccept(item) : undefined}
                  onReject={onReject ? () => onReject(item) : undefined}
                />
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
