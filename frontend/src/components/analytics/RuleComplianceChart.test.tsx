import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { JournalStatsResponse } from "@/lib/api/types";

const cellProps: Array<{ fill?: string; fillOpacity?: number }> = [];

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-container">{children}</div>
  ),
  BarChart: ({ children, data }: { children: React.ReactNode; data: unknown[] }) => (
    <div data-testid="recharts-bar-chart" data-rows={data.length}>{children}</div>
  ),
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Bar: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div data-testid="recharts-bar">{children}</div>,
  Cell: (props: { fill?: string; fillOpacity?: number }) => {
    cellProps.push({ fill: props.fill, fillOpacity: props.fillOpacity });
    return <div data-testid="recharts-cell" />;
  },
}));

import { RuleComplianceChart } from "./RuleComplianceChart";

function ok(data: JournalStatsResponse): SourceResult<JournalStatsResponse> {
  return { data, available: true, error: null, fallbackUsed: false };
}

const ruleComplianceData: JournalStatsResponse = {
  group_by: "rule_compliance",
  filters: {},
  overall: {
    trade_count: 3,
    wins: 2,
    losses: 1,
    breakeven: 0,
    win_rate: 0.67,
    pnl_sample_count: 3,
    net_pnl_total: "30",
    gross_pnl_total: "40",
    expectancy: "10",
    average_winner: "20",
    average_loser: "-10",
    profit_factor: 2,
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
    confidence: "moderate",
    warnings: [],
  },
  buckets: [
    {
      key: "compliant",
      group_id: "compliant",
      label: "Compliant",
      metrics: {
        trade_count: 6,
        wins: 4,
        losses: 2,
        breakeven: 0,
        win_rate: 0.67,
        pnl_sample_count: 6,
        net_pnl_total: "60",
        gross_pnl_total: "80",
        expectancy: "10",
        average_winner: "20",
        average_loser: "-10",
        profit_factor: 2,
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
        confidence: "moderate",
        warnings: [],
      },
    },
    {
      key: "partial",
      group_id: "partial",
      label: "Partial",
      metrics: {
        trade_count: 1,
        wins: 0,
        losses: 1,
        breakeven: 0,
        win_rate: 0,
        pnl_sample_count: 1,
        net_pnl_total: "-10",
        gross_pnl_total: "-10",
        expectancy: "-10",
        average_winner: null,
        average_loser: "-10",
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
        confidence: "insufficient",
        warnings: [],
      },
    },
  ],
  total_buckets: 2,
  limit: 20,
  offset: 0,
  truncated: false,
  max_rows: 5000,
  generated_at: "2026-07-25T12:05:00Z",
};

describe("RuleComplianceChart", () => {
  afterEach(() => {
    cleanup();
    cellProps.length = 0;
  });

  it("applies muted bar treatment for insufficient compliance buckets", () => {
    render(<RuleComplianceChart source={ok(ruleComplianceData)} />);

    expect(screen.getByTestId("rule-compliance-chart-plot")).toBeInTheDocument();
    expect(cellProps.some((cell) => cell.fill === "var(--color-text-muted)")).toBe(true);
    expect(cellProps.some((cell) => cell.fillOpacity === 0.45)).toBe(true);
    expect(cellProps.some((cell) => cell.fill === "var(--color-accent)")).toBe(true);
  });
});
