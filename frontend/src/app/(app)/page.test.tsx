import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    providers: { providers: [] },
    health: { version: "0.1.0", status: "ok" },
  }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
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
  strategy_readiness: null,
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
  ],
  open_paper_trades_summary: {
    proposal_flow_count: 1,
    paper_validation_count: 0,
    total_count: 1,
    total_open_exposure: "5",
    items: [],
    limitations: [],
  },
  alerts_lessons: {
    unread_alerts: 2,
    latest_high_priority: [],
    pending_lessons: 2,
    accepted_lessons: 1,
    top_pending_lessons: [],
    limitations: [],
  },
  market_watcher: {
    effective_enabled: true,
    last_scan_at: "2026-06-28T12:00:00Z",
    fresh_observations: 1,
    limitations: [],
  },
  bridge: null,
  next_recommended_action: {
    action: "Consider pausing new entries and reviewing today's paper results.",
    reason: "Green-day protection is active after reaching your daily target.",
    link: "/analytics",
    priority: 3,
  },
  limitations: [],
};

function ok<T>(data: T) {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T = null>(error = "boom") {
  return { data: null as T | null, available: false, error, fallbackUsed: false };
}

let asyncState = {
  data: {
    summary: ok(summary),
    approvals: ok({
      items: [{ id: "a1", status: "pending", proposal_id: "p1" }],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    proposals: ok({
      items: [{ id: "p1", status: "pending_approval" }],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    tvSignals: ok({
      items: [
        {
          id: "sig-1",
          status: "validated",
          links: { candidate_id: null },
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    setupReviewSummary: ok({ total_unreviewed: 3 }),
    paperDraftSummary: ok({ ready_for_validation_count: 1 }),
    paperCandidateSummary: ok({ total_queued: 2 }),
    paperRunPlanSummary: ok({ total_planned: 1 }),
    paperRunSessions: ok({ items: [], total: 0 }),
    alertRouting: ok({ generated_at: "2026-06-28T12:00:00Z" }),
    watcherSummary: ok({ last_scan_at: "2026-06-28T12:00:00Z", generated_at: "2026-06-28T12:00:00Z" }),
    discipline: failed(),
    risk: failed(),
    tradeReview: failed(),
  } as unknown,
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

afterEach(() => {
  cleanup();
  safetyPosture.executionMode = "paper";
  safetyPosture.realTradingEnabled = false;
  asyncState = {
    ...asyncState,
    loading: false,
    error: null,
  };
});

describe("DashboardPage Phase C1 safety and availability", () => {
  it("shows confirmed paper posture only when verified", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent("PAPER mode");
    expect(screen.getByTestId("dashboard-real-trading-status")).toHaveTextContent(
      "Real trading disabled",
    );
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent("Paper only");
    expect(screen.queryByText("Simulated execution only")).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("shows safety conflict when real trading is enabled", () => {
    safetyPosture.realTradingEnabled = true;
    asyncState = {
      ...asyncState,
      data: {
        ...(asyncState.data as Record<string, unknown>),
        summary: ok({
          ...summary,
          safety: { ...summary.safety, real_trading_enabled: true },
        }),
      },
    };
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-safety-conflict")).toHaveTextContent(/safety conflict/i);
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent("Safety conflict");
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("shows unverified posture when runtime fields are unknown", () => {
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    asyncState = {
      ...asyncState,
      data: {
        ...(asyncState.data as Record<string, unknown>),
        summary: failed(),
      },
    };
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent("Execution unverified");
    expect(screen.getByTestId("dashboard-runtime-posture")).toHaveTextContent(
      "Runtime posture unverified",
    );
  });

  it("renders attention queue with prioritized actionable links", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("attention-queue")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review approvals/i })).toHaveAttribute(
      "href",
      "/approvals",
    );
    expect(screen.getByRole("link", { name: /open signals inbox/i })).toHaveAttribute(
      "href",
      "/tradingview-signals",
    );
  });

  it("does not claim catch-up when required sources failed", () => {
    asyncState = {
      ...asyncState,
      data: {
        ...(asyncState.data as Record<string, unknown>),
        approvals: failed("approvals down"),
        proposals: failed("proposals down"),
        tvSignals: failed("tv down"),
        summary: failed("summary down"),
        setupReviewSummary: failed(),
        paperDraftSummary: failed(),
        paperCandidateSummary: failed(),
        paperRunPlanSummary: failed(),
        paperRunSessions: failed(),
      },
    };
    render(<DashboardPage />);
    expect(screen.getByTestId("attention-partial-data")).toBeInTheDocument();
    expect(screen.getByText(/no actionable items found in the available sources/i)).toBeInTheDocument();
    expect(screen.queryByText(/you are caught up/i)).not.toBeInTheDocument();
  });

  it("shows loading and error states", () => {
    asyncState = { ...asyncState, loading: true, data: null };
    const { rerender } = render(<DashboardPage />);
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();

    asyncState = { ...asyncState, loading: false, error: "Failed to load", data: null };
    rerender(<DashboardPage />);
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });
});
