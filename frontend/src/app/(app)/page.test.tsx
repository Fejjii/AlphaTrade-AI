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
    risk_settings_source: "user_risk_settings",
    pnl_sources: { paper_validation_closed: "12.50" },
    reasons: ["Daily target reached — green-day protection is active."],
    recommended_action: "Move deliberately — protective signals are active for paper trading today.",
    limitations: ["Unrealized paper PnL unavailable for some open validation trades."],
  },
  discipline_score: {
    score: 84,
    grade: "B",
    band: "good",
    main_contributors: ["Consistent stop-loss usage"],
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
  open_paper_trades: [
    {
      position_id: "p1",
      paper_trade_id: null,
      strategy_id: null,
      strategy_name: null,
      symbol: "BTCUSDT",
      direction: "long",
      unrealized_pnl: "5",
      status: "open",
      source: "proposal_flow",
    },
    {
      position_id: null,
      paper_trade_id: "t1",
      strategy_id: "s1",
      strategy_name: "HTF Pullback",
      symbol: "ETHUSDT",
      direction: "short",
      unrealized_pnl: null,
      status: "open",
      source: "paper_validation",
    },
  ],
  open_paper_trades_summary: {
    proposal_flow_count: 1,
    paper_validation_count: 1,
    total_count: 2,
    total_open_exposure: "5",
    items: [],
    limitations: ["Paper-validation open trades do not include live unrealized PnL in this slice."],
  },
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
      exchangeDiagnostics: null,
      alertRouting: {
        alerts_enabled: true,
        telegram_enabled: false,
        webhook_enabled: false,
        external_delivery_enabled: false,
        paper_only: true,
        quiet_hours: { enabled: false, start: null, end: null, timezone: "UTC", source: "none" },
        severity_filters: ["worker: info+", "user: info+"],
        pending_alerts_count: 0,
        delivered_alerts_count: 0,
        failed_alerts_count: 0,
        market_watcher_configured: false,
        market_watcher_running: false,
        bridge_enabled: false,
        bridge_running: false,
        worker_enabled: false,
        worker_running: false,
        readiness: "ready",
        warnings: [],
        generated_at: "2026-06-28T12:00:00Z",
      },
      setupReviewSummary: {
        total_unreviewed: 3,
        total_watching: 2,
        total_important: 1,
        total_ignored: 0,
        by_condition: { order_block: 2, sfp: 1 },
        by_symbol: { BTCUSDT: 3 },
        latest_created_at: "2026-06-28T12:00:00Z",
        highest_confidence_alerts: [
          {
            alert_id: "a1",
            symbol: "BTCUSDT",
            condition: "order_block",
            confidence: 0.91,
            created_at: "2026-06-28T12:00:00Z",
          },
        ],
      },
      paperDraftSummary: {
        total_drafts: 2,
        latest_condition: "breakout_retest",
        latest_created_at: "2026-06-28T12:00:00Z",
      },
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
    expect(screen.getByTestId("dashboard-setup-alerts-review")).toHaveTextContent("Unreviewed: 3");
    expect(screen.getByTestId("dashboard-setup-alerts-review")).toHaveTextContent("Watching: 2");
    expect(screen.getByTestId("dashboard-setup-alerts-review")).toHaveTextContent("Important: 1");
    expect(screen.getByTestId("dashboard-setup-alerts-review")).toHaveTextContent("Order block");
    expect(screen.getByRole("link", { name: "Review setup alerts" })).toHaveAttribute(
      "href",
      "/alerts/review",
    );
    expect(screen.getByTestId("dashboard-paper-drafts")).toHaveTextContent("Draft count: 2");
    expect(screen.getByTestId("dashboard-paper-drafts")).toHaveTextContent("Breakout retest");
    expect(screen.getByRole("link", { name: "View paper drafts" })).toHaveAttribute(
      "href",
      "/paper-validation/drafts",
    );
    expect(screen.getByTestId("what-to-do-next")).toBeInTheDocument();
    expect(screen.getByTestId("next-action-reason")).toHaveTextContent("Green-day protection");
  });

  it("displays discipline score and configured limits", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("discipline-score-badge")).toHaveTextContent("84");
    expect(screen.getByTestId("discipline-configured-limits")).toHaveTextContent("Max trades: 20");
  });

  it("shows open paper trades from summary", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("open-paper-trades-counts")).toHaveTextContent("Paper validation: 1");
    expect(screen.getByTestId("dashboard-open-paper-trades")).toHaveTextContent("HTF Pullback");
  });

  it("renders PnL limitations in discipline details", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("discipline-limitations")).toHaveTextContent("Unrealized paper PnL");
  });
});
