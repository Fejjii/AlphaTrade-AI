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

const summary = {
  safety: {
    execution_mode: "paper",
    paper_only: true,
    real_trading_enabled: false,
    real_trading_disabled: true,
  },
  daily_discipline: {
    date: "2026-06-17",
    timezone: "UTC",
    trades_today: 4,
    paper_trades_opened_today: 3,
    paper_trades_closed_today: 1,
    journal_entries_today: 0,
    realized_pnl_today_paper: "12.50",
    unrealized_pnl_paper: "0",
    net_pnl_today_paper: "12.50",
    daily_loss_limit: null,
    daily_target: null,
    loss_lock_active: false,
    green_day_protection_active: true,
    overtrading_warning_active: false,
    max_trades_per_day: 20,
    remaining_trades_allowed: 16,
    discipline_status: "caution",
    reasons: ["Daily target reached — green-day protection is active."],
    recommended_action: "Move deliberately — protective signals are active for paper trading today.",
    limitations: [],
  },
  strategy_readiness: {
    counts: {
      needs_structure: 0,
      ready_for_backtest: 0,
      needs_more_sample: 0,
      paper_eligible: 0,
      paper_validation_running: 1,
      paper_validated: 0,
      restricted: 0,
    },
    top_needing_action: [
      {
        strategy_id: "s1",
        name: "HTF Pullback",
        status: "Paper validation running",
        next_action: "Review latest scans and simulated trades.",
        blockers: [],
        link_hint: "/strategy-lab/s1",
      },
    ],
    limitations: [],
  },
  active_paper_validations: [{ strategy_id: "s1", name: "HTF Pullback", status: "running" }],
  open_paper_trades: [],
  alerts_lessons: {
    unread_alerts: 2,
    latest_high_priority: [
      {
        alert_type: "setup_signal_detected",
        severity: "warning",
        message: "Setup",
      },
    ],
    pending_lessons: 2,
    accepted_lessons: 1,
    top_pending_lessons: [],
    limitations: [],
  },
  market_watcher: null,
  bridge: null,
  next_recommended_action: {
    action: "Consider pausing new entries and reviewing today's paper results.",
    reason: "Green-day protection is active after reaching your daily target.",
    link: "/analytics",
    priority: 3,
  },
  limitations: [],
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      summary,
      strategies: [
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
      usage: { event_count: 10, total_estimated_cost: "0.50", cost_is_placeholder: true },
      audit: { items: [], total: 0 },
      legacyDiscipline: null,
      legacyRisk: null,
      legacyTradesToday: null,
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

  it("renders workflow and summary-backed cards", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("workflow-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("todays-discipline-card")).toBeInTheDocument();
    expect(screen.getByTestId("trades-today")).toHaveTextContent("4");
    expect(screen.getByTestId("daily-pnl-today")).toHaveTextContent("12.5");
    expect(screen.getByTestId("discipline-green-day-protection")).toHaveTextContent("engaged");
    expect(screen.getByTestId("strategy-readiness-card")).toBeInTheDocument();
    expect(screen.getByTestId("active-paper-validations")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-latest-alerts")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-lessons-pending")).toHaveTextContent("2");
    expect(screen.getByTestId("what-to-do-next")).toBeInTheDocument();
    expect(screen.getByTestId("next-action-reason")).toHaveTextContent("Green-day protection");
  });
});
