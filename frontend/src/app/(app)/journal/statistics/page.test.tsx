import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import JournalStatisticsPage from "@/app/(app)/journal/statistics/page";
import type { JournalTradeStatsMetrics } from "@/lib/api/types";

const metrics = (overrides: Partial<JournalTradeStatsMetrics>): JournalTradeStatsMetrics => ({
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
});

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ health: null, providers: { providers: [] } }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      group_by: "setup_version",
      filters: {},
      overall: metrics({
        trade_count: 12,
        wins: 7,
        losses: 4,
        breakeven: 1,
        win_rate: 7 / 11,
        pnl_sample_count: 12,
        net_pnl_total: "420",
        expectancy: "35",
        profit_factor: 2.1,
        r_sample_count: 10,
        average_r: 0.8,
        confidence: "low",
        warnings: [
          {
            code: "low_sample",
            message: "Only 12 closed trade(s); treat these statistics as anecdotal.",
          },
        ],
      }),
      buckets: [
        {
          key: "11111111-1111-1111-1111-111111111111",
          group_id: "11111111-1111-1111-1111-111111111111",
          label: "Sweep reversal v2",
          metrics: metrics({
            trade_count: 8,
            wins: 5,
            losses: 3,
            win_rate: 5 / 8,
            pnl_sample_count: 8,
            net_pnl_total: "300",
            confidence: "low",
          }),
        },
      ],
      total_buckets: 1,
      limit: 20,
      offset: 0,
      truncated: false,
      max_rows: 5000,
      generated_at: "2026-07-24T10:00:00Z",
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("JournalStatisticsPage", () => {
  afterEach(() => cleanup());

  it("renders overall metrics, bucket cards, and warnings", () => {
    safetyPosture.executionMode = "paper";
    safetyPosture.realTradingEnabled = false;
    safetyPosture.postureKnown = true;
    render(<JournalStatisticsPage />);
    expect(screen.getByText("Journal statistics")).toBeInTheDocument();
    expect(screen.getByText("Overall (filtered)")).toBeInTheDocument();
    expect(screen.getByText("Sweep reversal v2")).toBeInTheDocument();
    expect(
      screen.getByText(/Only 12 closed trade\(s\); treat these statistics as anecdotal\./),
    ).toBeInTheDocument();
    expect(screen.getByText(/Setup version breakdown/)).toBeInTheDocument();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("fails closed when runtime safety is missing", () => {
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    safetyPosture.postureKnown = false;
    render(<JournalStatisticsPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });
});
