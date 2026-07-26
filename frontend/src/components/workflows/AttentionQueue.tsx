import { AttentionItem } from "@/components/workflows/AttentionItem";
import { WorkflowEmptyState } from "@/components/workflows/WorkflowEmptyState";
import {
  ATTENTION_SECTION_LABELS,
  type AttentionItemModel,
  type AttentionSectionId,
} from "@/components/workflows/types";
import { groupAttentionItems } from "@/components/workflows/buildAttentionItems";
import { Button } from "@/components/ui/button";

type AttentionQueueProps = {
  items: AttentionItemModel[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  partialData?: boolean;
  unavailableSources?: string[];
};

export function AttentionQueue({
  items,
  loading = false,
  error = null,
  onRetry,
  emptyTitle = "Nothing needs your attention",
  emptyDescription = "You are caught up. New signals, approvals, and lessons will appear here.",
  partialData = false,
  unavailableSources = [],
}: AttentionQueueProps) {
  if (loading) {
    return (
      <section aria-labelledby="attention-queue-heading" data-testid="attention-queue">
        <h2 id="attention-queue-heading" className="text-lg font-semibold text-text-primary">
          What needs my attention right now?
        </h2>
        <p className="mt-2 text-sm text-text-muted" role="status">
          Loading attention queue…
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-labelledby="attention-queue-heading" data-testid="attention-queue">
        <h2 id="attention-queue-heading" className="text-lg font-semibold text-text-primary">
          What needs my attention right now?
        </h2>
        <div className="mt-3" role="alert">
          <WorkflowEmptyState
            title="Attention queue unavailable"
            description={error}
            actionLabel={onRetry ? "Retry" : undefined}
            onAction={onRetry}
            tone="error"
          />
        </div>
      </section>
    );
  }

  const groups = groupAttentionItems(items);

  return (
    <section
      aria-labelledby="attention-queue-heading"
      data-testid="attention-queue"
      className="space-y-4"
    >
      <div>
        <h2 id="attention-queue-heading" className="text-lg font-semibold text-text-primary">
          What needs my attention right now?
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Prioritized actionable items from existing paper workflows. No live orders.
        </p>
      </div>

      {partialData ? (
        <div
          role="status"
          data-testid="attention-partial-data"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            Some sources failed. Showing attention items from available sources only.
          </p>
          {unavailableSources.length ? (
            <p className="mt-1" data-testid="attention-unavailable-sources">
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

      {groups.length === 0 ? (
        <WorkflowEmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className="space-y-5">
          {groups.map((group) => (
            <AttentionSection
              key={group.section}
              section={group.section}
              items={group.items}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function AttentionSection({
  section,
  items,
}: {
  section: AttentionSectionId;
  items: AttentionItemModel[];
}) {
  const headingId = `attention-section-${section}`;
  return (
    <section aria-labelledby={headingId} data-testid={`attention-section-${section}`}>
      <h3 id={headingId} className="mb-2 text-sm font-semibold text-text-secondary">
        {ATTENTION_SECTION_LABELS[section]}
      </h3>
      <ul className="space-y-2">{items.map((item) => <AttentionItem key={item.id} item={item} />)}</ul>
    </section>
  );
}
