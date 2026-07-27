import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OverviewStats } from "./OverviewStats";
import type { JournalStatsResponse, PaperPortfolioResponse } from "@/lib/api/types";
import type { SourceResult } from "@/components/workflows";

function okJournal(overrides?: Partial<JournalStatsResponse["overall"]>): SourceResult<JournalStatsResponse> {
  return {
    available: true,
    error: null,
    fallbackUsed: false,
    data: {
      group_by: "overall",
      filters: {},
      overall: {
        trade_count: 5,
        wins: 3,
        losses: 2,
        breakeven: 0,
        win_rate: 0.6,
        pnl_sample_count: 5,
        net_pnl_total: null,
        gross_pnl_total: "100",
        expectancy: null,
        average_winner: "40",
        average_loser: "-20",
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
        confidence: "moderate",
        warnings: [],
        ...overrides,
      },
      buckets: [],
      total_buckets: 0,
      limit: 50,
      offset: 0,
      truncated: false,
      max_rows: 5000,
      generated_at: "2026-07-25T12:00:00Z",
    },
  };
}

const portfolioOk: SourceResult<PaperPortfolioResponse> = {
  available: true,
  error: null,
  fallbackUsed: false,
  data: {
    safety: {
      execution_mode: "paper",
      paper_only: true,
      real_trading_enabled: false,
      disclaimer: "Paper only",
    },
    account: {
      starting_balance: "10000",
      current_equity: "10150",
      cumulative_realized_pnl: "150",
      unrealized_pnl: "0",
      open_trade_count: 0,
      closed_trade_count: 5,
      as_of: "2026-07-25T12:00:00Z",
      limitations: [],
    },
    metrics: {
      trade_count: 5,
      wins: 3,
      losses: 2,
      breakeven: 0,
      win_rate: 0.6,
      net_pnl: "150",
      gross_profit: "200",
      gross_loss: "-50",
      total_fees: "0",
      total_funding: "0",
      avg_win: "40",
      avg_loss: "-20",
      expectancy: "30",
      profit_factor: 2,
      avg_r_multiple: null,
      max_drawdown: "0",
      max_drawdown_pct: 0,
      avg_duration_seconds: null,
      violations: 0,
      equity_curve: [],
    },
    open_exposure: {
      open_trade_count: 0,
      proposal_flow_count: 0,
      paper_validation_count: 0,
      unrealized_pnl_total: "0",
      notional_exposure: "0",
      limitations: [],
    },
    equity_curve: [
      {
        index: 0,
        timestamp: "2026-07-01T00:00:00Z",
        equity: "10000",
        cumulative_realized_pnl: "0",
        unrealized_pnl: "0",
        event: "start",
      },
    ],
    daily_series: [],
    breakdowns: {
      by_symbol: [],
      by_setup: [],
      by_timeframe: [],
      by_strategy: [],
      by_source: [],
      by_detector: [],
    },
    trend: {
      label: "insufficient_data",
      window_days: 30,
      recent_net_pnl: null,
      prior_net_pnl: null,
      rationale: "Not enough data",
    },
    date_range: null,
    filters_applied: {
      start_date: null,
      end_date: null,
      source: "all",
      symbol: null,
      setup: null,
      timeframe: null,
      timezone: "UTC",
    },
  },
};

describe("OverviewStats metric honesty", () => {
  afterEach(() => cleanup());

  it("keeps null journal metrics as unavailable when portfolio is also available", () => {
    render(<OverviewStats journal={okJournal()} portfolio={portfolioOk} />);
    expect(screen.getByTestId("overview-tile-realised-p&l")).toHaveTextContent("—");
    expect(screen.getByTestId("overview-source-Realised P&L")).toHaveTextContent(
      "Journal statistics",
    );
    expect(screen.getByTestId("overview-source-Realised P&L")).not.toHaveTextContent("fallback");
    expect(screen.getByTestId("overview-tile-trend")).toHaveTextContent("Insufficient data");
  });

  it("labels portfolio fallback tiles when journal is unavailable", () => {
    render(
      <OverviewStats
        journal={{ available: false, data: null, error: "down", fallbackUsed: false }}
        portfolio={portfolioOk}
      />,
    );
    expect(screen.getByTestId("overview-source-Realised P&L")).toHaveTextContent(
      "Paper portfolio (fallback)",
    );
  });
});
