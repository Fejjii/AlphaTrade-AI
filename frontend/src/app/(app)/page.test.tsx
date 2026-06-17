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
      strategies: {
        items: [
          {
            id: "s1",
            name: "HTF Pullback",
            setup_type: "htf_trend_pullback",
            current_version: 1,
            paper_validation_status: "running",
            paper_eligible: true,
            backtest_status: "completed",
            enabled: true,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
      },
      positions: { items: [], total: 0 },
      alertSummary: { total: 3, unread: 2, by_type: {}, by_severity: {} },
      alerts: {
        items: [
          {
            id: "a1",
            alert_type: "setup_signal_detected",
            severity: "warning",
            message: "Setup",
            created_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
      },
      lessons: { items: [], total: 2 },
      discipline: {
        score: 80,
        grade: "B",
        positive_behaviors: [],
        negative_behaviors: [],
        improvement_suggestions: [],
      },
      risk: {
        risk_blocks_count: 0,
        daily_loss_warnings: 0,
        green_day_warnings: 0,
        overtrading_warnings: 0,
        revenge_trading_warnings: 0,
        proposals_rejected: 0,
        proposals_needs_more_analysis: 0,
        paper_orders_rejected: 0,
        approval_pending_count: 0,
        approval_approved_count: 0,
        journal_completion_rate: 1,
        triggered_rules: {},
      },
      tradeReview: { total_journaled_trades: 5 },
      usage: { event_count: 10, total_estimated_cost: "0.50", cost_is_placeholder: true },
      audit: { items: [], total: 0 },
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

afterEach(cleanup);

describe("DashboardPage", () => {
  it("shows paper-only and real-trading-disabled status", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent("PAPER mode");
    expect(screen.getByTestId("dashboard-real-trading-status")).toHaveTextContent(
      "Real trading disabled",
    );
  });

  it("renders the workflow stepper and trader cards", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("workflow-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("todays-discipline-card")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-readiness-card")).toBeInTheDocument();
    expect(screen.getByTestId("active-paper-validations")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-latest-alerts")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-lessons-pending")).toHaveTextContent("2");
    expect(screen.getByTestId("what-to-do-next")).toBeInTheDocument();
  });

  it("hides developer details behind a collapsed section", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("developer-details")).toBeInTheDocument();
  });
});
