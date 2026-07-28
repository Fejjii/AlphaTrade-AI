"use client";

import { useMemo } from "react";

import type { AnalyticsFilterParams } from "./filterValidation";
import {
  formatAnalyticsWindowFiltersSummary,
  formatJournalStatsFiltersSummary,
  formatLearningAnalyticsFiltersSummary,
} from "./filterValidation";
import { DisciplineScoreCards } from "./DisciplineScoreCards";
import { RiskBehaviourCounters } from "./RiskBehaviourCounters";
import { RuleComplianceChart } from "./AnalyticsCharts";
import {
  gateSourceByFreshness,
  journalFreshnessTimestamp,
  tabSourcesStale,
} from "./sourceFreshness";
import { useBehaviourSources } from "./useBehaviourSources";

export type BehaviourChartsProps = {
  apiParams: AnalyticsFilterParams;
  enabled?: boolean;
};

export function BehaviourCharts({ apiParams, enabled = true }: BehaviourChartsProps) {
  const {
    ruleCompliance,
    proposalDiscipline,
    learningDiscipline,
    riskBehavior,
    loading,
    reloadRuleCompliance,
    reloadProposalDiscipline,
    reloadLearningDiscipline,
    reloadRiskBehavior,
  } = useBehaviourSources(apiParams, enabled);

  const ruleComplianceSummary = formatJournalStatsFiltersSummary(
    apiParams.ruleComplianceJournal,
  );
  const analyticsWindowSummary = formatAnalyticsWindowFiltersSummary(
    apiParams.analyticsWindow,
  );
  const learningWindowSummary = formatLearningAnalyticsFiltersSummary(
    apiParams.learningWindow,
  );

  const gatedRuleCompliance = useMemo(
    () => gateSourceByFreshness(ruleCompliance, journalFreshnessTimestamp(ruleCompliance)),
    [ruleCompliance],
  );

  const staleWholeTab = useMemo(
    () => tabSourcesStale("behaviour", null, null, undefined, [ruleCompliance]),
    [ruleCompliance],
  );

  if (!enabled) return null;

  return (
    <div className="space-y-6" data-testid="behaviour-charts">
      <RuleComplianceChart
        source={gatedRuleCompliance}
        loading={loading && !ruleCompliance}
        onRetry={() => void reloadRuleCompliance()}
        filtersSummary={ruleComplianceSummary}
        staleWholeTab={staleWholeTab}
      />
      <DisciplineScoreCards
        proposalSource={proposalDiscipline}
        learningSource={learningDiscipline}
        loading={loading}
        onRetryProposal={() => void reloadProposalDiscipline()}
        onRetryLearning={() => void reloadLearningDiscipline()}
        proposalFiltersSummary={analyticsWindowSummary}
        learningFiltersSummary={learningWindowSummary}
        staleWholeTab={staleWholeTab}
      />
      <RiskBehaviourCounters
        source={riskBehavior}
        loading={loading && !riskBehavior}
        onRetry={() => void reloadRiskBehavior()}
        filtersSummary={analyticsWindowSummary}
        staleWholeTab={staleWholeTab}
      />
    </div>
  );
}
