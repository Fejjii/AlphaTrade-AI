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
 * Setups-tab loader: journal bucket statistics + setup-evidence.
 * Never calls /performance/portfolio (journal setup_id must not reach PP).
 */
export function useSetupAnalyticsSources(
  params: SetupAnalyticsApiParams,
  options: { enabled: boolean },
) {
  const filterKey = useMemo(() => buildSetupFilterKey(params), [params]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [strategies, setStrategies] = useState<UserStrategy[]>([]);
  const [strategiesError, setStrategiesError] = useState<string | null>(null);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const generationRef = useRef(0);
  const mountedRef = useRef(true);
  const strategiesLoadedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadStrategies = useCallback(async () => {
    if (strategiesLoadedRef.current) return;
    setStrategiesLoading(true);
    setStrategiesError(null);
    try {
      const page = await api.strategies.list({ limit: 200, offset: 0 });
      if (!mountedRef.current) return;
      setStrategies(page.items ?? []);
      strategiesLoadedRef.current = true;
    } catch (error) {
      if (!mountedRef.current) return;
      setStrategiesError(error instanceof Error ? error.message : "Strategies unavailable");
    } finally {
      if (mountedRef.current) setStrategiesLoading(false);
    }
  }, []);

  const load = useCallback(async () => {
    if (!options.enabled) return;
    const generation = ++generationRef.current;
    setLoading(true);

    const [journal, evidence] = await Promise.all([
      loadSource(api.journal.statistics(params.journal)),
      loadSource(api.journal.setupEvidence(params.evidence)),
    ]);

    if (!mountedRef.current || generation !== generationRef.current) return;

    setSnapshot({ filterKey, journal, evidence });
    setLoading(false);
  }, [filterKey, options.enabled, params.evidence, params.journal]);

  useEffect(() => {
    if (!options.enabled) return;
    void load();
    void loadStrategies();
  }, [load, loadStrategies, options.enabled]);

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
    loading: isLoading,
    reload: load,
    filterKey,
    loadedFilterKey: matchesCurrentFilter ? snapshot?.filterKey ?? null : null,
  };
}
