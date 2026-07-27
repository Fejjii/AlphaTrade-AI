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
  buckets: [],
  total_buckets: 0,
  limit: 20,
  offset: 0,
  truncated: false,
  max_rows: 5000,
  generated_at: "2026-07-25T12:00:00Z",
};

const strategyItem = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Strat",
  setup_type: "breakout",
  current_version: 1,
  enabled: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function baseParams() {
  return buildSetupAnalyticsApiParams({
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
}

function mockJournalOk() {
  vi.mocked(api.journal.statistics).mockResolvedValue(journalResponse as never);
  vi.mocked(api.journal.setupEvidence).mockResolvedValue({
    items: [],
    generated_at: "2026-07-25T12:00:00Z",
    note: "n/a",
  } as never);
}

describe("useSetupAnalyticsSources", () => {
  afterEach(() => {
    vi.mocked(api.journal.statistics).mockReset();
    vi.mocked(api.journal.setupEvidence).mockReset();
    vi.mocked(api.strategies.list).mockReset();
    vi.mocked(api.performance.portfolio).mockReset();
  });

  it("loads journal statistics and setup-evidence without calling portfolio", async () => {
    mockJournalOk();
    vi.mocked(api.strategies.list).mockResolvedValue({
      items: [strategyItem],
      total: 1,
      limit: 200,
      offset: 0,
    } as never);

    const params = baseParams();
    const { result } = renderHook(() =>
      useSetupAnalyticsSources(params, { enabled: true }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    await waitFor(() => expect(result.current.strategiesLoaded).toBe(true));
    expect(api.journal.statistics).toHaveBeenCalledWith(
      expect.objectContaining({ group_by: "setup", setup_id: SETUP_UUID }),
    );
    expect(api.performance.portfolio).not.toHaveBeenCalled();
    expect(result.current.strategies[0]?.id).toBe(strategyItem.id);
  });

  it("exposes strategies loading separately from a confirmed empty list", async () => {
    mockJournalOk();
    let resolveStrategies!: (value: unknown) => void;
    const deferred = new Promise((resolve) => {
      resolveStrategies = resolve;
    });
    vi.mocked(api.strategies.list).mockReturnValue(deferred as never);

    const params = baseParams();
    const { result } = renderHook(() =>
      useSetupAnalyticsSources(params, { enabled: true }),
    );

    await waitFor(() => expect(result.current.strategiesLoading).toBe(true));
    expect(result.current.strategiesLoaded).toBe(false);
    expect(result.current.strategies).toEqual([]);

    await act(async () => {
      resolveStrategies({ items: [], total: 0, limit: 200, offset: 0 });
      await deferred;
    });
    await waitFor(() => expect(result.current.strategiesLoading).toBe(false));
    expect(result.current.strategiesLoaded).toBe(true);
    expect(result.current.strategies).toEqual([]);
  });

  it("exposes strategies failure and retry success without collapsing journal data", async () => {
    mockJournalOk();
    vi.mocked(api.strategies.list).mockRejectedValue(new Error("strategies down"));

    const params = baseParams();
    const { result } = renderHook(() =>
      useSetupAnalyticsSources(params, { enabled: true }),
    );

    await waitFor(() => expect(result.current.strategiesError).toBe("strategies down"));
    expect(result.current.journal?.available).toBe(true);
    expect(result.current.strategiesLoaded).toBe(false);

    vi.mocked(api.strategies.list).mockResolvedValue({
      items: [strategyItem],
      total: 1,
      limit: 200,
      offset: 0,
    } as never);

    await act(async () => {
      await result.current.reloadStrategies();
    });
    await waitFor(() => expect(result.current.strategiesError).toBeNull());
    expect(result.current.strategies).toHaveLength(1);
    expect(result.current.strategiesLoaded).toBe(true);
    expect(result.current.journal?.available).toBe(true);
  });

  it("prevents concurrent duplicate strategy-list requests while in flight", async () => {
    mockJournalOk();
    let resolveStrategies!: (value: unknown) => void;
    const deferred = new Promise((resolve) => {
      resolveStrategies = resolve;
    });
    vi.mocked(api.strategies.list).mockReturnValue(deferred as never);

    const params = baseParams();
    const { result } = renderHook(() =>
      useSetupAnalyticsSources(params, { enabled: true }),
    );

    await waitFor(() => expect(result.current.strategiesLoading).toBe(true));
    const callsAfterStart = vi.mocked(api.strategies.list).mock.calls.length;

    await act(async () => {
      void result.current.reloadStrategies();
      void result.current.reloadStrategies();
    });

    expect(vi.mocked(api.strategies.list).mock.calls.length).toBe(callsAfterStart);

    await act(async () => {
      resolveStrategies({ items: [strategyItem], total: 1, limit: 200, offset: 0 });
      await deferred;
    });
    await waitFor(() => expect(result.current.strategiesLoaded).toBe(true));
  });

  it("does not fetch when disabled", async () => {
    mockJournalOk();
    vi.mocked(api.strategies.list).mockResolvedValue({
      items: [],
      total: 0,
      limit: 200,
      offset: 0,
    } as never);

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
    expect(api.strategies.list).not.toHaveBeenCalled();
  });
});
