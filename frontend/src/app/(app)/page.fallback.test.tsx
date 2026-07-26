import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    providers: { providers: [] },
    health: { version: "0.1.0", status: "ok" },
  }),
  useSafetyPosture: () => ({ executionMode: "paper", realTradingEnabled: false }),
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      summary: null,
      pendingApprovals: 0,
      pendingProposals: 0,
      validatedSignalsNeedingReview: 0,
      setupReviewUnreviewed: 0,
      draftsReady: 0,
      candidatesQueued: 0,
      runPlansPending: 0,
      activeValidations: 0,
      freshnessTimestamps: [],
      disciplineFallback: {
        legacyDiscipline: null,
        legacyRisk: {
          daily_loss_warnings: 0,
          green_day_warnings: 0,
          overtrading_warnings: 0,
        },
        legacyTradesToday: 2,
      },
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
    fireEvent.click(screen.getByText(/today's discipline snapshot/i));
    expect(screen.getByTestId("todays-discipline-card")).toBeInTheDocument();
    expect(screen.getByTestId("trades-today")).toHaveTextContent("2");
    expect(screen.getByTestId("discipline-limitations")).toHaveTextContent("fallback");
    expect(screen.getByTestId("dashboard-real-trading-status")).toHaveTextContent(
      "Real trading disabled",
    );
  });
});
