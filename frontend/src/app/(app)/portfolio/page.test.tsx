import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";
import type {
  DashboardSummary,
  DailyDisciplineSnapshot,
  JournalEntry,
  PaginatedJournalEntries,
  PaginatedPositions,
  PaperPortfolioResponse,
  Position,
} from "@/lib/api/types";

import PaperPortfolioPage from "./page";
import { samplePortfolio } from "./sample-portfolio";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
  postureKnown: true,
};

const appContext = {
  killSwitchActive: false,
  killSwitchStatus: {
    organization_id: "org",
    active: false,
    reason: null as string | null,
    activated_by: null,
    activated_at: null,
    deactivated_by: null,
    deactivated_at: null,
    version: 1,
    scope: "org",
    global_active: false,
    execution_blocked: false,
  } as {
    organization_id: string;
    active: boolean;
    reason: string | null;
    activated_by: string | null;
    activated_at: string | null;
    deactivated_by: string | null;
    deactivated_at: string | null;
    version: number;
    scope: string;
    global_active: boolean;
    execution_blocked: boolean;
  } | null,
  killSwitchError: null as string | null,
  killSwitchBusy: false,
  loading: false,
  setKillSwitchActive: vi.fn(),
  refreshKillSwitch: vi.fn(),
  health: null,
  providers: { providers: [] },
};

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => appContext,
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
}));

const portfolioMock = vi.fn();
const dashboardMock = vi.fn();
const positionsMock = vi.fn();
const journalMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    performance: {
      portfolio: (...args: unknown[]) => portfolioMock(...args),
    },
    dashboard: {
      summary: (...args: unknown[]) => dashboardMock(...args),
    },
    positions: {
      list: (...args: unknown[]) => positionsMock(...args),
    },
    journal: {
      list: (...args: unknown[]) => journalMock(...args),
    },
  },
}));

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error: string): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function makeDiscipline(
  overrides: Partial<DailyDisciplineSnapshot> = {},
): DailyDisciplineSnapshot {
  return {
    date: "2026-07-27",
    timezone: "UTC",
    trades_today: 1,
    paper_trades_opened_today: 1,
    paper_trades_closed_today: 0,
    journal_entries_today: 0,
    realized_pnl_today_paper: "10",
    unrealized_pnl_paper: "5",
    net_pnl_today_paper: "15",
    daily_loss_limit: "100",
    daily_target: "200",
    loss_lock_active: false,
    green_day_protection_active: false,
    overtrading_warning_active: false,
    max_trades_per_day: 5,
    remaining_trades_allowed: 4,
    discipline_status: "calm",
    risk_settings_source: "user_risk_settings",
    pnl_sources: {},
    reasons: [],
    recommended_action: "Stay patient within paper rules.",
    limitations: [],
    ...overrides,
  };
}

function makeDashboard(
  disciplineOverrides: Partial<DailyDisciplineSnapshot> = {},
): DashboardSummary {
  return {
    safety: {
      execution_mode: "paper",
      real_trading_enabled: false,
      paper_only: true,
      real_trading_disabled: true,
    },
    daily_discipline: makeDiscipline(disciplineOverrides),
    discipline_score: null,
    strategy_readiness: null,
    active_paper_validations: [],
    open_paper_trades: [
      {
        position_id: "pos-open-1",
        strategy_id: "strat-1",
        strategy_name: "HTF Pullback",
        symbol: "BTCUSDT",
        direction: "long",
        unrealized_pnl: "12",
        status: "open",
      },
    ],
    open_paper_trades_summary: {
      proposal_flow_count: 1,
      paper_validation_count: 0,
      total_count: 1,
      total_open_exposure: "500",
      items: [
        {
          position_id: "pos-open-1",
          strategy_id: "strat-1",
          strategy_name: "HTF Pullback",
          symbol: "BTCUSDT",
          direction: "long",
          unrealized_pnl: "12",
          status: "open",
        },
      ],
      limitations: [],
    },
    alerts_lessons: null,
    market_watcher: null,
    bridge: null,
    next_recommended_action: {
      action: "Review paper portfolio risk posture.",
      reason: "Command centre sample",
      link: "/portfolio",
      priority: 3,
    },
    limitations: [],
  };
}

function makePosition(overrides: Partial<Position> & { id: string; status: Position["status"] }): Position {
  return {
    organization_id: "org",
    user_id: "user",
    symbol: "BTCUSDT",
    direction: "long",
    size: "0.5",
    entry_price: "64000",
    leverage: "2",
    take_profits: [],
    unrealized_pnl: "12",
    realized_pnl: "25",
    risk_state: {},
    opened_at: "2026-07-20T10:00:00.000Z",
    closed_at: overrides.status === "closed" ? "2026-07-21T10:00:00.000Z" : null,
    ...overrides,
  };
}

function makeEntry(overrides: Partial<JournalEntry> & { id: string }): JournalEntry {
  return {
    organization_id: "org",
    user_id: "user",
    symbol: "ETHUSDT",
    timeframe: "1h",
    direction: "long",
    entry_rationale: "Plan",
    emotions: [],
    mistakes: [],
    result: "win",
    tags: [],
    screenshot_refs: [],
    created_at: "2026-07-21T12:00:00.000Z",
    ...overrides,
  };
}

type HubData = {
  portfolio: SourceResult<PaperPortfolioResponse>;
  dashboard: SourceResult<DashboardSummary>;
  openPositions: SourceResult<PaginatedPositions>;
  closedPositions: SourceResult<PaginatedPositions>;
  journal: SourceResult<PaginatedJournalEntries>;
};

function completeData(overrides: Partial<HubData> = {}): HubData {
  return {
    portfolio: ok(samplePortfolio),
    dashboard: ok(makeDashboard()),
    openPositions: ok({
      items: [makePosition({ id: "pos-open-1", status: "open" })],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    closedPositions: ok({
      items: [
        makePosition({ id: "pos-closed-1", status: "closed", symbol: "ETHUSDT", realized_pnl: "40" }),
        makePosition({
          id: "pos-closed-2",
          status: "closed",
          symbol: "SOLUSDT",
          realized_pnl: "-10",
          closed_at: "2026-07-22T10:00:00.000Z",
        }),
      ],
      total: 2,
      limit: 50,
      offset: 0,
    }),
    journal: ok({
      items: [makeEntry({ id: "entry-1", linked_position_id: "pos-closed-1" })],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    ...overrides,
  };
}

let asyncState = {
  data: completeData() as HubData | null,
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: (loader: () => Promise<unknown>, deps: unknown[]) => {
    void loader;
    void deps;
    return asyncState;
  },
}));

describe("Portfolio & Risk command centre", () => {
  afterEach(() => {
    cleanup();
    portfolioMock.mockClear();
    dashboardMock.mockClear();
    positionsMock.mockClear();
    journalMock.mockClear();
  });

  beforeEach(() => {
    safetyPosture.executionMode = "paper";
    safetyPosture.realTradingEnabled = false;
    safetyPosture.postureKnown = true;
    appContext.killSwitchError = null;
    appContext.loading = false;
    appContext.killSwitchStatus = {
      organization_id: "org",
      active: false,
      reason: null,
      activated_by: null,
      activated_at: null,
      deactivated_by: null,
      deactivated_at: null,
      version: 1,
      scope: "org",
      global_active: false,
      execution_blocked: false,
    };
    asyncState = {
      data: completeData(),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  });

  it("renders initial loading state", () => {
    asyncState = { data: null, loading: true, error: null, reload: vi.fn() };
    render(<PaperPortfolioPage />);
    expect(screen.getByText(/loading paper portfolio/i)).toBeInTheDocument();
  });

  it("renders complete portfolio data with command centre sections", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("paper-portfolio-page")).toBeInTheDocument();
    expect(screen.getByTestId("account-overview-panel")).toBeInTheDocument();
    expect(screen.getByTestId("risk-posture-panel")).toBeInTheDocument();
    expect(screen.getByTestId("open-positions-panel")).toBeInTheDocument();
    expect(screen.getByTestId("closed-positions-panel")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-history-panel")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-current-equity")).toHaveTextContent("10,450");
    expect(screen.getByTestId("portfolio-realized-pnl")).toHaveTextContent("450");
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/allowed/i);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("shows portfolio source failure without inventing zero balances", () => {
    asyncState = {
      data: completeData({ portfolio: failed("Portfolio unavailable") }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("account-overview-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-current-equity")).not.toBeInTheDocument();
    expect(screen.getByTestId("portfolio-sources-partial")).toBeInTheDocument();
    expect(screen.getAllByText(/Portfolio unavailable/i).length).toBeGreaterThan(0);
  });

  it("shows risk source failure without claiming trading allowed", () => {
    asyncState = {
      data: completeData({ dashboard: failed("Risk state unavailable") }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/unavailable/i);
    expect(screen.getByTestId("portfolio-risk-attention-summary")).toHaveTextContent(
      /cannot be confirmed|failed/i,
    );
    expect(screen.queryByText(/^Trading allowed$/i)).not.toBeInTheDocument();
  });

  it("supports partial sources — available sections remain, failed ones stay honest", () => {
    asyncState = {
      data: completeData({
        openPositions: failed("Open positions down"),
        journal: failed("Journal down"),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-sources-partial")).toBeInTheDocument();
    expect(screen.getByTestId("account-overview-panel")).toBeInTheDocument();
    expect(screen.getByTestId("open-positions-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("open-positions-empty")).not.toBeInTheDocument();
  });

  it("shows missing equity / pnl / timestamps as unavailable, not zero", () => {
    asyncState = {
      data: completeData({
        portfolio: ok({
          ...samplePortfolio,
          account: {
            ...samplePortfolio.account,
            current_equity: "",
            cumulative_realized_pnl: "",
            unrealized_pnl: null,
            as_of: "",
          },
          daily_series: [],
        }),
        dashboard: ok(
          makeDashboard({
            net_pnl_today_paper: null,
          }),
        ),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-current-equity-unavailable")).toHaveTextContent(
      /unavailable/i,
    );
    expect(screen.getByTestId("portfolio-realized-pnl-unavailable")).toHaveTextContent(
      /unavailable/i,
    );
    expect(screen.getByTestId("portfolio-unrealized-pnl-unavailable")).toHaveTextContent(
      /unavailable/i,
    );
    expect(screen.getByTestId("portfolio-snapshot-time")).toHaveTextContent(
      /freshness unavailable/i,
    );
    expect(screen.getByTestId("portfolio-daily-pnl-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("risk-daily-pnl-unavailable")).toBeInTheDocument();
  });

  it("labels daily P&L and drawdown honestly without inventing current drawdown", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-daily-pnl")).toHaveTextContent(/Today's paper P&L/i);
    expect(screen.getByTestId("portfolio-daily-pnl-source")).toHaveTextContent(
      /today's paper discipline/i,
    );
    expect(screen.getByTestId("portfolio-latest-daily-drawdown")).toHaveTextContent(
      /Latest daily drawdown in selected range/i,
    );
    expect(screen.getByTestId("portfolio-max-drawdown")).toHaveTextContent(/Max drawdown/i);
    expect(screen.queryByText(/Current drawdown/i)).not.toBeInTheDocument();
  });

  it("labels latest selected-range daily P&L when discipline today P&L is missing", () => {
    asyncState = {
      data: completeData({
        dashboard: ok(makeDashboard({ net_pnl_today_paper: null })),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-daily-pnl")).toHaveTextContent(
      /Latest daily P&L in selected range/i,
    );
    expect(screen.getByTestId("portfolio-daily-pnl-source")).toHaveTextContent(
      /not claimed as today/i,
    );
  });

  it("does not mark empty equity curve as truncated portfolio coverage", () => {
    asyncState = {
      data: completeData({
        portfolio: ok({
          ...samplePortfolio,
          equity_curve: [],
          daily_series: [],
        }),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-source-coverage-portfolio-performance")).toHaveTextContent(
      /complete/i,
    );
    expect(screen.getByTestId("portfolio-history-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-history-partial")).not.toBeInTheDocument();
  });

  it("does not claim trading allowed when kill-switch is null without error while loading", () => {
    appContext.killSwitchStatus = null;
    appContext.killSwitchError = null;
    appContext.loading = true;
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).not.toHaveTextContent(/^Trading allowed$/i);
    expect(screen.getByTestId("portfolio-risk-attention-summary")).toHaveTextContent(/loading/i);
    expect(screen.getByTestId("portfolio-source-kill-switch")).toHaveTextContent(/Unavailable/i);
  });

  it("marks kill-switch source unavailable for cached clear + refresh error and never allows trading", () => {
    appContext.killSwitchStatus = {
      organization_id: "org",
      active: false,
      reason: null,
      activated_by: null,
      activated_at: null,
      deactivated_by: null,
      deactivated_at: null,
      version: 1,
      scope: "org",
      global_active: false,
      execution_blocked: false,
    };
    appContext.killSwitchError = "refresh failed";
    appContext.loading = false;
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-source-kill-switch")).toHaveTextContent(/Unavailable/i);
    expect(screen.getByTestId("portfolio-source-kill-switch")).toHaveTextContent(/Freshness timestamp: unavailable/i);
    expect(screen.getByTestId("risk-trading-state")).not.toHaveTextContent(/^Trading allowed$/i);
    expect(screen.getByTestId("portfolio-source-daily-discipline")).toHaveTextContent(/Available/i);
  });

  it("keeps authoritative BLOCK when cached blocked status remains after refresh error", () => {
    appContext.killSwitchStatus = {
      organization_id: "org",
      active: true,
      reason: "Manual halt",
      activated_by: "user",
      activated_at: "2026-07-27T10:00:00.000Z",
      deactivated_by: null,
      deactivated_at: null,
      version: 2,
      scope: "org",
      global_active: false,
      execution_blocked: true,
    };
    appContext.killSwitchError = "refresh failed";
    appContext.loading = false;
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/blocked/i);
    expect(screen.getByTestId("portfolio-risk-block")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-source-kill-switch")).toHaveTextContent(/Unavailable/i);
    expect(screen.getByTestId("portfolio-source-kill-switch")).toHaveTextContent(
      /Freshness timestamp: unavailable/i,
    );
  });

  it("renders RiskBlock for blocked kill switch while portfolio data is still loading", () => {
    appContext.killSwitchStatus = {
      organization_id: "org",
      active: true,
      reason: "Manual halt",
      activated_by: "user",
      activated_at: "2026-07-27T10:00:00.000Z",
      deactivated_by: null,
      deactivated_at: null,
      version: 2,
      scope: "org",
      global_active: false,
      execution_blocked: true,
    };
    asyncState = { data: null, loading: true, error: null, reload: vi.fn() };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-risk-block")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-risk-block")).toHaveTextContent(/Manual halt/);
  });

  it("renders RiskBlock for blocked kill switch when the discipline source failed", () => {
    appContext.killSwitchStatus = {
      organization_id: "org",
      active: true,
      reason: "Manual halt",
      activated_by: "user",
      activated_at: "2026-07-27T10:00:00.000Z",
      deactivated_by: null,
      deactivated_at: null,
      version: 2,
      scope: "org",
      global_active: false,
      execution_blocked: true,
    };
    asyncState = {
      data: completeData({ dashboard: failed("Risk state unavailable") }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/blocked/i);
    expect(screen.getByTestId("portfolio-risk-block")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-risk-block")).toHaveTextContent(/Manual halt/);
    expect(screen.getByTestId("risk-daily-loss-status")).toHaveTextContent(/unavailable/i);
  });

  it("renders RiskBlock for blocked kill switch when the discipline snapshot is missing", () => {
    appContext.killSwitchStatus = {
      organization_id: "org",
      active: true,
      reason: "Manual halt",
      activated_by: "user",
      activated_at: "2026-07-27T10:00:00.000Z",
      deactivated_by: null,
      deactivated_at: null,
      version: 2,
      scope: "org",
      global_active: false,
      execution_blocked: true,
    };
    asyncState = {
      data: completeData({
        dashboard: ok({ ...makeDashboard(), daily_discipline: null }),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/blocked/i);
    expect(screen.getByTestId("portfolio-risk-block")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-risk-block")).toHaveTextContent(/Manual halt/);
    expect(screen.getByTestId("risk-daily-loss-status")).toHaveTextContent(/unavailable/i);
  });

  it("confirms no open positions only with complete coverage", () => {
    asyncState = {
      data: completeData({
        openPositions: ok({ items: [], total: 0, limit: 50, offset: 0 }),
        dashboard: ok({
          ...makeDashboard(),
          open_paper_trades: [],
          open_paper_trades_summary: {
            proposal_flow_count: 0,
            paper_validation_count: 0,
            total_count: 0,
            total_open_exposure: null,
            items: [],
            limitations: [],
          },
        }),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("open-positions-empty")).toHaveTextContent(/complete coverage/i);
  });

  it("does not show empty open positions when the open-position source failed", () => {
    asyncState = {
      data: completeData({ openPositions: failed("boom") }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("open-positions-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("open-positions-empty")).not.toBeInTheDocument();
  });

  it("reports truncated open positions honestly", () => {
    asyncState = {
      data: completeData({
        openPositions: ok({
          items: [makePosition({ id: "pos-open-1", status: "open" })],
          total: 9,
          limit: 1,
          offset: 0,
        }),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("open-positions-coverage")).toHaveTextContent(/1 of 9/);
  });

  it("shows risk allowed / warning / blocked / cooldown states", () => {
    const { rerender } = render(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/allowed/i);

    asyncState = {
      data: completeData({
        dashboard: ok(makeDashboard({ discipline_status: "caution", overtrading_warning_active: true })),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    rerender(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/warned/i);
    expect(screen.getByTestId("risk-cooldown-status")).toHaveTextContent(/active/i);

    asyncState = {
      data: completeData({
        dashboard: ok(
          makeDashboard({
            loss_lock_active: true,
            discipline_status: "locked",
            reasons: ["Daily loss limit reached"],
          }),
        ),
      }),
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    rerender(<PaperPortfolioPage />);
    expect(screen.getByTestId("risk-trading-state")).toHaveTextContent(/blocked/i);
    expect(screen.getByTestId("portfolio-risk-block")).toBeInTheDocument();
    expect(screen.getByTestId("risk-daily-loss-status")).toHaveTextContent(/active/i);
  });

  it("uses confirmed paper posture wording and fail-closed unverified posture", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("portfolio-account-mode")).toHaveTextContent(/simulated paper/i);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );

    cleanup();
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    asyncState = { data: completeData(), loading: false, error: null, reload: vi.fn() };
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
    expect(screen.getByTestId("portfolio-account-mode")).toHaveTextContent(/not confirmed/i);
  });

  it("creates relationship links only from real identifiers and omits missing ones", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("open-position-strategy-link-pos-open-1")).toHaveAttribute(
      "href",
      "/strategy-lab/strat-1",
    );
    expect(screen.getByTestId("open-position-positions-link-pos-open-1")).toHaveAttribute(
      "href",
      "/positions",
    );
    expect(screen.getByTestId("open-position-positions-link-pos-open-1")).toHaveTextContent(
      /View positions/i,
    );
    expect(screen.getByTestId("closed-position-journal-link-pos-closed-1")).toHaveAttribute(
      "href",
      "/journal?entry=entry-1",
    );
    expect(screen.getByTestId("closed-position-journal-link-pos-closed-2")).toHaveAttribute(
      "href",
      expect.stringContaining("position_id=pos-closed-2"),
    );
  });

  it("uses mobile card structure for closed positions and clears bottom nav padding", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("closed-positions-mobile")).toHaveClass("md:hidden");
    expect(screen.getByTestId("closed-positions-desktop")).toHaveClass("hidden");
    expect(screen.getByTestId("paper-portfolio-page").className).toMatch(/pb-24/);
    expect(screen.getByRole("heading", { name: /account overview/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /risk posture/i })).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-hub-nav")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-hub-safety")).not.toBeInTheDocument();
  });

  it("keeps portfolio filters wired and has no unsafe live CTAs", () => {
    render(<PaperPortfolioPage />);
    fireEvent.change(screen.getByTestId("portfolio-filter-start-date"), {
      target: { value: "2026-01-01" },
    });
    fireEvent.change(screen.getByTestId("portfolio-filter-source"), {
      target: { value: "proposal_flow" },
    });
    expect(screen.getByTestId("portfolio-filter-start-date")).toHaveValue("2026-01-01");
    expect(screen.getByTestId("portfolio-filter-source")).toHaveValue("proposal_flow");
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.getByTestId("paper-portfolio-related-links")).toHaveTextContent(/Risk settings/i);
  });

  it("renders charts and breakdowns when portfolio source is available", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("paper-portfolio-charts")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-breakdown-symbol")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-breakdown-symbol-row-BTCUSDT")).toBeInTheDocument();
  });

  it("keeps /portfolio route reachable with existing page test id", () => {
    render(<PaperPortfolioPage />);
    expect(screen.getByTestId("paper-portfolio-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });
});
