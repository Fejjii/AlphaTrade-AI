"use client";

import { useEffect, useMemo } from "react";

import {
  AnalyticsFilterBar,
  CumulativePnlChart,
  DailyPnlChart,
  OverviewStats,
  formatAppliedFiltersSummary,
  useAnalyticsFilters,
  useAnalyticsSources,
} from "@/components/analytics";
import { freshnessFromTimestamp } from "@/components/workflows/freshness";
import { PageHeader } from "@/components/ui/page-header";
import { VerifiedPaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { TabPanel, Tabs, TabsRoot } from "@/components/ui/tabs";
import { ErrorState, LoadingState } from "@/components/states";

const TAB_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "performance", label: "Performance" },
];

function tabSourcesStale(
  tab: "overview" | "performance",
  journalAsOf: string | null | undefined,
  portfolioAsOf: string | null | undefined,
): boolean {
  const timestamps =
    tab === "overview"
      ? [journalAsOf, portfolioAsOf]
      : [portfolioAsOf];
  const states = timestamps
    .filter(Boolean)
    .map((timestamp) => freshnessFromTimestamp(timestamp)?.state);
  return states.length > 0 && states.every((state) => state === "stale");
}

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

  const filtersSummary = formatAppliedFiltersSummary(state);

  const staleWholeTab = useMemo(
    () =>
      tabSourcesStale(
        state.tab,
        journal?.available ? journal.data?.generated_at : null,
        portfolio?.available ? portfolio.data?.account.as_of : null,
      ),
    [journal, portfolio, state.tab],
  );

  const initialLoad = loading && !journal && !portfolio;

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

        {initialLoad ? <LoadingState label="Loading analytics…" /> : null}

        {bothFailed ? (
          <ErrorState
            message="Analytics sources unavailable. Journal statistics and paper portfolio both failed."
            onRetry={() => void reload()}
          />
        ) : null}

        {!bothFailed ? (
          <>
            <TabPanel id="overview">
              <OverviewStats
                journal={journal}
                portfolio={portfolio}
                loading={loading}
                onRetryJournal={() => void reload()}
                onRetryPortfolio={() => void reload()}
              />
            </TabPanel>
            <TabPanel id="performance">
              <div className="space-y-6">
                <DailyPnlChart
                  source={portfolio}
                  loading={loading && !portfolio}
                  onRetry={() => void reload()}
                  filtersSummary={filtersSummary}
                  staleWholeTab={staleWholeTab}
                />
                <CumulativePnlChart
                  source={portfolio}
                  loading={loading && !portfolio}
                  onRetry={() => void reload()}
                  filtersSummary={filtersSummary}
                  staleWholeTab={staleWholeTab}
                />
              </div>
            </TabPanel>
          </>
        ) : null}
      </TabsRoot>
    </div>
  );
}
