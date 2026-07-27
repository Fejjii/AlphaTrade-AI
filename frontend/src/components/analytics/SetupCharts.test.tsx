import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { JournalStatsResponse, SetupEvidenceResponse } from "@/lib/api/types";

import { SetupBucketTable } from "./SetupBucketTable";
import { SetupExpectancyChart } from "./SetupExpectancyChart";
import { SetupWinRateChart } from "./SetupWinRateChart";
import { containsCurrencySymbol } from "./format";

function metrics(overrides: Partial<JournalStatsResponse["overall"]> = {}) {
  return {
    trade_count: 12,
    wins: 7,
    losses: 5,
    breakeven: 0,
    win_rate: 0.5833,
    pnl_sample_count: 12,
    net_pnl_total: "150.25",
    gross_pnl_total: "200.00",
    expectancy: "12.52",
    average_winner: "40.00",
    average_loser: "-20.00",
    profit_factor: 1.6,
    r_sample_count: 10,
    average_r: 1.2,
    cost_sample_count: 12,
    fees_total: "5.00",
    funding_total: "0",
    slippage_total: "0",
    total_costs: "5.00",
    mfe_sample_count: 0,
    average_mfe_amount: null,
    mae_sample_count: 0,
    average_mae_amount: null,
    capture_sample_count: 0,
    available_profit_total: null,
    realized_on_available_total: null,
    average_realized_vs_available_pct: null,
    confidence: "moderate" as const,
    warnings: [],
    ...overrides,
  };
}

const SETUP_A = "11111111-1111-1111-1111-111111111111";
const SETUP_B = "22222222-2222-2222-2222-222222222222";

const journalData: JournalStatsResponse = {
  group_by: "setup",
  filters: {},
  overall: metrics(),
  buckets: [
    {
      key: SETUP_A,
      group_id: SETUP_A,
      label: "Breakout",
      metrics: metrics({ trade_count: 8, win_rate: 0.75, expectancy: "15.00", confidence: "high" }),
    },
    {
      key: SETUP_B,
      group_id: SETUP_B,
      label: "Breakout",
      metrics: metrics({
        trade_count: 3,
        win_rate: 0.33,
        expectancy: null,
        confidence: "insufficient",
      }),
    },
    {
      key: "unassigned",
      group_id: null,
      label: "Unassigned",
      metrics: metrics({ trade_count: 1, win_rate: 0, expectancy: "-5.00", confidence: "insufficient" }),
    },
  ],
  total_buckets: 3,
  limit: 20,
  offset: 0,
  truncated: true,
  max_rows: 5000,
  generated_at: "2026-07-25T12:00:00Z",
};

const evidenceData: SetupEvidenceResponse = {
  items: [
    {
      strategy_id: "33333333-3333-3333-3333-333333333333",
      strategy_version_id: "44444444-4444-4444-4444-444444444444",
      strategy_name: "Breakout",
      version: 2,
      tier: "tier2",
      measured: {
        oos_trade_count: 12,
        oos_profit_factor: 1.4,
        oos_expectancy: "3.50",
        confirm_trade_count: 4,
        confirm_expectancy: null,
        total_backtest_trades: 40,
      },
      thresholds: {
        tier1_oos_min_trades: 30,
        tier1_oos_min_profit_factor: 1.2,
        tier1_min_confirm_trades: 10,
        tier2_min_trades: 10,
        tier2_oos_min_trades: 10,
        tier2_oos_min_profit_factor: 1.1,
      },
      note: "Evidence note",
    },
  ],
  generated_at: "2026-07-25T12:00:00Z",
  note: "Paper evidence only",
};

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

describe("Setup analytics charts", () => {
  afterEach(() => cleanup());

  it("renders win-rate chart with provenance, unassigned, and insufficient muting", () => {
    render(
      <SetupWinRateChart
        source={ok(journalData)}
        filtersSummary="dates all time · group setup"
      />,
    );
    expect(screen.getByTestId("setup-win-rate-chart-source")).toHaveTextContent(
      "/journal/statistics",
    );
    expect(screen.getByTestId("setup-win-rate-chart-sample")).toHaveTextContent("n=12");
    expect(screen.getByTestId("setup-win-rate-chart-plot")).toHaveAttribute("role", "img");
    expect(screen.getByTestId(`setup-win-rate-row-${SETUP_B}`)).toHaveTextContent(/insufficient/i);
    expect(screen.getByTestId("setup-win-rate-row-unassigned")).toBeInTheDocument();
    expect(screen.getByTestId("setup-win-rate-a11y-table")).toBeInTheDocument();
    expect(screen.queryByText(/best setup|guaranteed|outperform/i)).not.toBeInTheDocument();
  });

  it("renders null expectancy as No P&L data and never fabricates zero bars on error", () => {
    render(<SetupExpectancyChart source={ok(journalData)} />);
    expect(screen.getByTestId(`setup-expectancy-row-${SETUP_B}`)).toHaveTextContent("No P&L data");
    const monetary = screen.getByTestId(`setup-expectancy-row-${SETUP_A}`).textContent ?? "";
    expect(containsCurrencySymbol(monetary)).toBe(false);

    cleanup();
    render(<SetupExpectancyChart source={failed("journal down")} />);
    expect(screen.getByTestId("setup-expectancy-chart-error")).toBeInTheDocument();
    expect(screen.queryByTestId("setup-expectancy-chart-plot")).not.toBeInTheDocument();
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
  });

  it("shows truncated pager disclosure and keyboard-operable pagination", () => {
    const onPageChange = vi.fn();
    const paged: JournalStatsResponse = {
      ...journalData,
      total_buckets: 45,
      limit: 20,
      offset: 20,
    };
    render(
      <SetupBucketTable
        source={ok(paged)}
        evidence={ok(evidenceData)}
        groupBy="setup"
        bucketOffset={20}
        onPageChange={onPageChange}
      />,
    );
    expect(screen.getByTestId("setup-bucket-pager")).toHaveTextContent(/Showing 21–40 of 45/);
    expect(screen.getByTestId("setup-bucket-table")).toHaveTextContent(/Truncated coverage|oldest 5000/i);
    fireEvent.click(screen.getByTestId("setup-bucket-prev"));
    expect(onPageChange).toHaveBeenCalledWith(0);
    fireEvent.click(screen.getByTestId("setup-bucket-next"));
    expect(onPageChange).toHaveBeenCalledWith(40);
    expect(screen.getByTestId("setup-evidence-panel")).toHaveTextContent("Breakout");
    expect(screen.getByTestId(`setup-bucket-stats-link-${SETUP_A}`)).toHaveAttribute(
      "href",
      expect.stringContaining(`setup_id=${SETUP_A}`),
    );
  });

  it("keeps colliding labels distinct by journal key in the table", () => {
    render(
      <SetupBucketTable
        source={ok(journalData)}
        evidence={failed("evidence down")}
        groupBy="setup"
        bucketOffset={0}
        onPageChange={vi.fn()}
      />,
    );
    const table = screen.getByTestId("setup-bucket-data-table");
    expect(within(table).getByText(SETUP_A)).toBeInTheDocument();
    expect(within(table).getByText(SETUP_B)).toBeInTheDocument();
    expect(screen.getByTestId("setup-evidence-panel")).toHaveTextContent(/unavailable/i);
  });

  it("shows loading skeleton without empty state", () => {
    render(<SetupWinRateChart source={null} loading />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByText(/No closed trades/i)).not.toBeInTheDocument();
  });
});
