"use client";

import { DataNumber } from "@/components/ui/data-number";
import type { SourceResult } from "@/components/workflows";
import type { RiskBehaviorAnalytics } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";

type RiskBehaviourCountersProps = {
  source: SourceResult<RiskBehaviorAnalytics> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

const COUNTERS: {
  key: keyof RiskBehaviorAnalytics;
  label: string;
  testId: string;
}[] = [
  {
    key: "revenge_trading_warnings",
    label: "Revenge-trading warning counts",
    testId: "risk-behaviour-revenge",
  },
  {
    key: "daily_loss_warnings",
    label: "Daily-loss warning counts",
    testId: "risk-behaviour-daily-loss",
  },
  {
    key: "overtrading_warnings",
    label: "Overtrading warning counts",
    testId: "risk-behaviour-overtrading",
  },
  {
    key: "green_day_warnings",
    label: "Green-day warning counts",
    testId: "risk-behaviour-green-day",
  },
];

export function RiskBehaviourCounters({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: RiskBehaviourCountersProps) {
  const data = source?.available ? source.data : null;

  return (
    <ChartFrame
      title="Risk behaviour warning counts"
      sourceLabel="GET /analytics/risk-behavior"
      filtersSummary={filtersSummary}
      loading={loading && !source}
      error={source && !source.available ? source.error ?? "Risk behaviour unavailable" : null}
      onRetry={onRetry}
      empty={false}
      staleWholeTab={staleWholeTab}
      data-testid="risk-behaviour-counters"
    >
      {data ? (
        <div className="space-y-4">
          <p
            className="rounded-control border border-border-subtle bg-surface-1/40 px-3 py-2 text-sm text-text-secondary"
            data-testid="risk-behaviour-counts-caption"
            role="note"
          >
            These values are warning <strong>counts</strong>, not performance metrics. Never infer
            profitability, expectancy, or edge from warning counts.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {COUNTERS.map((counter) => {
              const value = data[counter.key];
              const display = typeof value === "number" ? String(value) : "—";
              return (
                <div key={counter.key} className="space-y-1" data-testid={counter.testId}>
                  <p className="text-caption text-text-muted">{counter.label}</p>
                  <DataNumber value={display} className="text-xl" aria-label={`${counter.label}: ${display}`} />
                </div>
              );
            })}
          </div>
          <p className="text-caption text-text-muted" data-testid="risk-behaviour-completion">
            Journal completion rate (context only):{" "}
            {Number.isFinite(data.journal_completion_rate)
              ? `${(data.journal_completion_rate * 100).toFixed(1)}%`
              : "—"}
          </p>
          <table className="sr-only" data-testid="risk-behaviour-a11y-table">
            <caption>Risk behaviour warning counts</caption>
            <thead>
              <tr>
                <th>Warning type</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {COUNTERS.map((counter) => (
                <tr key={counter.key}>
                  <td>{counter.label}</td>
                  <td>{typeof data[counter.key] === "number" ? String(data[counter.key]) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </ChartFrame>
  );
}
