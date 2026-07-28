"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type { JournalComparisonResponse } from "@/lib/api/types";

import { buildFilterKey, type AnalyticsFilterParams } from "./filterValidation";

type ComparisonSnapshot = {
  filterKey: string;
  comparison: SourceResult<JournalComparisonResponse>;
};

/**
 * Comparison-tab loader with request-generation guards.
 * Never displays stale-filter data under current filter captions.
 */
export function useComparisonSources(params: AnalyticsFilterParams, enabled: boolean) {
  const filterKey = useMemo(() => buildFilterKey(params), [params]);
  const [snapshot, setSnapshot] = useState<ComparisonSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const generationRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    if (!enabled) return;
    const generation = ++generationRef.current;
    setLoading(true);

    const comparison = await loadSource(api.journal.comparison(params.comparison));

    if (!mountedRef.current || generation !== generationRef.current) return;

    setSnapshot({ filterKey, comparison });
    setLoading(false);
  }, [enabled, filterKey, params.comparison]);

  useEffect(() => {
    if (!enabled) return;
    void load();
  }, [enabled, load]);

  const matchesCurrentFilter = enabled && snapshot?.filterKey === filterKey;
  const comparison = matchesCurrentFilter ? snapshot?.comparison ?? null : null;
  const isLoading = enabled && (loading || !matchesCurrentFilter);

  return {
    comparison,
    loading: isLoading,
    reload: load,
    filterKey,
    loadedFilterKey: matchesCurrentFilter ? snapshot?.filterKey ?? null : null,
  };
}
