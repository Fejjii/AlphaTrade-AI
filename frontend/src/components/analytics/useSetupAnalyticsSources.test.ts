import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { buildSetupAnalyticsApiParams } from "./filterValidation";
import { useSetupAnalyticsSources } from "./useSetupAnalyticsSources";

vi.mock("@/lib/api", () => ({
  api: {
    journal: {
      statistics: vi.fn(),
      setupEvidence: vi.fn(),
    },
    strategies: {
      list: vi.fn(),
    },
    performance: {
      portfolio: vi.fn(),
    },
  },
}));

const SETUP_UUID = "11111111-1111-1111-1111-111111111111";

const journalResponse = {
  group_by: "setup" as const,
  filters: { setup_id: SETUP_UUID },
  overall: {
    trade_count: 2,
    wins: 1,
    losses: 1,
    breakeven: 0,
    win_rate: 0.5,
    pnl_sample_count: 2,
    net_pnl_total: "10",
    gross_pnl_total: "12",
    expectancy: "5",
    average_winner: "10",
    average_loser: "-5",
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
    confidence: "low" as const,
    warnings: [],
  },
  buckets: [
    {
      key: SETUP_UUID,
      group_id: SETUP_UUID,
      label: "Breakout",
      metrics: {
        trade_count: 2,
        wins: 1,
        losses: 1,
        breakeven: 0,
        win_rate: 0.5,
        pnl_sample_count: 2,
        net_pnl_total: "10",
        gross_pnl_total: "12",
        expectancy: "5",
        average_winner: "10",
        average_loser: "-5",
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
        confidence: "low" as const,
        warnings: [],
      },
    },
  ],
  total_buckets: 1,
  limit: 20,
  offset: 0,
  truncated: false,
  max_rows: 5000,
  generated_at: "2026-07-25T12:00:00Z",
};

describe("useSetupAnalyticsSources", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads journal statistics and setup-evidence without calling portfolio", async () => {
    vi.mocked(api.journal.statistics).mockResolvedValue(journalResponse as never);
    vi.mocked(api.journal.setupEvidence).mockResolvedValue({
      items: [],
      generated_at: "2026-07-25T12:00:00Z",
      note: "n/a",
    } as never);
    vi.mocked(api.strategies.list).mockResolvedValue({
      items: [
        {
          id: "22222222-2222-2222-2222-222222222222",
          name: "Strat",
          setup_type: "breakout",
          current_version: 1,
          enabled: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    } as never);

    const params = buildSetupAnalyticsApiParams({
      tab: "setups",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      setupId: SETUP_UUID,
      userStrategyId: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });

    const { result } = renderHook(() =>
      useSetupAnalyticsSources(params, { enabled: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(api.journal.statistics).toHaveBeenCalledWith(
      expect.objectContaining({ group_by: "setup", setup_id: SETUP_UUID }),
    );
    expect(api.journal.setupEvidence).toHaveBeenCalledWith(
      expect.objectContaining({ setup_id: SETUP_UUID }),
    );
    expect(api.performance.portfolio).not.toHaveBeenCalled();
    expect(result.current.journal?.available).toBe(true);
    expect(result.current.strategies[0]?.id).toBe("22222222-2222-2222-2222-222222222222");
  });

  it("does not fetch when disabled", async () => {
    const params = buildSetupAnalyticsApiParams({
      tab: "overview",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      setupId: null,
      userStrategyId: null,
      groupBy: "setup",
      bucketOffset: 0,
      ignoredParams: [],
    });
    renderHook(() => useSetupAnalyticsSources(params, { enabled: false }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(api.journal.statistics).not.toHaveBeenCalled();
    expect(api.journal.setupEvidence).not.toHaveBeenCalled();
  });
});
