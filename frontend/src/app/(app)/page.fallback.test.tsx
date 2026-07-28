import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

function buildDashboardData(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  };
}

const asyncState: {
  data: ReturnType<typeof buildDashboardData> | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
} = {
  data: buildDashboardData(),
  loading: false,
  error: null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({ ...asyncState }),
}));

beforeEach(() => {
  asyncState.data = buildDashboardData();
  asyncState.loading = false;
  asyncState.error = null;
});

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

  it("keeps measured risk protections honest while never fabricating a discipline status (FP2-102)", () => {
    render(<DashboardPage />);
    fireEvent.click(screen.getByText(/today's discipline snapshot/i));

    // Risk fallback loaded with zero warnings — "clear" is a measured fact here.
    expect(screen.getByTestId("discipline-loss-protection")).toHaveTextContent(
      "Loss protection: clear",
    );
    // But the fallback never measures a discipline status — no fabricated "calm".
    expect(screen.getByTestId("discipline-status-badge")).toHaveTextContent(
      "status unavailable",
    );
    expect(screen.getByTestId("discipline-status-badge")).not.toHaveTextContent("calm");
  });

  it("renders unmeasured fields as unavailable, never as zeros or clear (FP2-102)", () => {
    asyncState.data = buildDashboardData({
      risk: failed(),
      tradeReview: failed(),
      discipline: ok({ improvement_suggestions: ["Review your last session."] }),
    });

    render(<DashboardPage />);
    fireEvent.click(screen.getByText(/today's discipline snapshot/i));

    // Trades today is unmeasured (trade-review fallback failed) — never 0.
    expect(screen.getByTestId("trades-today")).toHaveTextContent("Trades today: —");
    expect(screen.getByTestId("trades-today")).not.toHaveTextContent("0");

    // Risk fallback failed — protections are unknown, never "clear" badges.
    expect(screen.getByTestId("discipline-loss-protection")).toHaveTextContent(
      "Loss protection: unknown",
    );
    expect(screen.getByTestId("discipline-green-day-protection")).toHaveTextContent(
      "Green-day protection: unknown",
    );
    expect(screen.getByTestId("discipline-frequency-notice")).toHaveTextContent(
      "Frequency notice: unknown",
    );

    // Unavailable sources are named in the limitations.
    expect(screen.getByTestId("discipline-limitations")).toHaveTextContent(
      "Trades-today fallback unavailable.",
    );
    expect(screen.getByTestId("discipline-limitations")).toHaveTextContent(
      "Risk-behavior fallback unavailable.",
    );
  });
});
