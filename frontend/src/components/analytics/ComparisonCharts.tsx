"use client";

import { useMemo } from "react";

import type { AnalyticsFilterParams } from "./filterValidation";
import { formatComparisonFiltersSummary } from "./filterValidation";
import { ComparisonChart } from "./AnalyticsCharts";
import { DecisionQualityTiles } from "./DecisionQualityTiles";
import {
  gateSourceByFreshness,
  journalFreshnessTimestamp,
  tabSourcesStale,
} from "./sourceFreshness";
import { useComparisonSources } from "./useComparisonSources";

export type ComparisonChartsProps = {
  apiParams: AnalyticsFilterParams;
  enabled?: boolean;
};

export function ComparisonCharts({ apiParams, enabled = true }: ComparisonChartsProps) {
  const { comparison, loading, reload } = useComparisonSources(apiParams, enabled);

  const comparisonSummary = formatComparisonFiltersSummary(apiParams.comparison);

  const gatedComparison = useMemo(
    () => gateSourceByFreshness(comparison, journalFreshnessTimestamp(comparison)),
    [comparison],
  );

  const staleWholeTab = useMemo(
    () => tabSourcesStale("comparison", null, null, undefined, [comparison]),
    [comparison],
  );

  if (!enabled) return null;

  return (
    <div className="space-y-6" data-testid="comparison-charts">
      <ComparisonChart
        source={gatedComparison}
        loading={loading && !comparison}
        onRetry={() => void reload()}
        filtersSummary={comparisonSummary}
        staleWholeTab={staleWholeTab}
      />
      <DecisionQualityTiles
        source={gatedComparison}
        loading={loading && !comparison}
        onRetry={() => void reload()}
        filtersSummary={comparisonSummary}
        staleWholeTab={staleWholeTab}
      />
    </div>
  );
}
