import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FreshnessPill } from "@/components/ui/freshness-pill";
import { cn } from "@/lib/utils";
import type { InboxSignalModel } from "@/components/workflows/types";

const SOURCE_LABELS: Record<InboxSignalModel["source"], string> = {
  tradingview: "TradingView",
  alert: "Alert",
  setup_review: "Setup review",
  watcher: "Watcher",
  market_watch: "Market watch",
  orchestration: "Orchestration",
};

type SignalSummaryCardProps = {
  signal: InboxSignalModel;
  selected?: boolean;
  onSelect?: (signal: InboxSignalModel) => void;
  onReviewEvidence?: (signal: InboxSignalModel) => void;
  onCreateDraft?: (signal: InboxSignalModel) => void;
  onPlanTrade?: (signal: InboxSignalModel) => void;
  onDismissWithReason?: (signal: InboxSignalModel) => void;
  onHideForSession?: (signal: InboxSignalModel) => void;
  compactActions?: boolean;
};

export function SignalSummaryCard({
  signal,
  selected = false,
  onSelect,
  onReviewEvidence,
  onCreateDraft,
  onPlanTrade,
  onDismissWithReason,
  onHideForSession,
  compactActions = false,
}: SignalSummaryCardProps) {
  return (
    <article
      data-testid={`signal-summary-${signal.id}`}
      className={cn(
        "rounded-control border px-4 py-3 text-left transition",
        selected
          ? "border-info-border bg-info-muted"
          : "border-border-subtle bg-surface-0/40 hover:border-border",
      )}
    >
      <button
        type="button"
        className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        onClick={() => onSelect?.(signal)}
        aria-pressed={selected}
        aria-label={`Select signal ${signal.title}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-text-primary">{signal.title}</p>
            <p className="mt-0.5 text-sm text-text-secondary">{signal.summary}</p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="muted">{SOURCE_LABELS[signal.source]}</Badge>
            <Badge variant="muted">{signal.reviewStatus.replaceAll("_", " ")}</Badge>
            <FreshnessPill state={signal.freshness} ageLabel={signal.freshnessLabel} />
          </div>
        </div>
        <dl className="mt-2 grid grid-cols-2 gap-2 text-caption text-text-muted sm:grid-cols-3">
          <div>
            <dt className="sr-only">Confidence</dt>
            <dd>
              Confidence:{" "}
              {signal.confidence != null ? signal.confidence.toFixed(2) : "unavailable"}
            </dd>
          </div>
          <div className="col-span-1 sm:col-span-2">
            <dt className="sr-only">Provenance</dt>
            <dd className="truncate">{signal.provenance}</dd>
          </div>
        </dl>
        <p className="mt-2 text-caption text-text-secondary">Next: {signal.nextAction}</p>
      </button>

      <div
        className={cn(
          "mt-3 flex flex-wrap gap-2",
          compactActions && "flex-col sm:flex-row",
        )}
      >
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => onReviewEvidence?.(signal)}
        >
          Review evidence
        </Button>
        {signal.canCreateDraft ? (
          <Button type="button" size="sm" variant="outline" onClick={() => onCreateDraft?.(signal)}>
            {signal.createActionLabel ?? "Create validation draft"}
          </Button>
        ) : null}
        {signal.canPlanTrade ? (
          <Button type="button" size="sm" variant="outline" onClick={() => onPlanTrade?.(signal)}>
            Plan trade
          </Button>
        ) : null}
        {signal.canDismissWithReason ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onDismissWithReason?.(signal)}
          >
            Dismiss with reason
          </Button>
        ) : null}
        {signal.canHideForSession ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onHideForSession?.(signal)}
          >
            Hide for this session
          </Button>
        ) : null}
        {signal.detailHref ? (
          <Link
            href={signal.detailHref}
            className="inline-flex min-h-9 items-center text-caption text-text-secondary underline"
          >
            Open source
          </Link>
        ) : null}
      </div>
    </article>
  );
}
