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
  const showItems =
    (queue.queueStatus === "available" || queue.queueStatus === "filtered_empty") &&
    queue.items &&
    queue.items.length > 0;

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
        {queue.countDefinitive && queue.sourceAvailable ? (
          <p className="text-sm text-text-secondary" data-testid="lessons-attention-count">
            {queue.items?.length ?? 0} pending
          </p>
        ) : (
          <p className="text-sm text-text-muted" data-testid="lessons-attention-count-unavailable">
            Count unavailable
          </p>
        )}
      </div>

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

      {showItems ? (
        <ul className="grid gap-3" data-testid="lessons-attention-list">
          {queue.items!.map((lesson) => (
            <li key={lesson.id} data-testid={`lessons-attention-item-${lesson.id}`}>
              {acceptingId === lesson.id && onAcceptSubmit && onAcceptCancel ? (
                <LessonAcceptPanel
                  lesson={lesson}
                  busy={busyId === lesson.id}
                  onAccept={(payload) => onAcceptSubmit(lesson.id, payload)}
                  onCancel={onAcceptCancel}
                />
              ) : (
                <LessonReviewCard
                  lesson={lesson}
                  highlighted={highlightedLessonId === lesson.id}
                  busy={busyId === lesson.id}
                  mutationError={mutationErrors[lesson.id] ?? null}
                  reviewerNotes={notes[lesson.id]}
                  onReviewerNotesChange={
                    onNotesChange ? (value) => onNotesChange(lesson.id, value) : undefined
                  }
                  onAccept={onAccept ? () => onAccept(lesson) : undefined}
                  onReject={onReject ? () => onReject(lesson) : undefined}
                />
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
