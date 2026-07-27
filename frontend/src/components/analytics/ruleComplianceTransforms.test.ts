import { describe, expect, it } from "vitest";

import type { JournalStatsResponse } from "@/lib/api/types";

import { buildRuleComplianceRows, totalRuleComplianceSample } from "./ruleComplianceTransforms";

function metrics(tradeCount: number, winRate: number | null = 0.5, expectancy: string | null = "1.5") {
  return {
    trade_count: tradeCount,
    wins: 0,
    losses: 0,
    breakeven: 0,
    win_rate: winRate,
    pnl_sample_count: tradeCount,
    net_pnl_total: "0",
    gross_pnl_total: "0",
    expectancy,
    average_winner: null,
    average_loser: null,
    profit_factor: null,
    r_sample_count: 0,
    average_r: null,
    cost_sample_count: 0,
    fees_total: "0",
    funding_total: "0",
    slippage_total: "0",
    total_costs: "0",
    mfe_sample_count: 0,
    average_mfe_amount: null,
    mae_sample_count: 0,
    average_mae_amount: null,
    capture_sample_count: 0,
    available_profit_total: null,
    realized_on_available_total: null,
    average_realized_vs_available_pct: null,
    confidence: tradeCount < 5 ? ("insufficient" as const) : ("moderate" as const),
    warnings: [],
  };
}

describe("buildRuleComplianceRows", () => {
  it("always includes assessed and unassessed buckets with sample counts", () => {
    const response: JournalStatsResponse = {
      group_by: "rule_compliance",
      filters: {},
      overall: metrics(10),
      buckets: [
        { key: "compliant", label: "compliant", metrics: metrics(4, 0.75, "2.0") },
        { key: "violated", label: "violated", metrics: metrics(2, 0.0, "-1.0") },
      ],
      total_buckets: 2,
      limit: 20,
      offset: 0,
      truncated: false,
      max_rows: 5000,
      generated_at: "2026-07-25T12:00:00Z",
    };

    const rows = buildRuleComplianceRows(response);
    expect(rows.map((row) => row.key)).toEqual([
      "compliant",
      "partial",
      "violated",
      "unassessed",
    ]);
    expect(rows.find((row) => row.key === "unassessed")?.tradeCount).toBe(0);
    expect(rows.find((row) => row.key === "partial")?.tradeCount).toBe(0);
    expect(totalRuleComplianceSample(rows)).toBe(6);
    expect(rows.find((row) => row.key === "compliant")?.expectancy).toBe(2);
  });

  it("keeps null expectancy as null rather than zero", () => {
    const response: JournalStatsResponse = {
      group_by: "rule_compliance",
      filters: {},
      overall: metrics(3, null, null),
      buckets: [
        { key: "unassessed", label: "unassessed", metrics: metrics(3, null, null) },
      ],
      total_buckets: 1,
      limit: 20,
      offset: 0,
      truncated: false,
      max_rows: 5000,
      generated_at: "2026-07-25T12:00:00Z",
    };
    const rows = buildRuleComplianceRows(response);
    const unassessed = rows.find((row) => row.key === "unassessed");
    expect(unassessed?.winRate).toBeNull();
    expect(unassessed?.expectancy).toBeNull();
  });
});
