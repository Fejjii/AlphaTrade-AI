"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type {
  JournalStatsResponse,
  SetupEvidenceResponse,
  UserStrategy,
} from "@/lib/api/types";

import {
  buildSetupFilterKey,
  type SetupAnalyticsApiParams,
} from "./filterValidation";

type Snapshot = {
  filterKey: string;
  journal: SourceResult<JournalStatsResponse>;
  evidence: SourceResult<SetupEvidenceResponse>;
};

/**
 * Setups-tab loader: journal bucket statistics + setup-evidence + strategy options.
 * Never calls /performance/portfolio (journal identities must not reach PP).
 */
export function useSetupAnalyticsSources(
  params: SetupAnalyticsApiParams,
  options: { enabled: boolean },
) {
  const filterKey = useMemo(() => buildSetupFilterKey(params), [params]);
  const paramsRef = useRef(params);
  paramsRef.current = params;

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [strategies, setStrategies] = useState<UserStrategy[]>([]);
  const [strategiesError, setStrategiesError] = useState<string | null>(null);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [strategiesLoaded, setStrategiesLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const generationRef = useRef(0);
  const mountedRef = useRef(true);
  const strategiesInFlightRef = useRef(false);
  const strategiesSuccessRef = useRef(false);
  const strategiesGenerationRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      strategiesGenerationRef.current += 1;
      strategiesInFlightRef.current = false;
    };
  }, []);

  const loadStrategies = useCallback(async (force = false) => {
    if (strategiesInFlightRef.current) return;
    if (!force && strategiesSuccessRef.current) return;

    const generation = ++strategiesGenerationRef.current;
    strategiesInFlightRef.current = true;
    setStrategiesLoading(true);
    setStrategiesError(null);
    try {
      const page = await api.strategies.list({ limit: 200, offset: 0 });
      if (!mountedRef.current || generation !== strategiesGenerationRef.current) return;
      setStrategies(page.items ?? []);
      setStrategiesLoaded(true);
      strategiesSuccessRef.current = true;
      setStrategiesError(null);
    } catch (error) {
      if (!mountedRef.current || generation !== strategiesGenerationRef.current) return;
      setStrategiesError(error instanceof Error ? error.message : "Strategies unavailable");
      setStrategiesLoaded(false);
      strategiesSuccessRef.current = false;
    } finally {
      if (generation === strategiesGenerationRef.current) {
        strategiesInFlightRef.current = false;
        if (mountedRef.current) setStrategiesLoading(false);
      }
    }
  }, []);

  const reloadStrategies = useCallback(async () => {
    strategiesSuccessRef.current = false;
    setStrategiesLoaded(false);
    await loadStrategies(true);
  }, [loadStrategies]);

  const load = useCallback(async () => {
    if (!options.enabled) return;
    const generation = ++generationRef.current;
    const currentFilterKey = filterKey;
    const currentParams = paramsRef.current;
    setLoading(true);

    const [journal, evidence] = await Promise.all([
      loadSource(api.journal.statistics(currentParams.journal)),
      loadSource(api.journal.setupEvidence(currentParams.evidence)),
    ]);

    if (!mountedRef.current || generation !== generationRef.current) return;

    setSnapshot({ filterKey: currentFilterKey, journal, evidence });
    setLoading(false);
  }, [filterKey, options.enabled]);

  useEffect(() => {
    if (!options.enabled) return;
    void load();
  }, [load, options.enabled]);

  useEffect(() => {
    if (!options.enabled) return;
    void loadStrategies(false);
  }, [loadStrategies, options.enabled]);

  const matchesCurrentFilter = snapshot?.filterKey === filterKey;
  const journal = options.enabled && matchesCurrentFilter ? snapshot?.journal ?? null : null;
  const evidence = options.enabled && matchesCurrentFilter ? snapshot?.evidence ?? null : null;
  const isLoading = options.enabled && (loading || !matchesCurrentFilter);

  return {
    journal,
    evidence,
    strategies,
    strategiesError,
    strategiesLoading,
    strategiesLoaded,
    loading: isLoading,
    reload: load,
    reloadStrategies,
    filterKey,
    loadedFilterKey: matchesCurrentFilter ? snapshot?.filterKey ?? null : null,
  };
}
