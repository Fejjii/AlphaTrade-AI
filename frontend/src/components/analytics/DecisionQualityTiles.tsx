"use client";

import { DataNumber } from "@/components/ui/data-number";
import type { SourceResult } from "@/components/workflows";
import type { DecisionQualityMetrics, JournalComparisonResponse } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { formatMonetary, formatPercent } from "./format";

type DecisionQualityTilesProps = {
  source: SourceResult<JournalComparisonResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

/**
 * Decision-quality percents from the comparison API are already expressed as
 * 0–100 style percentages in some fields (average_entry_timing_pct / average_capture_pct)
 * and rates (early_exit_rate). Mirror the journal comparison page conventions.
 */
function formatTimingPct(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

function formatRate(value: number | null): string {
  return formatPercent(value);
}

function tilesFrom(dq: DecisionQualityMetrics) {
  return [
    {
      id: "entry-timing",
      label: "Avg entry timing",
      value: formatTimingPct(dq.average_entry_timing_pct),
      detail: `n=${dq.timing_sample_count}`,
    },
    {
      id: "early-exit-count",
      label: "Early exit count",
      value: dq.early_exit_count === null ? "—" : String(dq.early_exit_count),
      detail: `of ${dq.early_exit_sample_count}`,
    },
    {
      id: "early-exit-rate",
      label: "Early exit rate",
      value: formatRate(dq.early_exit_rate),
      detail: `n=${dq.early_exit_sample_count}`,
    },
    {
      id: "missed-profit",
      label: "Avg missed profit",
      value: formatMonetary(dq.average_missed_profit),
      detail: `n=${dq.missed_profit_sample_count}`,
    },
    {
      id: "capture",
      label: "Avg capture",
      value: formatTimingPct(dq.average_capture_pct),
      detail: `n=${dq.missed_profit_sample_count}`,
    },
  ];
}

export function DecisionQualityTiles({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: DecisionQualityTilesProps) {
  const dq = source?.available ? source.data?.decision_quality ?? null : null;
  const tiles = dq ? tilesFrom(dq) : [];

  return (
    <ChartFrame
      title="Decision quality"
      sourceLabel="GET /journal/comparison · decision_quality"
      generatedAt={source?.available ? source.data?.generated_at ?? null : null}
      filtersSummary={filtersSummary}
      loading={loading}
      error={source && !source.available ? source.error ?? "Decision quality unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? !dq : false}
      emptyTitle="Decision quality unavailable"
      emptyDescription="No decision-quality metrics were returned for the current filters."
      staleWholeTab={staleWholeTab}
      data-testid="decision-quality-tiles"
    >
      {dq ? (
        <div className="space-y-3">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {tiles.map((tile) => (
              <div key={tile.id} className="space-y-1" data-testid={`decision-quality-${tile.id}`}>
                <p className="text-caption text-text-muted">{tile.label}</p>
                <DataNumber
                  value={tile.value}
                  className="text-lg"
                  aria-label={`${tile.label}: ${tile.value}`}
                />
                <p className="text-caption text-text-muted">{tile.detail}</p>
              </div>
            ))}
          </div>
          <p className="text-caption text-text-muted">
            Null metrics render as unavailable (—), never as zero. Sample sizes come from the server
            response.
          </p>
          <table className="sr-only" data-testid="decision-quality-a11y-table">
            <caption>Decision quality metrics</caption>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {tiles.map((tile) => (
                <tr key={tile.id}>
                  <td>{tile.label}</td>
                  <td>{tile.value}</td>
                  <td>{tile.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </ChartFrame>
  );
}
