import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";
import { failedSource, okSource } from "@/components/workflows/sourceResult";
import { formatCurrency, formatMonetary, UNAVAILABLE } from "@/lib/format";
import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";
import type { TraderDashboardData } from "@/components/dashboard/TraderDashboardView";
import type {
  CanonicalMarketMonitorStatusRead,
  DashboardSummary,
  CanonicalJournalTradeListItem,
  JournalStatsResponse,
  PaginatedCanonicalJournalTrades,
  PaperAlert,
  PaperPortfolioResponse,
} from "@/lib/api/types";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
};

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/components/dashboard/BloFinDemoAccountCard", () => ({
  BloFinDemoAccountCard: ({ refreshKey }: { refreshKey: number }) => (
    <section data-testid="dashboard-demo-account" data-refresh-key={refreshKey}>BloFin demo account</section>
  ),
}));

function portfolio(
  tradeCount: number,
  winRate: number,
): PaperPortfolioResponse {
  return {
    account: { current_equity: "1000.50" },
    metrics: { trade_count: tradeCount, win_rate: winRate, net_pnl: "12.50" },
    breakdowns: {
      by_strategy: [
        {
          key: "HTF Pullback",
          metrics: { net_pnl: "12.50", trade_count: tradeCount },
        },
      ],
    },
  } as PaperPortfolioResponse;
}

function dashboardData(
  overrides: Partial<TraderDashboardData> = {},
): TraderDashboardData {
  const base: TraderDashboardData = {
    portfolio: okSource(portfolio(4, 0.5)),
    journal: okSource({
      items: [
        {
          id: "j1",
          symbol: "ETHUSDT",
          direction: "short",
          result: "loss",
          net_pnl: "-2.00",
          status: "closed",
          created_at: "2026-10-01T00:00:00Z",
        } as CanonicalJournalTradeListItem,
      ],
      total: 1,
      limit: 8,
      offset: 0,
    } as PaginatedCanonicalJournalTrades),
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
      open_paper_trades_summary: {
        total_count: 1,
        items: [{
          journal_trade_id: "canonical-p1",
          symbol: "BTCUSDT",
          direction: "long",
          exchange: "PAPER_INTERNAL",
          account_id: "account-one",
          unrealized_pnl: null,
        }],
      },
    } as DashboardSummary),
    watcher: okSource(makeWatcherMonitoringSnapshot()),
    market: okSource({
      symbol: "BTCUSDT",
      availability: "fresh",
    } as CanonicalMarketMonitorStatusRead),
    alerts: okSource({
      items: [
        {
          id: "a1",
          message: "Paper target reached",
          severity: "high",
          created_at: "2026-01-01",
        } as PaperAlert,
      ],
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
  it("refreshes the saved demo snapshot together with the Dashboard", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-demo-account")).toHaveAttribute("data-refresh-key", "0");
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(screen.getByTestId("dashboard-demo-account")).toHaveAttribute("data-refresh-key", "1");
    expect(asyncState.reload).toHaveBeenCalled();
  });
  it("shows confirmed paper posture only when verified", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent(
      "PAPER mode",
    );
    expect(
      screen.getByTestId("dashboard-real-trading-status"),
    ).toHaveTextContent("Real trading disabled");
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent(
      "Paper only",
    );
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("daily-review-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("daily-review-content")).not.toBeInTheDocument();
  });

  it("shows safety conflict when real trading is enabled", () => {
    safetyPosture.realTradingEnabled = true;
    asyncState.data = dashboardData({
      summary: okSource({
        safety: { execution_mode: "paper", real_trading_enabled: true },
      } as DashboardSummary),
    });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-safety-conflict")).toHaveTextContent(
      /safety conflict/i,
    );
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
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent(
      "Execution unverified",
    );
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent(
      "Runtime posture unverified",
    );
  });

  it("shows paper value, pnl, win rate, positions, and trader watcher status", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-equity")).toHaveTextContent(
      formatCurrency("1000.50"),
    );
    expect(screen.getByTestId("dashboard-pnl")).toHaveTextContent(
      formatMonetary("12.50"),
    );
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent("50.0%");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent(
      "BTCUSDT",
    );
    expect(screen.getByTestId("dashboard-recent-trades")).toHaveTextContent(
      "ETHUSDT",
    );
    expect(
      screen.getByTestId("dashboard-strategy-performance"),
    ).toHaveTextContent("HTF Pullback");
    expect(screen.getByTestId("dashboard-watcher-status")).toHaveTextContent(
      "Stopped",
    );
    expect(screen.getByTestId("dashboard-market-evidence")).toHaveTextContent(
      "Healthy",
    );
    expect(screen.getByTestId("dashboard-alerts")).toHaveTextContent(
      "Paper target reached",
    );
    expect(
      screen.queryByTestId("watcher-monitoring-card"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });

  it("does not present an unmeasured win rate as zero", () => {
    asyncState.data = dashboardData({ portfolio: okSource(portfolio(0, 0)) });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent(
      UNAVAILABLE,
    );
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent(
      "No closed trades yet",
    );
    expect(screen.getByTestId("dashboard-win-rate")).not.toHaveTextContent(
      "0.0%",
    );
  });

  it("keeps unavailable daily status explicit and reports total open positions", () => {
    const data = dashboardData();
    asyncState.data = dashboardData({
      summary: okSource({
        ...data.summary.data!,
        open_paper_trades_summary: {
          ...data.summary.data!.open_paper_trades_summary!, total_count: 25,
        },
      }),
    });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-open-count")).toHaveTextContent("25");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent(
      "Showing 1 of 25",
    );
    expect(screen.getByTestId("dashboard-daily-status")).toHaveTextContent(
      "Daily status unavailable",
    );
    expect(screen.getByTestId("dashboard-daily-pnl")).toHaveTextContent(
      UNAVAILABLE,
    );
    expect(screen.getByTestId("dashboard-expectancy")).toHaveTextContent(
      "Expectancy unavailable",
    );
  });

  it("links canonical trades and labels scope differences without inventing PnL", () => {
    render(<DashboardPage />);
    expect(screen.getByRole("link", { name: /ETHUSDT/ })).toHaveAttribute("href", "/journal?trade_id=j1");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("manual demo tests excluded");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("PAPER_INTERNAL");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("Unrealized PnL unavailable");
    expect(screen.getByText(/these scopes can differ/)).toBeInTheDocument();
  });

  it("labels demo Journal provenance separately from paper account metrics", () => {
    const data = dashboardData();
    asyncState.data = dashboardData({ journal: okSource({
      ...data.journal.data!, items: [{ ...data.journal.data!.items[0],
        exchange: "BLOFIN_DEMO", source: "manual_demo_test", net_pnl: null,
      }],
    }) });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-recent-trades")).toHaveTextContent("BLOFIN_DEMO");
    expect(screen.getByTestId("dashboard-equity")).toHaveTextContent(formatCurrency("1000.50"));
  });

  it("never falls back to legacy positions when canonical open records fail", () => {
    asyncState.data = dashboardData({ summary: failedSource("down") });
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-open-count")).toHaveTextContent(UNAVAILABLE);
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("Open positions unavailable");
    expect(screen.queryByText("No open positions")).not.toBeInTheDocument();
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
