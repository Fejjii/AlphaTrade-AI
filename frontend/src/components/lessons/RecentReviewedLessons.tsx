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
      result.status === "partial_failure" ||
      result.status === "partial_truncated" ||
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

      {result.coverageMessage ? (
        <div
          role="status"
          data-testid="lessons-recent-coverage"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {result.coverageMessage}
        </div>
      ) : null}

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

      {result.status === "partial_failure" ? (
        <div
          role="status"
          data-testid="lessons-recent-partial-failure"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial review history — source failure</p>
          <p className="mt-1">
            {[
              result.acceptedFailed ? "Accepted lessons unavailable" : null,
              result.rejectedFailed ? "Rejected lessons unavailable" : null,
            ]
              .filter(Boolean)
              .join("; ")}
            . Showing available history only.
          </p>
        </div>
      ) : null}

      {result.status === "partial_truncated" ? (
        <div
          role="status"
          data-testid="lessons-recent-partial-truncated"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial review history — incomplete coverage</p>
          <p className="mt-1">
            Loaded history may not represent all reviewed lessons. See coverage details above.
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

      {result.status === "truncated_empty" ? (
        <div
          role="status"
          data-testid="lessons-recent-truncated-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No reviewed lessons appear in the loaded page, but history coverage is incomplete. An
          empty history cannot be confirmed.
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
          {result.items!.map((item) => (
            <li key={item.id} data-testid={`lessons-recent-item-${item.id}`}>
              <LessonReviewCard lesson={item} highlighted={highlightedLessonId === item.id} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
