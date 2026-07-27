import Link from "next/link";

import type { NeedsJournalingResult } from "@/components/journal/buildNeedsJournaling";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";

type NeedsJournalingQueueProps = {
  queue: NeedsJournalingResult;
  onRetry?: () => void;
};

export function NeedsJournalingQueue({ queue, onRetry }: NeedsJournalingQueueProps) {
  const showItems =
    (queue.queueStatus === "available" ||
      queue.queueStatus === "limited" ||
      queue.queueStatus === "unverified") &&
    queue.items &&
    queue.items.length > 0;

  return (
    <section
      aria-labelledby="needs-journaling-heading"
      data-testid="needs-journaling-queue"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2
            id="needs-journaling-heading"
            className="text-lg font-semibold text-text-primary"
          >
            Needs journaling
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Closed paper positions without a linked journal entry in the loaded page.
          </p>
        </div>
        {queue.countDefinitive ? (
          <p className="text-sm text-text-secondary" data-testid="needs-journaling-count">
            {queue.items?.length ?? 0} need journaling
          </p>
        ) : queue.countAvailable && !queue.countDefinitive ? (
          <p
            className="text-sm text-text-secondary"
            data-testid="needs-journaling-count-loaded"
          >
            {queue.items?.length ?? 0} need journaling (loaded coverage only)
          </p>
        ) : (
          <p className="text-sm text-text-muted" data-testid="needs-journaling-count-unavailable">
            Count unavailable
          </p>
        )}
      </div>

      {queue.coverageMessage ? (
        <div
          role="status"
          data-testid="needs-journaling-coverage"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {queue.coverageMessage}
        </div>
      ) : null}

      {queue.limitations.length > 0 && !queue.coverageMessage ? (
        <div
          role="status"
          data-testid="needs-journaling-limitations"
          className="rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary"
        >
          <ul className="list-disc space-y-1 pl-5">
            {queue.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {queue.queueStatus === "loading" ? (
        <p className="text-sm text-text-muted" data-testid="needs-journaling-loading">
          Loading needs-journaling queue…
        </p>
      ) : null}

      {queue.queueStatus === "unavailable" ? (
        <div
          role="alert"
          data-testid="needs-journaling-unavailable"
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
          data-testid="needs-journaling-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          No closed positions currently need journaling.
        </div>
      ) : null}

      {(queue.queueStatus === "limited" || queue.queueStatus === "unverified") &&
      queue.items &&
      queue.items.length === 0 ? (
        <div
          role="status"
          data-testid="needs-journaling-unverified-empty"
          className="rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
        >
          Loaded closed positions appear journaled, but full coverage is unavailable so an
          all-clear cannot be confirmed.
        </div>
      ) : null}

      {showItems ? (
        <ul className="grid gap-2" data-testid="needs-journaling-list">
          {queue.items!.map((item) => (
            <li
              key={item.positionId}
              className="flex flex-col gap-2 rounded-control border border-border-subtle px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              data-testid={`needs-journaling-item-${item.positionId}`}
              data-verification={item.verification}
            >
              <div className="min-w-0 space-y-1">
                <p className="font-medium text-text-primary">
                  {item.symbol} · {item.direction.toUpperCase()} · {item.status}
                </p>
                {item.verification === "unverified" ? (
                  <p
                    className="text-caption text-warning"
                    data-testid={`needs-journaling-unverified-label-${item.positionId}`}
                  >
                    Possibly needs journaling — full journal coverage unavailable
                  </p>
                ) : null}
                <p className="text-caption text-text-muted">
                  Closed:{" "}
                  {item.closedAt && Number.isFinite(Date.parse(item.closedAt))
                    ? formatDate(item.closedAt)
                    : "timestamp unavailable"}
                  {item.realizedPnl != null && item.realizedPnl !== ""
                    ? ` · Realized P&L: ${item.realizedPnl}`
                    : ""}
                </p>
              </div>
              {item.verification === "confirmed" ? (
                <Link
                  href={item.href}
                  className="inline-flex h-10 min-w-[8rem] items-center justify-center rounded-control border border-border bg-surface-1 px-4 text-sm font-medium text-text-primary hover:bg-surface-2"
                  data-testid={`needs-journaling-action-${item.positionId}`}
                >
                  Journal this trade
                </Link>
              ) : (
                <Link
                  href={item.href}
                  className="inline-flex h-10 min-w-[8rem] items-center justify-center rounded-control border border-border bg-surface-1 px-4 text-sm font-medium text-text-secondary hover:bg-surface-2"
                  data-testid={`needs-journaling-possible-action-${item.positionId}`}
                >
                  Review for journaling
                </Link>
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
