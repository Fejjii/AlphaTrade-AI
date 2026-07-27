"use client";

import { useEffect, useMemo } from "react";

import {
  AnalyticsFilterBar,
  OverviewStats,
  PerformanceCharts,
  SetupsCharts,
  formatAppliedFiltersSummary,
  gateSourceByFreshness,
  journalFreshnessTimestamp,
  portfolioFreshnessTimestamp,
  tabSourcesStale,
  useAnalyticsFilters,
  useAnalyticsSources,
  useSetupAnalyticsSources,
} from "@/components/analytics";
import { PageHeader } from "@/components/ui/page-header";
import { VerifiedPaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { TabPanel, Tabs, TabsRoot } from "@/components/ui/tabs";
import { ErrorState, LoadingState, StaleState } from "@/components/states";

const TAB_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "performance", label: "Performance" },
  { id: "setups", label: "Setups" },
];

export default function AnalyticsPage() {
  const {
    state,
    apiParams,
    setupApiParams,
    setTab,
    applyDraft,
    applyDatePreset,
    setGroupBy,
    setBucketOffset,
    clearFilters,
    cleanupIgnoredParams,
  } = useAnalyticsFilters();

  const shared = useAnalyticsSources(apiParams);
  const setups = useSetupAnalyticsSources(setupApiParams, { enabled: state.tab === "setups" });

  useEffect(() => {
    cleanupIgnoredParams();
  }, [cleanupIgnoredParams]);

  const filtersSummary = formatAppliedFiltersSummary(state);

  const gatedJournal = useMemo(
    () => gateSourceByFreshness(shared.journal, journalFreshnessTimestamp(shared.journal)),
    [shared.journal],
  );

  const gatedPortfolio = useMemo(
    () => gateSourceByFreshness(shared.portfolio, portfolioFreshnessTimestamp(shared.portfolio)),
    [shared.portfolio],
  );

  const gatedSetupJournal = useMemo(
    () => gateSourceByFreshness(setups.journal, journalFreshnessTimestamp(setups.journal)),
    [setups.journal],
  );

  const staleWholeTab = useMemo(() => {
    if (state.tab === "setups") {
      return tabSourcesStale("setups", setups.journal, null);
    }
    return tabSourcesStale(state.tab, shared.journal, shared.portfolio);
  }, [setups.journal, shared.journal, shared.portfolio, state.tab]);

  const initialLoad =
    state.tab === "setups"
      ? setups.loading && !setups.journal
      : shared.loading && !shared.journal && !shared.portfolio;

  const blockPage =
    state.tab === "setups"
      ? Boolean(setups.journal && !setups.journal.available && setups.evidence && !setups.evidence.available)
      : shared.bothFailed;

  return (
    <div className="space-y-8 max-w-full overflow-x-hidden" data-testid="analytics-page">
      <PageHeader
        title="Analytics"
        description="Paper-only statistical hub — overview, performance, and journal setup analytics with honest source states."
        meta={<VerifiedPaperModeIndicator />}
      />

      <TabsRoot value={state.tab} onChange={(tab) => setTab(tab as typeof state.tab)}>
        <div data-testid="analytics-tabs">
          <Tabs items={TAB_ITEMS} aria-label="Analytics sections" />
        </div>

        <AnalyticsFilterBar
          state={state}
          strategies={setups.strategies}
          strategiesLoading={setups.strategiesLoading}
          onApplyDraft={applyDraft}
          onApplyPreset={applyDatePreset}
          onClear={clearFilters}
        />

        {state.tab !== "setups" && shared.partialData ? (
          <p
            className="text-sm text-amber-500/90"
            data-testid="analytics-partial-data"
            role="status"
          >
            Partial analytics data — some sources failed. Retry unavailable sections before
            treating this as complete.
          </p>
        ) : null}

        {state.tab === "setups" &&
        setups.evidence &&
        !setups.evidence.available &&
        setups.journal?.available ? (
          <p
            className="text-sm text-amber-500/90"
            data-testid="analytics-partial-data"
            role="status"
          >
            Partial analytics data — setup evidence failed. Bucket charts remain from journal
            statistics.
          </p>
        ) : null}

        {initialLoad ? <LoadingState label="Loading analytics…" /> : null}

        {blockPage ? (
          <ErrorState
            message={
              state.tab === "setups"
                ? "Setups analytics unavailable. Journal statistics and setup evidence both failed."
                : "Analytics sources unavailable. Journal statistics and paper portfolio both failed."
            }
            onRetry={() => void (state.tab === "setups" ? setups.reload() : shared.reload())}
          />
        ) : null}

        {!blockPage ? (
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
                loading={shared.loading}
                onRetryJournal={() => void shared.reload()}
                onRetryPortfolio={() => void shared.reload()}
              />
            </TabPanel>
            <TabPanel id="performance">
              {state.tab === "performance" ? (
                <PerformanceCharts
                  source={gatedPortfolio}
                  loading={shared.loading && !shared.portfolio}
                  onRetry={() => void shared.reload()}
                  filtersSummary={filtersSummary}
                  staleWholeTab={staleWholeTab}
                />
              ) : null}
            </TabPanel>
            <TabPanel id="setups">
              {state.tab === "setups" ? (
                <SetupsCharts
                  source={gatedSetupJournal}
                  evidence={setups.evidence}
                  loading={setups.loading && !setups.journal}
                  onRetry={() => void setups.reload()}
                  filtersSummary={filtersSummary}
                  staleWholeTab={staleWholeTab}
                  groupBy={state.groupBy}
                  onGroupByChange={setGroupBy}
                  bucketOffset={state.bucketOffset}
                  onPageChange={setBucketOffset}
                />
              ) : null}
            </TabPanel>
          </>
        ) : null}
      </TabsRoot>
    </div>
  );
}
