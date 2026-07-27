import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { buildFilterKey, type AnalyticsFilterParams } from "./filterValidation";
import { useAnalyticsSources } from "./useAnalyticsSources";

vi.mock("@/lib/api", () => ({
  api: {
    journal: { statistics: vi.fn() },
    performance: { portfolio: vi.fn() },
  },
}));

const journalResponse = {
  group_by: "overall" as const,
  filters: {},
  overall: {
    trade_count: 1,
    wins: 1,
    losses: 0,
    breakeven: 0,
    win_rate: 1,
    pnl_sample_count: 1,
    net_pnl_total: "10",
    gross_pnl_total: "10",
    expectancy: "10",
    average_winner: "10",
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
    confidence: "insufficient" as const,
    warnings: [],
  },
  buckets: [],
  total_buckets: 0,
  limit: 50,
  offset: 0,
  truncated: false,
  max_rows: 5000,
  generated_at: "2026-07-25T12:00:00Z",
};

const portfolioResponse = {
  safety: {
    execution_mode: "paper",
    paper_only: true,
    real_trading_enabled: false,
    disclaimer: "Paper only",
  },
  account: {
    starting_balance: "10000",
    current_equity: "10010",
    cumulative_realized_pnl: "10",
    unrealized_pnl: "0",
    open_trade_count: 0,
    closed_trade_count: 1,
    as_of: "2026-07-25T12:00:00Z",
    limitations: [],
  },
  metrics: {
    trade_count: 1,
    wins: 1,
    losses: 0,
    breakeven: 0,
    win_rate: 1,
    net_pnl: "10",
    gross_profit: "10",
    gross_loss: "0",
    total_fees: "0",
    total_funding: "0",
    avg_win: "10",
    avg_loss: "0",
    expectancy: "10",
    profit_factor: null,
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
  equity_curve: [],
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
    label: "flat" as const,
    window_days: 30,
    recent_net_pnl: "0",
    prior_net_pnl: "0",
    rationale: "Flat",
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
};

const defaultParams: AnalyticsFilterParams = {
  journal: { group_by: "overall" as const },
  portfolio: { timezone: "UTC" },
  state: {
    tab: "overview" as const,
    dateFrom: null,
    dateTo: null,
    symbol: null,
    timeframe: null,
    portfolioSource: null,
    journalSource: null,
    setupId: null,
    userStrategyId: null,
    groupBy: "setup" as const,
    bucketOffset: 0,
    ignoredParams: [],
  },
};

function paramsForSymbol(symbol: string | null): AnalyticsFilterParams {
  return {
    journal: { group_by: "overall" as const, ...(symbol ? { symbol } : {}) },
    portfolio: { timezone: "UTC", ...(symbol ? { symbol } : {}) },
    state: {
      tab: "overview" as const,
      dateFrom: null,
      dateTo: null,
      symbol,
      timeframe: null,
      portfolioSource: null,
    journalSource: null,
      setupId: null,
      userStrategyId: null,
      groupBy: "setup" as const,
      bucketOffset: 0,
      ignoredParams: [],
    },
  };
}

describe("useAnalyticsSources", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("drops stale responses when a newer filter request resolves first", async () => {
    let resolveSlow: (value: unknown) => void = () => undefined;
    const slow = new Promise((resolve) => {
      resolveSlow = resolve;
    });

    vi.mocked(api.journal.statistics)
      .mockReturnValueOnce(slow as never)
      .mockResolvedValue(journalResponse as never);
    vi.mocked(api.performance.portfolio).mockResolvedValue(portfolioResponse as never);

    const btcParams = paramsForSymbol("BTCUSDT");
    const ethParams = paramsForSymbol("ETHUSDT");

    const { result, rerender } = renderHook(
      ({ params }) => useAnalyticsSources(params),
      { initialProps: { params: btcParams } },
    );

    rerender({ params: ethParams });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.journal?.data).toBeTruthy();
    expect(api.journal.statistics).toHaveBeenLastCalledWith(
      expect.objectContaining({ symbol: "ETHUSDT" }),
    );

    await act(async () => {
      resolveSlow(journalResponse);
      await slow;
    });

    expect(result.current.journal?.data).toBeTruthy();
    expect(result.current.loadedFilterKey).toBe(buildFilterKey(ethParams));
  });

  it("clears displayed data while a new filter loads", async () => {
    vi.mocked(api.journal.statistics).mockResolvedValue(journalResponse as never);
    vi.mocked(api.performance.portfolio).mockResolvedValue(portfolioResponse as never);

    const { result, rerender } = renderHook(
      ({ params }: { params: AnalyticsFilterParams }) => useAnalyticsSources(params),
      { initialProps: { params: defaultParams } },
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.journal).not.toBeNull();

    rerender({ params: paramsForSymbol("BTCUSDT") });
    expect(result.current.loading).toBe(true);
    expect(result.current.journal).toBeNull();
  });

  it("supports manual retry on the current filter key", async () => {
    vi.mocked(api.journal.statistics).mockResolvedValue(journalResponse as never);
    vi.mocked(api.performance.portfolio).mockResolvedValue(portfolioResponse as never);

    const { result } = renderHook(() => useAnalyticsSources(defaultParams));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.reload();
    });

    expect(api.journal.statistics).toHaveBeenCalledTimes(2);
    expect(result.current.loadedFilterKey).toBe(buildFilterKey(defaultParams));
  });

  it("reports partial source behavior honestly", async () => {
    vi.mocked(api.journal.statistics).mockRejectedValue(new Error("journal down"));
    vi.mocked(api.performance.portfolio).mockResolvedValue(portfolioResponse as never);

    const { result } = renderHook(() => useAnalyticsSources(defaultParams));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.partialData).toBe(true);
    expect(result.current.journal?.available).toBe(false);
    expect(result.current.portfolio?.available).toBe(true);
  });
});
