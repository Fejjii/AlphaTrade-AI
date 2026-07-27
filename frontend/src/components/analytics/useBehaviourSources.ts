"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type {
  DisciplineAnalyticsResponse,
  DisciplineScoreResult,
  JournalStatsResponse,
  RiskBehaviorAnalytics,
} from "@/lib/api/types";

import { buildFilterKey, type AnalyticsFilterParams } from "./filterValidation";

type BehaviourSnapshot = {
  filterKey: string;
  ruleCompliance: SourceResult<JournalStatsResponse>;
  proposalDiscipline: SourceResult<DisciplineScoreResult>;
  learningDiscipline: SourceResult<DisciplineAnalyticsResponse>;
  riskBehavior: SourceResult<RiskBehaviorAnalytics>;
};

/**
 * Independent Behaviour-tab loaders. One failed source never blocks sibling widgets,
 * and stale filter responses are never displayed under the current filter key.
 */
export function useBehaviourSources(params: AnalyticsFilterParams, enabled: boolean) {
  const filterKey = useMemo(() => buildFilterKey(params), [params]);
  const [snapshot, setSnapshot] = useState<BehaviourSnapshot | null>(null);
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

    const [ruleCompliance, proposalDiscipline, learningDiscipline, riskBehavior] =
      await Promise.all([
        loadSource(api.journal.statistics(params.ruleComplianceJournal)),
        loadSource(api.analytics.discipline(params.analyticsWindow)),
        loadSource(api.learningAnalytics.discipline(params.learningWindow)),
        loadSource(api.analytics.riskBehavior(params.analyticsWindow)),
      ]);

    if (!mountedRef.current || generation !== generationRef.current) return;

    setSnapshot({
      filterKey,
      ruleCompliance,
      proposalDiscipline,
      learningDiscipline,
      riskBehavior,
    });
    setLoading(false);
  }, [
    enabled,
    filterKey,
    params.analyticsWindow,
    params.learningWindow,
    params.ruleComplianceJournal,
  ]);

  useEffect(() => {
    if (!enabled) return;
    void load();
  }, [enabled, load]);

  const matchesCurrentFilter = enabled && snapshot?.filterKey === filterKey;
  const ruleCompliance = matchesCurrentFilter ? snapshot?.ruleCompliance ?? null : null;
  const proposalDiscipline = matchesCurrentFilter ? snapshot?.proposalDiscipline ?? null : null;
  const learningDiscipline = matchesCurrentFilter ? snapshot?.learningDiscipline ?? null : null;
  const riskBehavior = matchesCurrentFilter ? snapshot?.riskBehavior ?? null : null;
  const isLoading = enabled && (loading || !matchesCurrentFilter);

  const reloadRuleCompliance = useCallback(async () => {
    if (!enabled) return;
    const generation = generationRef.current;
    const next = await loadSource(api.journal.statistics(params.ruleComplianceJournal));
    if (!mountedRef.current || generation !== generationRef.current) return;
    setSnapshot((current) =>
      current && current.filterKey === filterKey
        ? { ...current, ruleCompliance: next }
        : current,
    );
  }, [enabled, filterKey, params.ruleComplianceJournal]);

  const reloadProposalDiscipline = useCallback(async () => {
    if (!enabled) return;
    const generation = generationRef.current;
    const next = await loadSource(api.analytics.discipline(params.analyticsWindow));
    if (!mountedRef.current || generation !== generationRef.current) return;
    setSnapshot((current) =>
      current && current.filterKey === filterKey
        ? { ...current, proposalDiscipline: next }
        : current,
    );
  }, [enabled, filterKey, params.analyticsWindow]);

  const reloadLearningDiscipline = useCallback(async () => {
    if (!enabled) return;
    const generation = generationRef.current;
    const next = await loadSource(api.learningAnalytics.discipline(params.learningWindow));
    if (!mountedRef.current || generation !== generationRef.current) return;
    setSnapshot((current) =>
      current && current.filterKey === filterKey
        ? { ...current, learningDiscipline: next }
        : current,
    );
  }, [enabled, filterKey, params.learningWindow]);

  const reloadRiskBehavior = useCallback(async () => {
    if (!enabled) return;
    const generation = generationRef.current;
    const next = await loadSource(api.analytics.riskBehavior(params.analyticsWindow));
    if (!mountedRef.current || generation !== generationRef.current) return;
    setSnapshot((current) =>
      current && current.filterKey === filterKey
        ? { ...current, riskBehavior: next }
        : current,
    );
  }, [enabled, filterKey, params.analyticsWindow]);

  return {
    ruleCompliance,
    proposalDiscipline,
    learningDiscipline,
    riskBehavior,
    loading: isLoading,
    reload: load,
    reloadRuleCompliance,
    reloadProposalDiscipline,
    reloadLearningDiscipline,
    reloadRiskBehavior,
    filterKey,
    loadedFilterKey: matchesCurrentFilter ? snapshot?.filterKey ?? null : null,
  };
}
