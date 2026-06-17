import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    providers: { providers: [] },
    health: { version: "0.1.0", status: "ok" },
  }),
  useSafetyPosture: () => ({ executionMode: "paper", realTradingEnabled: false }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      summary: null,
      strategies: [],
      usage: null,
      audit: { items: [], total: 0 },
      legacyDiscipline: null,
      legacyRisk: { daily_loss_warnings: 0, green_day_warnings: 0, overtrading_warnings: 0 },
      legacyTradesToday: 2,
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

afterEach(cleanup);

describe("DashboardPage fallback", () => {
  it("still renders discipline card when summary endpoint is unavailable", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("todays-discipline-card")).toBeInTheDocument();
    expect(screen.getByTestId("trades-today")).toHaveTextContent("2");
    expect(screen.getByTestId("discipline-limitations")).toHaveTextContent("fallback");
    expect(screen.getByTestId("dashboard-real-trading-status")).toHaveTextContent(
      "Real trading disabled",
    );
  });
});
