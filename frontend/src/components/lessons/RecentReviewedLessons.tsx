import Link from "next/link";

import type { RecentReviewedResult } from "@/components/lessons/buildRecentReviewed";
import { LessonReviewCard } from "@/components/lessons/LessonReviewCard";
import { Button } from "@/components/ui/button";

type RecentReviewedLessonsProps = {
  result: RecentReviewedResult;
  highlightedLessonId?: string | null;
  onRetry?: () => void;
  sourceFilter: "all" | "coaching";
};

export function RecentReviewedLessons({
  result,
  highlightedLessonId,
  onRetry,
  sourceFilter,
}: RecentReviewedLessonsProps) {
  const showItems =
    (result.status === "available" ||
      result.status === "partial" ||
      result.status === "filtered_empty") &&
    result.items &&
    result.items.length > 0;

  return (
    <section
      aria-labelledby="lessons-recent-reviewed-heading"
      data-testid="lessons-recent-reviewed"
      className="space-y-3"
    >
      <div>
        <h2 id="lessons-recent-reviewed-heading" className="text-lg font-semibold text-text-primary">
          Recently reviewed lessons
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Accepted and rejected lessons from loaded review history. Sorted by review or creation
          time when available.
        </p>
      </div>

      {result.status === "loading" ? (
        <p className="text-sm text-text-muted" data-testid="lessons-recent-loading">
          Loading recently reviewed lessons…
        </p>
      ) : null}

      {result.status === "unavailable" ? (
        <div
          role="alert"
          data-testid="lessons-recent-unavailable"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p>{result.reasonUnavailable}</p>
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {result.status === "partial" ? (
        <div
          role="status"
          data-testid="lessons-recent-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial review history</p>
          <p className="mt-1">
            {[
              !result.acceptedAvailable ? "Accepted lessons" : null,
              !result.rejectedAvailable ? "Rejected lessons" : null,
            ]
              .filter(Boolean)
              .join(", ")}{" "}
            unavailable. Showing available history only.
          </p>
        </div>
      ) : null}

      {result.status === "empty" ? (
        <div
          role="status"
          data-testid="lessons-recent-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No accepted or rejected lessons in loaded history yet.
        </div>
      ) : null}

      {result.status === "filtered_empty" ? (
        <div
          role="status"
          data-testid="lessons-recent-filtered-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No coaching-source reviewed lessons in this view.
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
        <ul className="grid gap-3" data-testid="lessons-recent-list">
          {result.items!.map((lesson) => (
            <li key={lesson.id} data-testid={`lessons-recent-item-${lesson.id}`}>
              <LessonReviewCard lesson={lesson} highlighted={highlightedLessonId === lesson.id} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
