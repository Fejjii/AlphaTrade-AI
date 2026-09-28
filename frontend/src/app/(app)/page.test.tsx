import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";
import { failedSource, okSource } from "@/components/workflows/sourceResult";
import { formatCurrency, formatMonetary, UNAVAILABLE } from "@/lib/format";
import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";
import type { TraderDashboardData } from "@/components/dashboard/TraderDashboardView";
import type {
  CanonicalMarketMonitorStatusRead,
  DashboardSummary,
  JournalEntry,
  JournalStatsResponse,
  PaginatedJournalEntries,
  PaginatedPositions,
  PaperAlert,
  PaperPortfolioResponse,
  Position,
} from "@/lib/api/types";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
};

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => safetyPosture,
}));

function portfolio(tradeCount: number, winRate: number): PaperPortfolioResponse {
  return {
    account: { current_equity: "1000.50" },
    metrics: { trade_count: tradeCount, win_rate: winRate, net_pnl: "12.50" },
    breakdowns: {
      by_strategy: [{ key: "HTF Pullback", metrics: { net_pnl: "12.50", trade_count: tradeCount } }],
    },
  } as PaperPortfolioResponse;
}

function dashboardData(
  overrides: Partial<TraderDashboardData> = {},
): TraderDashboardData {
  const base: TraderDashboardData = {
    portfolio: okSource(portfolio(4, 0.5)),
    positions: okSource({
      items: [
        {
          id: "p1",
          symbol: "BTCUSDT",
          direction: "long",
          unrealized_pnl: "5",
        } as Position,
      ],
      total: 1,
      limit: 20,
      offset: 0,
    } as PaginatedPositions),
    journal: okSource({
      items: [
        {
          id: "j1",
          symbol: "ETHUSDT",
          direction: "short",
          result: "loss",
          pnl: "-2.00",
        } as JournalEntry,
      ],
      total: 1,
      limit: 8,
      offset: 0,
    } as PaginatedJournalEntries),
    strategyStats: okSource({
      buckets: [
        {
          key: "s1",
          label: "HTF Pullback",
          metrics: { trade_count: 4, win_rate: 0.5, net_pnl_total: "12.50" },
        },
      ],
    } as JournalStatsResponse),
    summary: okSource({
      safety: { execution_mode: "paper", real_trading_enabled: false },
    } as DashboardSummary),
    watcher: okSource(makeWatcherMonitoringSnapshot()),
    market: okSource({
      symbol: "BTCUSDT",
      availability: "fresh",
    } as CanonicalMarketMonitorStatusRead),
    alerts: okSource({
      items: [{ id: "a1", message: "Paper target reached", severity: "high", created_at: "2026-01-01" } as PaperAlert],
      total: 1,
    }),
  };
  return { ...base, ...overrides };
}

const asyncState: {
  data: TraderDashboardData | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
} = {
  data: dashboardData(),
  loading: false,
  error: null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

afterEach(() => {
  cleanup();
  safetyPosture.executionMode = "paper";
  safetyPosture.realTradingEnabled = false;
  asyncState.data = dashboardData();
  asyncState.loading = false;
  asyncState.error = null;
});

describe("Trader dashboard", () => {
  it("shows confirmed paper posture only when verified", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent("PAPER mode");
    expect(screen.getByTestId("dashboard-real-trading-status")).toHaveTextContent(
      "Real trading disabled",
    );
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent("Paper only");
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
  });

  it("shows safety conflict when real trading is enabled", () => {
    safetyPosture.realTradingEnabled = true;
    asyncState.data = dashboardData({
      summary: okSource({
        safety: { execution_mode: "paper", real_trading_enabled: true },
      } as DashboardSummary),
    });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-safety-conflict")).toHaveTextContent(/safety conflict/i);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("shows unverified posture when runtime fields are unknown", () => {
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    asyncState.data = dashboardData({ summary: failedSource("summary down") });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent("Execution unverified");
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent(
      "Runtime posture unverified",
    );
  });

  it("shows paper value, pnl, win rate, positions, and trader watcher status", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-equity")).toHaveTextContent(formatCurrency("1000.50"));
    expect(screen.getByTestId("dashboard-pnl")).toHaveTextContent(formatMonetary("12.50"));
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent("50.0%");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("BTCUSDT");
    expect(screen.getByTestId("dashboard-recent-trades")).toHaveTextContent("ETHUSDT");
    expect(screen.getByTestId("dashboard-strategy-performance")).toHaveTextContent("HTF Pullback");
    expect(screen.getByTestId("dashboard-watcher-status")).toHaveTextContent("Stopped");
    expect(screen.getByTestId("dashboard-market-evidence")).toHaveTextContent("Healthy");
    expect(screen.getByTestId("dashboard-alerts")).toHaveTextContent("Paper target reached");
    expect(screen.queryByTestId("watcher-monitoring-card")).not.toBeInTheDocument();
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });

  it("does not present an unmeasured win rate as zero", () => {
    asyncState.data = dashboardData({ portfolio: okSource(portfolio(0, 0)) });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent(UNAVAILABLE);
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent("No closed trades yet");
    expect(screen.getByTestId("dashboard-win-rate")).not.toHaveTextContent("0.0%");
  });

  it("shows loading and error states", () => {
    asyncState.loading = true;
    asyncState.data = null;
    const { rerender } = render(<DashboardPage />);
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
    asyncState.loading = false;
    asyncState.error = "Failed to load";
    rerender(<DashboardPage />);
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });
});
