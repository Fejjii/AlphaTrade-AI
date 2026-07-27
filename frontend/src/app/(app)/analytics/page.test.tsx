import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "@/app/(app)/analytics/page";
import { DailyPnlChart } from "@/components/analytics/DailyPnlChart";
import { CumulativePnlChart } from "@/components/analytics/CumulativePnlChart";
import type { JournalStatsResponse, PaperPortfolioResponse } from "@/lib/api/types";
import type { SourceResult } from "@/components/workflows";
import type { AnalyticsFilterState } from "@/components/analytics/useAnalyticsFilters";

const mockReload = vi.fn();
const mockSetTab = vi.fn();
const mockApplyDraft = vi.fn();
const mockApplyPreset = vi.fn();
const mockClear = vi.fn();
const mockCleanup = vi.fn();

const journalData: JournalStatsResponse = {
  group_by: "overall",
  filters: {},
  overall: {
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
    confidence: "moderate",
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

const portfolioData: PaperPortfolioResponse = {
  safety: {
    execution_mode: "paper",
    paper_only: true,
    real_trading_enabled: false,
    disclaimer: "Paper only",
  },
  account: {
    starting_balance: "10000",
    current_equity: "10150.25",
    cumulative_realized_pnl: "150.25",
    unrealized_pnl: "0",
    open_trade_count: 0,
    closed_trade_count: 12,
    as_of: "2026-07-25T12:00:00Z",
    limitations: [],
  },
  metrics: {
    trade_count: 12,
    wins: 7,
    losses: 5,
    breakeven: 0,
    win_rate: 0.5833,
    net_pnl: "150.25",
    gross_profit: "200",
    gross_loss: "-50",
    total_fees: "5",
    total_funding: "0",
    avg_win: "40",
    avg_loss: "-20",
    expectancy: "12.52",
    profit_factor: 1.6,
    avg_r_multiple: 1.2,
    max_drawdown: "25",
    max_drawdown_pct: 0.0025,
    avg_duration_seconds: 3600,
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
    {
      index: 1,
      timestamp: "2026-07-25T12:00:00Z",
      equity: "10150.25",
      cumulative_realized_pnl: "150.25",
      unrealized_pnl: "0",
      event: "trade_close",
    },
  ],
  daily_series: [
    {
      date: "2026-07-25",
      starting_equity: "10000",
      ending_equity: "10150.25",
      daily_pnl: "150.25",
      daily_drawdown: "0",
      daily_drawdown_pct: 0,
      trades_closed: 12,
    },
  ],
  breakdowns: {
    by_symbol: [],
    by_setup: [],
    by_timeframe: [],
    by_strategy: [],
    by_source: [],
    by_detector: [],
  },
  trend: {
    label: "improving",
    window_days: 30,
    recent_net_pnl: "150.25",
    prior_net_pnl: "0",
    rationale: "Recent window positive",
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

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

let filterState: AnalyticsFilterState = {
  tab: "overview",
  dateFrom: null,
  dateTo: null,
  symbol: null,
  timeframe: null,
  portfolioSource: null,
  ignoredParams: [],
};

let sourcesState = {
  journal: ok(journalData),
  portfolio: ok(portfolioData),
  loading: false,
  bothFailed: false,
  partialData: false,
  loadedFilterKey: "key",
};

vi.mock("@/components/analytics/useAnalyticsFilters", () => ({
  useAnalyticsFilters: () => ({
    state: filterState,
    apiParams: { journal: { group_by: "overall" }, portfolio: { timezone: "UTC" }, state: filterState },
    setTab: mockSetTab,
    applyDraft: mockApplyDraft,
    applyDatePreset: mockApplyPreset,
    clearFilters: mockClear,
    cleanupIgnoredParams: mockCleanup,
  }),
  buildAnalyticsApiParams: vi.fn(),
}));

vi.mock("@/components/analytics/useAnalyticsSources", () => ({
  useAnalyticsSources: () => ({
    ...sourcesState,
    reload: mockReload,
  }),
}));

vi.mock("@/components/analytics/AnalyticsCharts", () => ({
  DailyPnlChart: (props: ComponentProps<typeof DailyPnlChart>) => <DailyPnlChart {...props} />,
  CumulativePnlChart: (props: ComponentProps<typeof CumulativePnlChart>) => (
    <CumulativePnlChart {...props} />
  ),
}));

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    providerMode: "fallback",
  }),
  useAppContext: () => ({ health: { version: "test" } }),
}));

describe("AnalyticsPage PR1", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    filterState = {
      tab: "overview",
      dateFrom: null,
      dateTo: null,
      symbol: null,
      timeframe: null,
      portfolioSource: null,
      ignoredParams: [],
    };
    sourcesState = {
      journal: ok(journalData),
      portfolio: ok(portfolioData),
      loading: false,
      bothFailed: false,
      partialData: false,
      loadedFilterKey: "key",
    };
    vi.clearAllMocks();
  });

  it("renders overview stats from available sources", () => {
    render(<AnalyticsPage />);
    expect(screen.getByTestId("analytics-page")).toBeInTheDocument();
    expect(screen.getByTestId("overview-stats")).toBeInTheDocument();
    expect(screen.getByText("Realised P&L")).toBeInTheDocument();
    expect(screen.getByTestId("overview-tile-trend")).toHaveTextContent("Improving");
  });

  it("shows partial banner when one source fails", () => {
    sourcesState = {
      journal: failed("journal down"),
      portfolio: ok(portfolioData),
      loading: false,
      bothFailed: false,
      partialData: true,
      loadedFilterKey: "key",
    };
    render(<AnalyticsPage />);
    expect(screen.getByTestId("analytics-partial-data")).toHaveTextContent(/partial analytics data/i);
    expect(screen.getByTestId("overview-journal-error")).toBeInTheDocument();
  });

  it("shows full error when both sources fail", () => {
    sourcesState = {
      journal: failed(),
      portfolio: failed(),
      loading: false,
      bothFailed: true,
      partialData: false,
      loadedFilterKey: "key",
    };
    render(<AnalyticsPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent(/both failed/i);
    expect(screen.queryByTestId("overview-stats")).not.toBeInTheDocument();
  });

  it("renders performance charts without zero fabrication on portfolio failure", () => {
    filterState = { ...filterState, tab: "performance" };
    sourcesState = {
      journal: ok(journalData),
      portfolio: failed("portfolio down"),
      loading: false,
      bothFailed: false,
      partialData: true,
      loadedFilterKey: "key",
    };
    render(<AnalyticsPage />);
    expect(screen.getByTestId("daily-pnl-chart-error")).toBeInTheDocument();
    expect(screen.getByTestId("cumulative-pnl-chart-error")).toBeInTheDocument();
    expect(screen.queryByTestId("daily-pnl-chart-plot")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cumulative-pnl-chart-plot")).not.toBeInTheDocument();
  });

  it("wires tab aria-controls to tabpanels and aria-labelledby back to tabs", () => {
    render(<AnalyticsPage />);
    const tablist = screen.getByRole("tablist", { name: "Analytics sections" });
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs).toHaveLength(2);
    for (const tab of tabs) {
      const panelId = tab.getAttribute("aria-controls");
      expect(panelId).toBeTruthy();
      const panel = document.getElementById(panelId!);
      expect(panel).toBeTruthy();
      expect(panel).toHaveAttribute("role", "tabpanel");
      expect(panel?.getAttribute("aria-labelledby")).toBe(tab.id);
      expect(panel?.hasAttribute("hidden")).toBe(tab.getAttribute("aria-selected") !== "true");
    }
  });

  it("uses filter bar actions", () => {
    render(<AnalyticsPage />);
    fireEvent.click(screen.getByTestId("analytics-preset-30d"));
    expect(mockApplyPreset).toHaveBeenCalledWith("30d");
    fireEvent.click(screen.getByTestId("analytics-clear-filters"));
    expect(mockClear).toHaveBeenCalled();
  });

  it("shows tab-level stale state on overview when all available sources are stale", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-25T12:00:00Z"));
    sourcesState = {
      journal: ok({ ...journalData, generated_at: "2026-07-25T11:00:00Z" }),
      portfolio: ok({
        ...portfolioData,
        account: { ...portfolioData.account, as_of: "2026-07-25T11:00:00Z" },
      }),
      loading: false,
      bothFailed: false,
      partialData: false,
      loadedFilterKey: "key",
    };
    render(<AnalyticsPage />);
    expect(screen.getByTestId("overview-stale-state")).toHaveTextContent(/stale for this view/i);
    vi.useRealTimers();
  });

  it("treats future-skewed portfolio as unavailable on performance tab", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-25T12:00:00Z"));
    filterState = { ...filterState, tab: "performance" };
    sourcesState = {
      journal: ok(journalData),
      portfolio: ok({
        ...portfolioData,
        account: { ...portfolioData.account, as_of: "2026-07-25T12:05:00Z" },
      }),
      loading: false,
      bothFailed: false,
      partialData: false,
      loadedFilterKey: "key",
    };
    render(<AnalyticsPage />);
    expect(screen.getByTestId("daily-pnl-chart-error")).toHaveTextContent(/clock-skewed/i);
    expect(screen.getByTestId("cumulative-pnl-chart-error")).toHaveTextContent(/clock-skewed/i);
    expect(screen.queryByTestId("daily-pnl-chart-plot")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cumulative-pnl-chart-plot")).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});
