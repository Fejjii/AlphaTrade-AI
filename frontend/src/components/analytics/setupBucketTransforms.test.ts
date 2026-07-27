import { describe, expect, it } from "vitest";

import type { JournalStatsBucket, JournalTradeStatsMetrics } from "@/lib/api/types";

import {
  buildSetupBucketRows,
  visibleSetupChartRows,
} from "./setupBucketTransforms";
import { containsCurrencySymbol, formatMonetary } from "./format";

function metrics(
  overrides: Partial<JournalTradeStatsMetrics> = {},
): JournalTradeStatsMetrics {
  return {
    trade_count: 10,
    wins: 6,
    losses: 4,
    breakeven: 0,
    win_rate: 0.6,
    pnl_sample_count: 10,
    net_pnl_total: "100",
    gross_pnl_total: "120",
    expectancy: "10",
    average_winner: "20",
    average_loser: "-10",
    profit_factor: 2,
    r_sample_count: 8,
    average_r: 1.1,
    cost_sample_count: 10,
    fees_total: "1",
    funding_total: "0",
    slippage_total: "0",
    total_costs: "1",
    mfe_sample_count: 0,
    average_mfe_amount: null,
    mae_sample_count: 0,
    average_mae_amount: null,
    capture_sample_count: 0,
    available_profit_total: null,
    realized_on_available_total: null,
    average_realized_vs_available_pct: null,
    confidence: "moderate",
    warnings: [],
    ...overrides,
  };
}

function bucket(
  key: string,
  label: string,
  overrides: Partial<JournalTradeStatsMetrics> = {},
): JournalStatsBucket {
  return { key, label, group_id: key === "unassigned" ? null : key, metrics: metrics(overrides) };
}

describe("buildSetupBucketRows", () => {
  it("keeps unassigned last and insufficient after confident buckets", () => {
    const rows = buildSetupBucketRows([
      bucket("unassigned", "Unassigned", { trade_count: 50, confidence: "high" }),
      bucket("a", "Alpha", { trade_count: 3, confidence: "insufficient" }),
      bucket("b", "Beta", { trade_count: 20, confidence: "high" }),
    ]);
    expect(rows.map((row) => row.key)).toEqual(["b", "a", "unassigned"]);
  });

  it("preserves colliding display names as distinct identities", () => {
    const rows = buildSetupBucketRows([
      bucket("11111111-1111-1111-1111-111111111111", "Breakout"),
      bucket("22222222-2222-2222-2222-222222222222", "Breakout"),
    ]);
    expect(rows).toHaveLength(2);
    expect(rows[0]?.key).not.toBe(rows[1]?.key);
    expect(rows[0]?.displayLabel).not.toBe(rows[1]?.displayLabel);
    expect(rows[0]?.displayLabel).toContain("Breakout");
    expect(rows[1]?.displayLabel).toContain("Breakout");
  });

  it("marks null expectancy as no P&L data without coercing to zero", () => {
    const rows = buildSetupBucketRows([
      bucket("a", "Alpha", { expectancy: null, trade_count: 4, confidence: "insufficient" }),
    ]);
    expect(rows[0]?.noPnlData).toBe(true);
    expect(rows[0]?.expectancy).toBeNull();
    expect(rows[0]?.insufficient).toBe(true);
    expect(formatMonetary(rows[0]?.expectancy)).toBe("—");
    expect(containsCurrencySymbol(formatMonetary(12.5))).toBe(false);
  });
});

describe("visibleSetupChartRows", () => {
  it("caps mobile bars and discloses the remainder", () => {
    const rows = buildSetupBucketRows(
      Array.from({ length: 12 }, (_, index) =>
        bucket(`k${index}`, `Label ${index}`, { trade_count: 12 - index }),
      ),
    );
    const capped = visibleSetupChartRows(rows, false, 8);
    expect(capped.visible).toHaveLength(8);
    expect(capped.hiddenCount).toBe(4);
    expect(visibleSetupChartRows(rows, true, 8).hiddenCount).toBe(0);
  });
});
