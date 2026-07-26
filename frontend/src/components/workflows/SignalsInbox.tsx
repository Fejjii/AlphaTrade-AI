"use client";

import { useMemo, useState } from "react";

import { SignalSummaryCard } from "@/components/workflows/SignalSummaryCard";
import { WorkflowEmptyState } from "@/components/workflows/WorkflowEmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { InboxSignalModel } from "@/components/workflows/types";

const DISMISS_REASONS = [
  "Duplicate",
  "Low confidence",
  "Stale setup",
  "Outside playbook",
  "Already planned",
  "Other",
] as const;

type SignalsInboxProps = {
  signals: InboxSignalModel[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  selectedId?: string | null;
  onSelect?: (signal: InboxSignalModel) => void;
  onReviewEvidence?: (signal: InboxSignalModel) => void;
  onCreateDraft?: (signal: InboxSignalModel) => void;
  onPlanTrade?: (signal: InboxSignalModel) => void;
  onDismiss?: (signal: InboxSignalModel, reason: string) => void;
  onHideForSession?: (signal: InboxSignalModel) => void;
  detail?: React.ReactNode;
  partialData?: boolean;
  unavailableSources?: string[];
  emptyTitle?: string;
  emptyDescription?: string;
  sourceAvailabilitySummary?: React.ReactNode;
};

export function SignalsInbox({
  signals,
  loading = false,
  error = null,
  onRetry,
  selectedId = null,
  onSelect,
  onReviewEvidence,
  onCreateDraft,
  onPlanTrade,
  onDismiss,
  onHideForSession,
  detail,
  partialData = false,
  unavailableSources = [],
  emptyTitle = "No signals need review",
  emptyDescription = "Validated TradingView signals, unread alerts, and setup reviews will appear here.",
  sourceAvailabilitySummary,
}: SignalsInboxProps) {
  const [dismissingId, setDismissingId] = useState<string | null>(null);
  const [dismissReason, setDismissReason] = useState<string>(DISMISS_REASONS[0]);
  const [customReason, setCustomReason] = useState("");

  const selected = useMemo(
    () => signals.find((signal) => signal.id === selectedId) ?? null,
    [signals, selectedId],
  );

  if (loading) {
    return (
      <section aria-labelledby="signals-inbox-heading" data-testid="signals-inbox">
        <h2 id="signals-inbox-heading" className="text-lg font-semibold text-text-primary">
          Signals inbox
        </h2>
        <p className="mt-2 text-sm text-text-muted" role="status">
          Loading signals…
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-labelledby="signals-inbox-heading" data-testid="signals-inbox">
        <h2 id="signals-inbox-heading" className="text-lg font-semibold text-text-primary">
          Signals inbox
        </h2>
        <div className="mt-3">
          <WorkflowEmptyState
            title="Signals unavailable"
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
      aria-labelledby="signals-inbox-heading"
      data-testid="signals-inbox"
      className="space-y-4"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="signals-inbox-heading" className="text-lg font-semibold text-text-primary">
            Signals inbox
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            TradingView, alerts, watcher, and setup review — paper triage only.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {partialData ? (
            <Badge variant="warning" data-testid="signals-partial-data">
              Partial inbox data
            </Badge>
          ) : null}
          <Badge variant="muted">{signals.length} visible</Badge>
        </div>
      </div>

      {sourceAvailabilitySummary}

      {partialData && unavailableSources.length ? (
        <div
          role="status"
          data-testid="signals-unavailable-sources"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          Unavailable sources: {unavailableSources.join(", ")}.
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" className="ml-3" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {signals.length === 0 ? (
        <WorkflowEmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className="grid gap-section lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <div className="space-y-3" role="list" aria-label="Signal list">
            {signals.map((signal) => (
              <div key={signal.id} role="listitem">
                <SignalSummaryCard
                  signal={signal}
                  selected={selected?.id === signal.id}
                  onSelect={onSelect}
                  onReviewEvidence={onReviewEvidence}
                  onCreateDraft={onCreateDraft}
                  onPlanTrade={onPlanTrade}
                  onHideForSession={onHideForSession}
                  onDismissWithReason={(item) => {
                    setDismissingId(item.id);
                    setDismissReason(DISMISS_REASONS[0]);
                    setCustomReason("");
                  }}
                  compactActions
                />
                {dismissingId === signal.id ? (
                  <div
                    className="mt-2 rounded-control border border-border-subtle bg-surface-1 p-3"
                    data-testid={`signal-dismiss-${signal.id}`}
                  >
                    <p className="text-sm font-medium text-text-primary">Dismiss with reason</p>
                    <p className="mt-1 text-caption text-text-muted">
                      Reason is persisted through the existing review/alert API.
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {DISMISS_REASONS.map((reason) => (
                        <Button
                          key={reason}
                          type="button"
                          size="sm"
                          variant={dismissReason === reason ? "secondary" : "outline"}
                          onClick={() => setDismissReason(reason)}
                        >
                          {reason}
                        </Button>
                      ))}
                    </div>
                    {dismissReason === "Other" ? (
                      <Input
                        className="mt-2"
                        value={customReason}
                        onChange={(event) => setCustomReason(event.target.value)}
                        aria-label="Custom dismiss reason"
                        placeholder="Reason"
                      />
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => {
                          const reason =
                            dismissReason === "Other"
                              ? customReason.trim() || "Other"
                              : dismissReason;
                          onDismiss?.(signal, reason);
                          setDismissingId(null);
                        }}
                      >
                        Confirm dismiss
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setDismissingId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          <div data-testid="signals-inbox-detail">{detail}</div>
        </div>
      )}
    </section>
  );
}
