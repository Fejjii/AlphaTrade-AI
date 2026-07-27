"use client";

import { useEffect } from "react";

import {
  AnalyticsFilterBar,
  CumulativePnlChart,
  DailyPnlChart,
  OverviewStats,
  useAnalyticsFilters,
  useAnalyticsSources,
} from "@/components/analytics";
import { formatDateRangeLabel } from "@/components/analytics/format";
import { PageHeader } from "@/components/ui/page-header";
import { VerifiedPaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { Tabs, TabsRoot } from "@/components/ui/tabs";
import { ErrorState, LoadingState } from "@/components/states";

const TAB_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "performance", label: "Performance" },
  { id: "setups", label: "Setups", disabled: true },
  { id: "behaviour", label: "Behaviour", disabled: true },
  { id: "validation", label: "Validation", disabled: true },
  { id: "comparison", label: "Comparison", disabled: true },
];

export default function AnalyticsPage() {
  const {
    state,
    apiParams,
    setTab,
    applyDraft,
    applyDatePreset,
    clearFilters,
    cleanupIgnoredParams,
  } = useAnalyticsFilters();

  const { journal, portfolio, loading, reload, bothFailed, partialData } =
    useAnalyticsSources(apiParams);

  useEffect(() => {
    cleanupIgnoredParams();
  }, [cleanupIgnoredParams]);

  const filtersSummary = formatDateRangeLabel(state.dateFrom, state.dateTo);

  return (
    <div className="space-y-8" data-testid="analytics-page">
      <PageHeader
        title="Analytics"
        description="Paper-only statistical hub — overview and performance charts with honest source states."
        meta={<VerifiedPaperModeIndicator />}
      />

      <TabsRoot value={state.tab} onChange={(tab) => setTab(tab as typeof state.tab)}>
        <div data-testid="analytics-tabs">
          <Tabs items={TAB_ITEMS} aria-label="Analytics sections" />
        </div>

        <AnalyticsFilterBar
          state={state}
          onApplyDraft={applyDraft}
          onApplyPreset={applyDatePreset}
          onClear={clearFilters}
        />

        {partialData ? (
          <p
            className="text-sm text-amber-500/90"
            data-testid="analytics-partial-data"
            role="status"
          >
            Partial analytics data — some sources failed. Retry unavailable sections before
            treating this as complete.
          </p>
        ) : null}

        {loading && !journal && !portfolio ? (
          <LoadingState label="Loading analytics…" />
        ) : null}

        {bothFailed ? (
          <ErrorState
            message="Analytics sources unavailable. Journal statistics and paper portfolio both failed."
            onRetry={() => void reload()}
          />
        ) : null}

        {!bothFailed && state.tab === "overview" ? (
          <OverviewStats
            journal={journal}
            portfolio={portfolio}
            onRetryJournal={() => void reload()}
            onRetryPortfolio={() => void reload()}
          />
        ) : null}

        {!bothFailed && state.tab === "performance" ? (
          <div className="space-y-6">
            <DailyPnlChart
              source={portfolio}
              loading={loading && !portfolio}
              onRetry={() => void reload()}
              filtersSummary={filtersSummary}
            />
            <CumulativePnlChart
              source={portfolio}
              loading={loading && !portfolio}
              onRetry={() => void reload()}
              filtersSummary={filtersSummary}
            />
          </div>
        ) : null}
      </TabsRoot>
    </div>
  );
}
