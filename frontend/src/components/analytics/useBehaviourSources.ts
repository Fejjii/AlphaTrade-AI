"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";

import {
  buildAnalyticsWindowFilterKey,
  buildLearningWindowFilterKey,
  buildRuleComplianceFilterKey,
  type AnalyticsFilterParams,
} from "./filterValidation";

type IndependentSourceReturn<T> = {
  source: SourceResult<T> | null;
  loading: boolean;
  retryLoading: boolean;
  reload: () => Promise<void>;
  loadedKey: string | null;
};

function useIndependentBehaviourSource<T>(
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

/**
 * Behaviour-tab loaders with independent source slots, keys, and retry actions.
 * A slow or failed source never delays already completed sibling widgets.
 */
export function useBehaviourSources(params: AnalyticsFilterParams, enabled: boolean) {
  const ruleComplianceKey = useMemo(
    () => buildRuleComplianceFilterKey(params.ruleComplianceJournal),
    [params.ruleComplianceJournal],
  );
  const analyticsWindowKey = useMemo(
    () => buildAnalyticsWindowFilterKey(params.analyticsWindow),
    [params.analyticsWindow],
  );
  const learningWindowKey = useMemo(
    () => buildLearningWindowFilterKey(params.learningWindow),
    [params.learningWindow],
  );

  const ruleComplianceSlot = useIndependentBehaviourSource(
    enabled,
    ruleComplianceKey,
    () => loadSource(api.journal.statistics(params.ruleComplianceJournal)),
  );
  const proposalDisciplineSlot = useIndependentBehaviourSource(
    enabled,
    analyticsWindowKey,
    () => loadSource(api.analytics.discipline(params.analyticsWindow)),
  );
  const learningDisciplineSlot = useIndependentBehaviourSource(
    enabled,
    learningWindowKey,
    () => loadSource(api.learningAnalytics.discipline(params.learningWindow)),
  );
  const riskBehaviorSlot = useIndependentBehaviourSource(
    enabled,
    analyticsWindowKey,
    () => loadSource(api.analytics.riskBehavior(params.analyticsWindow)),
  );

  const reloadRuleCompliance = ruleComplianceSlot.reload;
  const reloadProposalDiscipline = proposalDisciplineSlot.reload;
  const reloadLearningDiscipline = learningDisciplineSlot.reload;
  const reloadRiskBehavior = riskBehaviorSlot.reload;

  const reload = useCallback(async () => {
    await Promise.all([
      reloadRuleCompliance(),
      reloadProposalDiscipline(),
      reloadLearningDiscipline(),
      reloadRiskBehavior(),
    ]);
  }, [
    reloadRuleCompliance,
    reloadProposalDiscipline,
    reloadLearningDiscipline,
    reloadRiskBehavior,
  ]);

  const loading =
    ruleComplianceSlot.loading ||
    proposalDisciplineSlot.loading ||
    learningDisciplineSlot.loading ||
    riskBehaviorSlot.loading;

  return {
    ruleCompliance: ruleComplianceSlot.source,
    ruleComplianceLoading: ruleComplianceSlot.loading,
    ruleComplianceRetryLoading: ruleComplianceSlot.retryLoading,
    proposalDiscipline: proposalDisciplineSlot.source,
    proposalDisciplineLoading: proposalDisciplineSlot.loading,
    proposalDisciplineRetryLoading: proposalDisciplineSlot.retryLoading,
    learningDiscipline: learningDisciplineSlot.source,
    learningDisciplineLoading: learningDisciplineSlot.loading,
    learningDisciplineRetryLoading: learningDisciplineSlot.retryLoading,
    riskBehavior: riskBehaviorSlot.source,
    riskBehaviorLoading: riskBehaviorSlot.loading,
    riskBehaviorRetryLoading: riskBehaviorSlot.retryLoading,
    loading,
    reload,
    reloadRuleCompliance,
    reloadProposalDiscipline,
    reloadLearningDiscipline,
    reloadRiskBehavior,
    ruleComplianceKey,
    analyticsWindowKey,
    learningWindowKey,
    ruleComplianceLoadedKey: ruleComplianceSlot.loadedKey,
    proposalDisciplineLoadedKey: proposalDisciplineSlot.loadedKey,
    learningDisciplineLoadedKey: learningDisciplineSlot.loadedKey,
    riskBehaviorLoadedKey: riskBehaviorSlot.loadedKey,
  };
}
