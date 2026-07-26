import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WorkflowEmptyState } from "@/components/workflows/WorkflowEmptyState";
import type { ValidationAttentionItem } from "@/components/validate/types";

type ValidationAttentionQueueProps = {
  items: ValidationAttentionItem[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  partialData?: boolean;
  unavailableSources?: string[];
};

export function ValidationAttentionQueue({
  items,
  loading = false,
  error = null,
  onRetry,
  partialData = false,
  unavailableSources = [],
}: ValidationAttentionQueueProps) {
  if (loading) {
    return (
      <section aria-labelledby="validation-attention-heading" data-testid="validation-attention-queue">
        <h2 id="validation-attention-heading" className="text-lg font-semibold text-text-primary">
          Items requiring attention
        </h2>
        <p className="mt-2 text-sm text-text-muted" role="status">
          Loading attention items…
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-labelledby="validation-attention-heading" data-testid="validation-attention-queue">
        <h2 id="validation-attention-heading" className="text-lg font-semibold text-text-primary">
          Items requiring attention
        </h2>
        <div className="mt-3">
          <WorkflowEmptyState
            title="Attention items unavailable"
            description={error}
            actionLabel={onRetry ? "Retry" : undefined}
            onAction={onRetry}
            tone="error"
          />
        </div>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="validation-attention-heading"
      data-testid="validation-attention-queue"
      className="space-y-3"
    >
      <div>
        <h2 id="validation-attention-heading" className="text-lg font-semibold text-text-primary">
          Items requiring attention
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Explicit next actions from available Validate sources. No automatic promotion or execution.
        </p>
      </div>

      {partialData ? (
        <div
          role="status"
          data-testid="validation-attention-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            Some Validate sources failed. Attention items reflect available sources only.
          </p>
          {unavailableSources.length ? (
            <p className="mt-1" data-testid="validation-attention-unavailable">
              Unavailable: {unavailableSources.join(", ")}.
            </p>
          ) : null}
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {items.length === 0 ? (
        <WorkflowEmptyState
          title="Nothing needs Validate attention"
          description={
            partialData
              ? "No attention items from the sources that are currently available."
              : "No ready drafts, reviewing candidates, incomplete plans, or active sessions."
          }
        />
      ) : (
        <ul className="space-y-2" data-testid="validation-attention-list">
          {items.map((item) => (
            <li key={item.id}>
              <article
                data-testid={`validation-attention-${item.id}`}
                className="rounded-control border border-border-subtle bg-surface-0/40 px-4 py-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-text-primary">{item.title}</p>
                    <p className="mt-1 text-sm text-text-secondary">{item.detail}</p>
                  </div>
                  <Badge variant={item.urgency === "high" ? "warning" : "muted"}>
                    {item.urgency} · {item.stageId.replaceAll("_", " ")}
                  </Badge>
                </div>
                <Link
                  href={item.href}
                  className="mt-2 inline-flex min-h-11 items-center text-sm text-text-primary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  Open next action
                </Link>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
