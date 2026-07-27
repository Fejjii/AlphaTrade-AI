"use client";

import Link from "next/link";

import {
  formatLessonTimestamp,
  formatMistakeType,
  formatSourceType,
  nextActionForLesson,
  resolveLessonRelationships,
} from "@/components/lessons/lessonDisplay";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LessonCandidate } from "@/lib/api/types";

type LessonReviewCardProps = {
  lesson: LessonCandidate;
  highlighted?: boolean;
  busy?: boolean;
  mutationLocked?: boolean;
  deepLinkNotice?: boolean;
  mutationError?: string | null;
  onAccept?: () => void;
  onReject?: () => void;
  reviewerNotes?: string;
  onReviewerNotesChange?: (value: string) => void;
};

export function formatLessonConfidence(confidence: string | null | undefined): string {
  return confidence != null ? `confidence ${confidence}` : "confidence unavailable";
}

export function LessonReviewCard({
  lesson,
  highlighted = false,
  busy = false,
  mutationLocked = false,
  deepLinkNotice = false,
  mutationError = null,
  onAccept,
  onReject,
  reviewerNotes,
  onReviewerNotesChange,
}: LessonReviewCardProps) {
  const isPending = lesson.status === "pending_review";
  const isCoaching = lesson.source_type === "coaching";
  const nextAction = nextActionForLesson(lesson);
  const relationships = resolveLessonRelationships(lesson);
  const createdLabel = formatLessonTimestamp(lesson.created_at);
  const reviewedLabel = formatLessonTimestamp(lesson.reviewed_at);
  const showReviewerNotes = isPending && onReviewerNotesChange;
  const controlsDisabled = mutationLocked;

  return (
    <Card
      data-testid="lesson-review-card"
      data-lesson-id={lesson.id}
      data-highlighted={highlighted ? "true" : "false"}
      className={highlighted ? "ring-2 ring-warning-border" : undefined}
    >
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base capitalize">{formatMistakeType(lesson.mistake_type)}</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            {isCoaching ? (
              <Badge variant="info" data-testid="lesson-source-coaching">
                Coaching
              </Badge>
            ) : (
              <span className="text-xs text-zinc-500" data-testid="lesson-source-label">
                {formatSourceType(lesson.source_type)}
              </span>
            )}
            <Badge variant="muted" data-testid="lesson-status-badge">
              {lesson.status.replace(/_/g, " ")}
            </Badge>
            <Badge variant="muted">{lesson.severity}</Badge>
          </div>
        </div>
        <p className="text-xs text-zinc-500" data-testid="lesson-confidence">
          {formatLessonConfidence(lesson.confidence)}
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        {deepLinkNotice ? (
          <p
            className="rounded border border-amber-700/50 bg-amber-950/30 p-2 text-xs text-amber-100"
            data-testid="lesson-deeplink-notice"
          >
            Loaded directly because this lesson is outside the current paginated queues.
          </p>
        ) : null}
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Lesson text</p>
          <p data-testid="lesson-text">{lesson.lesson_text}</p>
        </div>

        <div data-testid="lesson-source-context">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Source context</p>
          <p className="text-zinc-400">
            Source type: <span className="text-zinc-200">{formatSourceType(lesson.source_type)}</span>
          </p>
          {lesson.source_id ? (
            <p className="text-zinc-400">
              Source reference: <span className="font-mono text-zinc-300">{lesson.source_id}</span>
            </p>
          ) : (
            <p className="text-zinc-500">Source reference unavailable</p>
          )}
        </div>

        <div data-testid="lesson-relationships">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Related context</p>
          <ul className="space-y-1">
            {relationships.map((relationship) => (
              <li key={`${lesson.id}-${relationship.kind}`} className="text-zinc-400">
                {relationship.label}:{" "}
                {relationship.href ? (
                  <Link href={relationship.href} className="underline">
                    Open
                  </Link>
                ) : (
                  <span className="text-zinc-500" data-testid={`lesson-relationship-unavailable-${relationship.kind}`}>
                    {relationship.unavailableReason ?? "Unavailable"}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div data-testid="lesson-next-action">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Current status and next action
          </p>
          <p className="font-medium text-zinc-200">{nextAction.label}</p>
          <p className="text-zinc-400">{nextAction.description}</p>
        </div>

        <div className="text-xs text-zinc-500" data-testid="lesson-timestamps">
          <p>
            Created: {createdLabel ?? "timestamp unavailable"}
            {reviewedLabel ? ` · Reviewed: ${reviewedLabel}` : ""}
          </p>
        </div>

        {lesson.proposed_rule_update?.summary ? (
          <div className="rounded border border-zinc-800 p-2 text-zinc-400">
            <p className="font-medium text-zinc-200">Proposed rule update</p>
            <p>{lesson.proposed_rule_update.summary}</p>
          </div>
        ) : null}

        {lesson.reviewer_notes && !showReviewerNotes ? (
          <p className="text-xs text-zinc-500">Reviewer notes: {lesson.reviewer_notes}</p>
        ) : null}

        {showReviewerNotes ? (
          <label className="block text-xs text-zinc-500">
            Reviewer notes (optional)
            <textarea
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 p-2 text-sm"
              rows={2}
              value={reviewerNotes ?? ""}
              onChange={(event) => onReviewerNotesChange(event.target.value)}
              data-testid={`reviewer-notes-${lesson.id}`}
            />
          </label>
        ) : null}

        {mutationError ? (
          <p className="text-sm text-red-300" role="alert" data-testid="lesson-mutation-error">
            {mutationError}
          </p>
        ) : null}

        {isPending && onAccept && onReject ? (
          <div className="flex flex-wrap gap-2" data-testid="lesson-actions">
            <button
              type="button"
              disabled={controlsDisabled}
              aria-busy={busy}
              className="inline-flex h-10 min-w-[8rem] items-center justify-center rounded-control bg-emerald-700/80 px-4 text-sm font-medium text-white disabled:opacity-50"
              data-testid="accept-lesson-btn"
              onClick={() => {
                if (controlsDisabled) return;
                onAccept();
              }}
            >
              {busy ? "Working…" : "Accept"}
            </button>
            <button
              type="button"
              disabled={controlsDisabled}
              aria-busy={busy}
              className="inline-flex h-10 min-w-[8rem] items-center justify-center rounded-control border border-zinc-600 px-4 text-sm disabled:opacity-50"
              data-testid="reject-lesson-btn"
              onClick={() => {
                if (controlsDisabled) return;
                onReject();
              }}
            >
              {busy ? "Working…" : "Reject"}
            </button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
