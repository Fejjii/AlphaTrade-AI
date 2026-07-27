"use client";

import type { SourceResult } from "@/components/workflows";
import type { SetupEvidenceResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { formatMonetary } from "./format";

export type SetupEvidencePanelProps = {
  evidence: SourceResult<SetupEvidenceResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  /** Only setup_id / strategy_id filters sent to GET /journal/setup-evidence. */
  evidenceFiltersSummary?: string;
  evidenceLimitationNote?: string | null;
};

/**
 * Independent setup-evidence source frame — never nested inside journal ChartFrame.
 */
export function SetupEvidencePanel({
  evidence,
  loading = false,
  onRetry,
  evidenceFiltersSummary,
  evidenceLimitationNote = null,
}: SetupEvidencePanelProps) {
  const available = Boolean(evidence?.available && evidence.data);
  const items = available ? evidence!.data!.items : [];
  const empty = available && items.length === 0;
  const generatedAt = available ? evidence!.data!.generated_at : null;

  return (
    <ChartFrame
      title="Setup evidence"
      sourceLabel="GET /journal/setup-evidence"
      generatedAt={generatedAt}
      filtersSummary={evidenceFiltersSummary}
      limitations={evidenceLimitationNote ? [evidenceLimitationNote] : []}
      sampleSize={available ? items.length : null}
      sampleLabel="evidence rows"
      loading={loading}
      error={evidence && !evidence.available ? evidence.error ?? "Setup evidence unavailable" : null}
      onRetry={onRetry}
      empty={!loading && available ? empty : false}
      emptyTitle="No setup-evidence rows for the current filters"
      emptyDescription="Evidence tiers appear after paper validation / backtest confirmation data exists."
      data-testid="setup-evidence-panel"
    >
      <ul className="space-y-2 text-sm" data-testid="setup-evidence-list">
        {items.map((item) => (
          <li
            key={`${item.strategy_id}:${item.strategy_version_id}`}
            className="rounded-control border border-border-subtle px-3 py-2"
            data-testid={`setup-evidence-item-${item.strategy_id}`}
          >
            <p className="font-medium text-text-primary">
              {item.strategy_name} · v{item.version} · {item.tier}
            </p>
            <p className="font-data text-text-muted">
              strategy_id {item.strategy_id}
              {item.measured.oos_expectancy != null
                ? ` · OOS expectancy ${formatMonetary(item.measured.oos_expectancy)}`
                : " · OOS expectancy No P&L data"}
            </p>
            <p className="text-caption text-text-muted">{item.note}</p>
          </li>
        ))}
      </ul>
    </ChartFrame>
  );
}
