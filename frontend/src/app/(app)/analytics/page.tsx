"use client";

import { useEffect, useMemo } from "react";

import {
  AnalyticsFilterBar,
  OverviewStats,
  PerformanceCharts,
  formatAppliedFiltersSummary,
  gateSourceByFreshness,
  journalFreshnessTimestamp,
  portfolioFreshnessTimestamp,
  tabSourcesStale,
  useAnalyticsFilters,
  useAnalyticsSources,
} from "@/components/analytics";
import { PageHeader } from "@/components/ui/page-header";
import { VerifiedPaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { TabPanel, Tabs, TabsRoot } from "@/components/ui/tabs";
import { ErrorState, LoadingState, StaleState } from "@/components/states";

const TAB_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "performance", label: "Performance" },
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

  const filtersSummary = formatAppliedFiltersSummary(state);

  const gatedJournal = useMemo(
    () => gateSourceByFreshness(journal, journalFreshnessTimestamp(journal)),
    [journal],
  );

  const gatedPortfolio = useMemo(
    () => gateSourceByFreshness(portfolio, portfolioFreshnessTimestamp(portfolio)),
    [portfolio],
  );

  const staleWholeTab = useMemo(
    () => tabSourcesStale(state.tab, journal, portfolio),
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
              {staleWholeTab ? (
                <div data-testid="overview-stale-state">
                  <StaleState message="Analytics sources may be delayed or stale for this view." />
                </div>
              ) : null}
              <OverviewStats
                journal={gatedJournal}
                portfolio={gatedPortfolio}
                loading={loading}
                onRetryJournal={() => void reload()}
                onRetryPortfolio={() => void reload()}
              />
            </TabPanel>
            <TabPanel id="performance">
              {state.tab === "performance" ? (
                <PerformanceCharts
                  source={gatedPortfolio}
                  loading={loading && !portfolio}
                  onRetry={() => void reload()}
                  filtersSummary={filtersSummary}
                  staleWholeTab={staleWholeTab}
                />
              ) : null}
            </TabPanel>
          </>
        ) : null}
      </TabsRoot>
    </div>
  );
}
