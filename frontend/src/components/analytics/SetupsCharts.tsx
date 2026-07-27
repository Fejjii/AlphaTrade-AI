"use client";

import type { SourceResult } from "@/components/workflows";
import type { JournalStatsResponse, SetupEvidenceResponse } from "@/lib/api/types";

import { SetupBucketTable } from "./SetupBucketTable";
import { SetupExpectancyChart, SetupWinRateChart } from "./AnalyticsCharts";
import { SetupGroupToggle } from "./SetupGroupToggle";
import type { SetupGroupBy } from "./filterValidation";

export type SetupsChartsProps = {
  source: SourceResult<JournalStatsResponse> | null;
  evidence: SourceResult<SetupEvidenceResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
  groupBy: SetupGroupBy;
  onGroupByChange: (value: SetupGroupBy) => void;
  bucketOffset: number;
  onPageChange: (offset: number) => void;
};

export function SetupsCharts({
  source,
  evidence,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
  groupBy,
  onGroupByChange,
  bucketOffset,
  onPageChange,
}: SetupsChartsProps) {
  return (
    <div className="space-y-6" data-testid="setups-charts">
      <div className="space-y-2">
        <p className="text-sm text-text-muted">
          Journal setup identities only — never Portfolio proposal-flow or paper-validation setup
          keys.
        </p>
        <SetupGroupToggle value={groupBy} onChange={onGroupByChange} />
      </div>

      <SetupWinRateChart
        source={source}
        loading={loading}
        onRetry={onRetry}
        filtersSummary={filtersSummary}
        staleWholeTab={staleWholeTab}
      />
      <SetupExpectancyChart
        source={source}
        loading={loading}
        onRetry={onRetry}
        filtersSummary={filtersSummary}
        staleWholeTab={staleWholeTab}
      />
      <SetupBucketTable
        source={source}
        evidence={evidence}
        loading={loading}
        onRetry={onRetry}
        filtersSummary={filtersSummary}
        staleWholeTab={staleWholeTab}
        groupBy={groupBy}
        bucketOffset={bucketOffset}
        onPageChange={onPageChange}
      />
    </div>
  );
}
