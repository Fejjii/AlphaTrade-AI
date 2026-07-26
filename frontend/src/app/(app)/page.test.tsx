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

let asyncState = {
  data: {
    summary,
    pendingApprovals: 1,
    pendingProposals: 1,
    validatedSignalsNeedingReview: 1,
    setupReviewUnreviewed: 3,
    draftsReady: 1,
    candidatesQueued: 2,
    runPlansPending: 1,
    activeValidations: 1,
    freshnessTimestamps: ["2026-06-28T12:00:00Z"],
    disciplineFallback: {
      legacyDiscipline: null,
      legacyRisk: null,
      legacyTradesToday: null,
    },
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
  asyncState = {
    ...asyncState,
    loading: false,
    error: null,
  };
});

describe("DashboardPage Phase C1 attention queue", () => {
  it("shows paper-only and real-trading-disabled status", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-paper-only")).toHaveTextContent("PAPER mode");
    expect(screen.getByTestId("dashboard-real-trading-status")).toHaveTextContent(
      "Real trading disabled",
    );
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("renders attention queue with prioritized actionable links", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("attention-queue")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /what needs my attention/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review approvals/i })).toHaveAttribute(
      "href",
      "/approvals",
    );
    expect(screen.getByRole("link", { name: /open signals inbox/i })).toHaveAttribute(
      "href",
      "/tradingview-signals",
    );
    expect(screen.getByRole("link", { name: /review lessons/i })).toHaveAttribute(
      "href",
      "/lessons",
    );
    expect(screen.getByRole("link", { name: /view positions/i })).toHaveAttribute(
      "href",
      "/positions",
    );
  });

  it("keeps progressive disclosure for denser metrics", () => {
    render(<DashboardPage />);
    expect(screen.getByText(/today's discipline snapshot/i)).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-progressive-links")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /validation queue/i })).toHaveAttribute(
      "href",
      "/paper-validation/candidates",
    );
  });

  it("shows loading and error states", () => {
    asyncState = { ...asyncState, loading: true, data: null };
    const { rerender } = render(<DashboardPage />);
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();

    asyncState = { ...asyncState, loading: false, error: "Failed to load", data: null };
    rerender(<DashboardPage />);
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });

  it("uses a simple one-column mobile-friendly layout", () => {
    const { container } = render(<DashboardPage />);
    expect(container.querySelector("[data-testid='dashboard-page']")?.className).toContain(
      "max-w-3xl",
    );
  });
});
