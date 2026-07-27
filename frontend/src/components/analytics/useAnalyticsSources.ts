"use client";

import { useCallback, useEffect, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type { JournalStatsResponse, PaperPortfolioResponse } from "@/lib/api/types";

import type { AnalyticsFilterParams } from "./useAnalyticsFilters";

export type AnalyticsSourcesSnapshot = {
  journal: SourceResult<JournalStatsResponse>;
  portfolio: SourceResult<PaperPortfolioResponse>;
};

/**
 * Local analytics data loader — explicit per-source results without modifying useAsyncData.
 */
export function useAnalyticsSources(params: AnalyticsFilterParams) {
  const [journal, setJournal] = useState<SourceResult<JournalStatsResponse> | null>(null);
  const [portfolio, setPortfolio] = useState<SourceResult<PaperPortfolioResponse> | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    const [nextJournal, nextPortfolio] = await Promise.all([
      loadSource(api.journal.statistics(params.journal)),
      loadSource(api.performance.portfolio(params.portfolio)),
    ]);
    setJournal(nextJournal);
    setPortfolio(nextPortfolio);
    setLoading(false);
  }, [params]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const bothFailed = Boolean(journal && portfolio && !journal.available && !portfolio.available);
  const partialData = Boolean(
    journal && portfolio && !bothFailed && (!journal.available || !portfolio.available),
  );

  return {
    journal,
    portfolio,
    loading,
    reload,
    bothFailed,
    partialData,
  };
}
