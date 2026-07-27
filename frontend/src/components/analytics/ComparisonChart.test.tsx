import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { JournalComparisonResponse, JournalTradeStatsMetrics } from "@/lib/api/types";

import { ComparisonChart } from "./ComparisonChart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function metrics(overrides: Partial<JournalTradeStatsMetrics> = {}): JournalTradeStatsMetrics {
  return {
    trade_count: 2,
    wins: 1,
    losses: 1,
    breakeven: 0,
    win_rate: 0.5,
    pnl_sample_count: 2,
    net_pnl_total: "0",
    gross_pnl_total: "0",
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

const insufficient: JournalComparisonResponse = {
  filters: {},
  cohorts: [
    {
      cohort: "human",
      sample_count: 2,
      truncated: false,
      metrics: metrics({ expectancy: null, profit_factor: null }),
    },
    {
      cohort: "paper_system",
      sample_count: 3,
      truncated: false,
      metrics: metrics({ win_rate: 0.3, expectancy: null }),
    },
  ],
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

describe("ComparisonChart", () => {
  afterEach(() => cleanup());

  it("mutes insufficient cohorts, suppresses verdict language, and keeps nulls unavailable", () => {
    render(<ComparisonChart source={ok(insufficient)} />);
    expect(screen.getByTestId("comparison-insufficient-note")).toHaveTextContent(
      /verdict language is suppressed/i,
    );
    expect(screen.queryByText(/\bHuman wins\b/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\bbest cohort\b/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("comparison-cohort-sample-human")).toHaveTextContent("n=2");
    expect(screen.getByTestId("comparison-drilldown-link")).toHaveAttribute(
      "href",
      "/journal/comparison",
    );
    const table = screen.getByTestId("comparison-a11y-table");
    expect(table).toHaveTextContent("—");
    expect(table.textContent).not.toMatch(/Expectancy\s*0(\.0+)?/);
  });
});
