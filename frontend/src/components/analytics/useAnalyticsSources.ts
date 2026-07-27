"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type { JournalStatsResponse, PaperPortfolioResponse } from "@/lib/api/types";

import { buildFilterKey, type AnalyticsFilterParams } from "./filterValidation";

type SourcesSnapshot = {
  filterKey: string;
  journal: SourceResult<JournalStatsResponse>;
  portfolio: SourceResult<PaperPortfolioResponse>;
};

/**
 * Local analytics data loader with request-generation guards.
 * Never displays stale-filter data under current filter captions.
 */
export function useAnalyticsSources(params: AnalyticsFilterParams) {
  const filterKey = useMemo(() => buildFilterKey(params), [params]);
  const [snapshot, setSnapshot] = useState<SourcesSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const generationRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const generation = ++generationRef.current;
    setLoading(true);

    const [journal, portfolio] = await Promise.all([
      loadSource(api.journal.statistics(params.journal)),
      loadSource(api.performance.portfolio(params.portfolio)),
    ]);

    if (!mountedRef.current || generation !== generationRef.current) return;

    setSnapshot({ filterKey, journal, portfolio });
    setLoading(false);
  }, [filterKey, params.journal, params.portfolio]);

  useEffect(() => {
    void load();
  }, [load]);

  const matchesCurrentFilter = snapshot?.filterKey === filterKey;
  const journal = matchesCurrentFilter ? snapshot?.journal ?? null : null;
  const portfolio = matchesCurrentFilter ? snapshot?.portfolio ?? null : null;
  const isLoading = loading || !matchesCurrentFilter;

  const bothFailed = Boolean(
    journal && portfolio && !journal.available && !portfolio.available,
  );
  const partialData = Boolean(
    journal && portfolio && !bothFailed && (!journal.available || !portfolio.available),
  );

  return {
    journal,
    portfolio,
    loading: isLoading,
    reload: load,
    bothFailed,
    partialData,
    filterKey,
    loadedFilterKey: matchesCurrentFilter ? snapshot?.filterKey ?? null : null,
  };
}
