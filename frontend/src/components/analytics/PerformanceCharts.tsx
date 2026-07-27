"use client";

import type { SourceResult } from "@/components/workflows";
import type { PaperPortfolioResponse } from "@/lib/api/types";

import { CumulativePnlChart, DailyPnlChart } from "./AnalyticsCharts";

export type PerformanceChartsProps = {
  source: SourceResult<PaperPortfolioResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
};

export function PerformanceCharts({
  source,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
}: PerformanceChartsProps) {
  return (
    <div className="space-y-6" data-testid="performance-charts">
      <DailyPnlChart
        source={source}
        loading={loading}
        onRetry={onRetry}
        filtersSummary={filtersSummary}
        staleWholeTab={staleWholeTab}
      />
      <CumulativePnlChart
        source={source}
        loading={loading}
        onRetry={onRetry}
        filtersSummary={filtersSummary}
        staleWholeTab={staleWholeTab}
      />
    </div>
  );
}
