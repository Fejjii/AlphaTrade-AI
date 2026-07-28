"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type {
  LearningAnalyticsParams,
  LearningAnalyticsSummaryResponse,
  SetupPerformanceResponse,
  SetupRankingResponse,
  StrategyQualitySummaryResponse,
} from "@/lib/api/types";

import {
  buildStrategyQualityFilterKey,
  buildValidationFilterKey,
  type AnalyticsFilterParams,
} from "./filterValidation";

type IndependentSourceReturn<T> = {
  source: SourceResult<T> | null;
  loading: boolean;
  retryLoading: boolean;
  reload: () => Promise<void>;
  loadedKey: string | null;
};

function useIndependentValidationSource<T>(
  enabled: boolean,
  requestKey: string,
  fetcher: () => Promise<SourceResult<T>>,
): IndependentSourceReturn<T> {
  const [result, setResult] = useState<SourceResult<T> | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [retryLoading, setRetryLoading] = useState(false);
  const generationRef = useRef(0);
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      setResult(null);
      setLoadedKey(null);
      setLoading(false);
      setRetryLoading(false);
      return;
    }

    const generation = ++generationRef.current;
    setLoading(true);
    setResult(null);

    void fetcherRef.current().then((next) => {
      if (!mountedRef.current || generation !== generationRef.current) return;
      setResult(next);
      setLoadedKey(requestKey);
      setLoading(false);
    });
  }, [enabled, requestKey]);

  const reload = useCallback(async () => {
    if (!enabled) return;
    const generation = ++generationRef.current;
    setRetryLoading(true);
    try {
      const next = await fetcherRef.current();
      if (!mountedRef.current || generation !== generationRef.current) return;
      setResult(next);
      setLoadedKey(requestKey);
    } finally {
      if (mountedRef.current && generation === generationRef.current) {
        setRetryLoading(false);
      }
    }
  }, [enabled, requestKey]);

  const displaySource = enabled && loadedKey === requestKey ? result : null;
  const isLoading = enabled && (loading || loadedKey !== requestKey);

  return {
    source: displaySource,
    loading: isLoading,
    retryLoading,
    reload,
    loadedKey: enabled ? loadedKey : null,
  };
}

function learningParamsFromValidation(
  params: AnalyticsFilterParams,
): LearningAnalyticsParams {
  return {
    start_date: params.validation.start_date,
    end_date: params.validation.end_date,
    min_sample: params.validation.min_sample,
  };
}

/**
 * Validation-tab loaders with independent source slots, keys, and retry actions.
 * A slow or failed source never delays already completed sibling widgets.
 */
export function useValidationSources(params: AnalyticsFilterParams, enabled: boolean) {
  const summaryParams = useMemo(() => learningParamsFromValidation(params), [params]);
  const setupParams = useMemo(
    () => ({
      ...learningParamsFromValidation(params),
      dimension: params.validation.dimension,
    }),
    [params],
  );
  const strategyParams = useMemo(() => params.strategyQuality, [params.strategyQuality]);

  const summaryKey = useMemo(
    () => buildValidationFilterKey(summaryParams),
    [summaryParams],
  );
  const setupPerformanceKey = useMemo(
    () => buildValidationFilterKey(setupParams),
    [setupParams],
  );
  const setupRankingKey = useMemo(
    () => buildValidationFilterKey(setupParams),
    [setupParams],
  );
  const strategyQualityKey = useMemo(
    () => buildStrategyQualityFilterKey(strategyParams),
    [strategyParams],
  );

  const summarySlot = useIndependentValidationSource<LearningAnalyticsSummaryResponse>(
    enabled,
    summaryKey,
    () => loadSource(api.learningAnalytics.summary(summaryParams)),
  );
  const setupPerformanceSlot = useIndependentValidationSource<SetupPerformanceResponse>(
    enabled,
    setupPerformanceKey,
    () => loadSource(api.learningAnalytics.setupPerformance(setupParams)),
  );
  const setupRankingSlot = useIndependentValidationSource<SetupRankingResponse>(
    enabled,
    setupRankingKey,
    () => loadSource(api.learningAnalytics.setupRanking(setupParams)),
  );
  const strategyQualitySlot = useIndependentValidationSource<StrategyQualitySummaryResponse>(
    enabled,
    strategyQualityKey,
    () => loadSource(api.strategyQuality.summary(strategyParams)),
  );

  const reloadSummary = summarySlot.reload;
  const reloadSetupPerformance = setupPerformanceSlot.reload;
  const reloadSetupRanking = setupRankingSlot.reload;
  const reloadStrategyQuality = strategyQualitySlot.reload;

  const reload = useCallback(async () => {
    await Promise.all([
      reloadSummary(),
      reloadSetupPerformance(),
      reloadSetupRanking(),
      reloadStrategyQuality(),
    ]);
  }, [
    reloadSummary,
    reloadSetupPerformance,
    reloadSetupRanking,
    reloadStrategyQuality,
  ]);

  const loading =
    summarySlot.loading ||
    setupPerformanceSlot.loading ||
    setupRankingSlot.loading ||
    strategyQualitySlot.loading;

  return {
    summary: summarySlot.source,
    summaryLoading: summarySlot.loading,
    summaryRetryLoading: summarySlot.retryLoading,
    setupPerformance: setupPerformanceSlot.source,
    setupPerformanceLoading: setupPerformanceSlot.loading,
    setupPerformanceRetryLoading: setupPerformanceSlot.retryLoading,
    setupRanking: setupRankingSlot.source,
    setupRankingLoading: setupRankingSlot.loading,
    setupRankingRetryLoading: setupRankingSlot.retryLoading,
    strategyQuality: strategyQualitySlot.source,
    strategyQualityLoading: strategyQualitySlot.loading,
    strategyQualityRetryLoading: strategyQualitySlot.retryLoading,
    loading,
    reload,
    reloadSummary,
    reloadSetupPerformance,
    reloadSetupRanking,
    reloadStrategyQuality,
    summaryKey,
    setupPerformanceKey,
    setupRankingKey,
    strategyQualityKey,
    summaryLoadedKey: summarySlot.loadedKey,
    setupPerformanceLoadedKey: setupPerformanceSlot.loadedKey,
    setupRankingLoadedKey: setupRankingSlot.loadedKey,
    strategyQualityLoadedKey: strategyQualitySlot.loadedKey,
  };
}
