import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import DashboardPage from "./page";
import { api } from "@/lib/api";

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => ({ executionMode: "paper", realTradingEnabled: false }),
}));
vi.mock("@/components/dashboard/AttentionCard", () => ({ AttentionCard: () => null }));
vi.mock("@/components/dashboard/DailyReviewCard", () => ({ DailyReviewCard: () => null }));
vi.mock("@/lib/api", () => ({
  api: {
    performance: { portfolio: vi.fn().mockRejectedValue(new Error("unavailable")) },
    positions: { list: vi.fn() },
    journal: {
      list: vi.fn(),
      listTrades: vi.fn().mockResolvedValue({
        total: 1, limit: 8, offset: 0,
        items: [{ id: "canonical-trade", symbol: "BTCUSDT", direction: "long", status: "open", net_pnl: null }],
      }),
      statistics: vi.fn().mockRejectedValue(new Error("unavailable")),
    },
    dashboard: { summary: vi.fn().mockResolvedValue({
      safety: { execution_mode: "paper", real_trading_enabled: false },
      open_paper_trades_summary: {
        total_count: 1,
        items: [{ journal_trade_id: "canonical-trade", symbol: "BTCUSDT", direction: "long", status: "open", unrealized_pnl: null }],
      },
    }) },
    marketWatcher: { monitoring: vi.fn().mockRejectedValue(new Error("unavailable")) },
    canonical: { getMarketStatus: vi.fn().mockRejectedValue(new Error("unavailable")) },
    alerts: { list: vi.fn().mockRejectedValue(new Error("unavailable")) },
  },
}));

afterEach(cleanup);

it("loads canonical Journal trades and summary positions without consulting the legacy stores", async () => {
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByTestId("dashboard-open-count")).toHaveTextContent("1"));
  expect(api.journal.listTrades).toHaveBeenCalledWith({ limit: 8 });
  expect(api.dashboard.summary).toHaveBeenCalledOnce();
  expect(api.positions.list).not.toHaveBeenCalled();
  expect(api.journal.list).not.toHaveBeenCalled();
  expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("BTCUSDT");
  expect(screen.getByTestId("dashboard-recent-trades")).toHaveTextContent("BTCUSDT");
  expect(screen.getByTestId("dashboard-recent-trades")).toHaveTextContent("Open");
  expect(screen.getAllByRole("link", { name: /BTCUSDT/ })).toHaveLength(2);
  for (const link of screen.getAllByRole("link", { name: /BTCUSDT/ })) {
    expect(link).toHaveAttribute("href", "/journal?trade_id=canonical-trade");
  }
});
