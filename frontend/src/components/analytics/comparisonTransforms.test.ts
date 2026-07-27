import { describe, expect, it } from "vitest";

import type { JournalComparisonResponse, JournalTradeStatsMetrics } from "@/lib/api/types";

import {
  buildComparisonCohorts,
  evidenceIsInsufficient,
  metricValue,
} from "./comparisonTransforms";

function metrics(
  overrides: Partial<JournalTradeStatsMetrics> = {},
): JournalTradeStatsMetrics {
  return {
    trade_count: 0,
    wins: 0,
    losses: 0,
    breakeven: 0,
    win_rate: null,
    pnl_sample_count: 0,
    net_pnl_total: null,
    gross_pnl_total: null,
    expectancy: null,
    average_winner: null,
    average_loser: null,
    profit_factor: null,
    r_sample_count: 0,
    average_r: null,
    cost_sample_count: 0,
    fees_total: null,
    funding_total: null,
    slippage_total: null,
    total_costs: null,
    mfe_sample_count: 0,
    average_mfe_amount: null,
    mae_sample_count: 0,
    average_mae_amount: null,
    capture_sample_count: 0,
    available_profit_total: null,
    realized_on_available_total: null,
    average_realized_vs_available_pct: null,
    confidence: "insufficient",
    warnings: [],
    ...overrides,
  };
}

function response(
  cohorts: JournalComparisonResponse["cohorts"],
): JournalComparisonResponse {
  return {
    filters: {},
    cohorts,
    scorecards: [],
    by_entry_method: [],
    by_source: [],
    rule_compliance: [],
    decision_quality: {
      timing_sample_count: 0,
      average_entry_timing_pct: null,
      early_exit_sample_count: 0,
      early_exit_count: null,
      early_exit_rate: null,
      missed_profit_sample_count: 0,
      average_missed_profit: null,
      average_capture_pct: null,
      warnings: [],
    },
    breakdowns: [],
    links: {
      journal_trades_path: "/journal",
      journal_statistics_path: "/journal/statistics",
      journal_comparison_path: "/journal/comparison",
      backtests_path: "/strategy-lab",
      research_validation_path: "/research-validation",
      paper_validation_candidates_path: "/paper-validation/candidates",
    },
    confidence: "insufficient",
    warnings: [],
    max_rows: 5000,
    generated_at: "2026-07-25T12:00:00Z",
    note: "test",
  };
}

describe("comparisonTransforms", () => {
  it("marks insufficient cohorts and keeps null metrics unavailable", () => {
    const cohorts = buildComparisonCohorts(
      response([
        {
          cohort: "human",
          sample_count: 2,
          truncated: false,
          metrics: metrics({
            trade_count: 2,
            win_rate: 0.5,
            expectancy: null,
            average_r: null,
            profit_factor: null,
            confidence: "insufficient",
          }),
        },
        {
          cohort: "paper_system",
          sample_count: 20,
          truncated: false,
          metrics: metrics({
            trade_count: 20,
            win_rate: 0.6,
            expectancy: "1.25",
            average_r: 1.1,
            profit_factor: 1.4,
            confidence: "moderate",
          }),
        },
      ]),
    );

    expect(cohorts).toHaveLength(3);
    expect(cohorts.find((c) => c.cohort === "human")?.insufficient).toBe(true);
    expect(cohorts.find((c) => c.cohort === "backtest")?.sampleCount).toBe(0);
    expect(metricValue(cohorts.find((c) => c.cohort === "human")!, "expectancy")).toBeNull();
    expect(evidenceIsInsufficient(cohorts)).toBe(true);
  });

  it("requires enough evidence before comparison is conclusive", () => {
    const cohorts = buildComparisonCohorts(
      response([
        {
          cohort: "human",
          sample_count: 25,
          truncated: false,
          metrics: metrics({
            trade_count: 25,
            win_rate: 0.55,
            expectancy: "2",
            average_r: 1.2,
            profit_factor: 1.5,
            confidence: "moderate",
          }),
        },
        {
          cohort: "paper_system",
          sample_count: 30,
          truncated: false,
          metrics: metrics({
            trade_count: 30,
            win_rate: 0.5,
            expectancy: "1",
            average_r: 1.0,
            profit_factor: 1.2,
            confidence: "moderate",
          }),
        },
      ]),
    );
    expect(evidenceIsInsufficient(cohorts)).toBe(false);
  });
});
