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

function ok<T>(data: T) {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed() {
  return { data: null, available: false, error: "unavailable", fallbackUsed: false };
}

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      summary: failed(),
      approvals: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      proposals: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      tvSignals: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      setupReviewSummary: failed(),
      paperDraftSummary: failed(),
      paperCandidateSummary: failed(),
      paperRunPlanSummary: failed(),
      paperRunSessions: failed(),
      alertRouting: failed(),
      watcherSummary: failed(),
      discipline: failed(),
      risk: ok({
        daily_loss_warnings: 0,
        green_day_warnings: 0,
        overtrading_warnings: 0,
      }),
      tradeReview: ok({ total_journaled_trades: 2 }),
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
    expect(screen.getByTestId("dashboard-summary-unavailable")).toBeInTheDocument();
  });
});
