import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";
import type { TraderDashboardData } from "@/components/dashboard/TraderDashboardView";
import { failedSource, okSource } from "@/components/workflows/sourceResult";
import { UNAVAILABLE } from "@/lib/format";
import type { PaginatedPositions } from "@/lib/api/types";

vi.mock("@/contexts/AppContext", () => ({
  useSafetyPosture: () => ({ executionMode: "paper", realTradingEnabled: false }),
}));

function failedDashboard(): TraderDashboardData {
  return {
    portfolio: failedSource("portfolio down"),
    positions: failedSource("positions down"),
    journal: failedSource("journal down"),
    strategyStats: failedSource("stats down"),
    summary: failedSource("summary down"),
    watcher: failedSource("watcher down"),
    market: failedSource("market down"),
    alerts: failedSource("alerts down"),
  };
}

const asyncState: {
  data: TraderDashboardData | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
} = {
  data: failedDashboard(),
  loading: false,
  error: null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

afterEach(() => {
  cleanup();
  asyncState.data = failedDashboard();
});

describe("Trader dashboard unavailable sources", () => {
  it("renders unavailable figures instead of zeros", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-equity")).toHaveTextContent(UNAVAILABLE);
    expect(screen.getByTestId("dashboard-pnl")).toHaveTextContent(UNAVAILABLE);
    expect(screen.getByTestId("dashboard-win-rate")).toHaveTextContent(UNAVAILABLE);
    expect(screen.getByTestId("dashboard-equity")).not.toHaveTextContent("0.00");
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent(
      "Open positions unavailable",
    );
    expect(screen.getByTestId("dashboard-recent-trades")).toHaveTextContent(
      "Recent trades unavailable",
    );
    expect(screen.getByTestId("dashboard-strategy-performance")).toHaveTextContent(
      "Strategy performance unavailable",
    );
    expect(screen.getByTestId("dashboard-watcher-status")).toHaveTextContent("Unavailable");
    expect(screen.getByTestId("dashboard-market-evidence")).toHaveTextContent("Unavailable");
    expect(screen.getByTestId("dashboard-alerts")).toHaveTextContent("Alerts unavailable");
    expect(screen.queryByText("No open positions")).not.toBeInTheDocument();
  });

  it("treats an empty open-position list as empty, not unavailable", () => {
    asyncState.data = {
      ...failedDashboard(),
      positions: okSource({ items: [], total: 0, limit: 20, offset: 0 } as PaginatedPositions),
    };
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-open-positions")).toHaveTextContent("No open positions");
    expect(screen.getByTestId("dashboard-open-count")).toHaveTextContent("0");
  });
});
