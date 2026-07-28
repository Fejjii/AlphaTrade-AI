import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import StrategyDetailPage from "./page";

const {
  strategy,
  paperValidationMock,
  paperEligibilityMock,
  schedulerStatusMock,
  schedulerHistoryMock,
  paperSignalsMock,
  paperTradesMock,
  alertsListMock,
} = vi.hoisted(() => {
  const strategy = {
    id: "strat-1",
    name: "HTF Pullback",
    setup_type: "htf_trend_pullback",
    current_version: 2,
    enabled: true,
    validation_status: "in_review",
    backtest_status: "completed",
    paper_validation_status: "in_progress",
    paper_eligible: true,
    latest_card: {
      strategy_name: "HTF Pullback",
      market_type: "crypto_perp",
      asset_universe: ["BTCUSDT"],
      timeframes: ["4h"],
      entry_conditions: ["entry"],
      confirmation_conditions: ["confirm"],
      invalidation: ["invalid"],
      stop_loss: ["stop"],
      take_profit_plan: ["tp"],
      runner_plan: ["runner"],
      position_sizing: ["size"],
      add_rules: [],
      no_trade_rules: ["no"],
      backtest_rules: [],
      success_criteria: [],
      validation_status: "in_review",
    },
    created_at: "2026-07-20T10:00:00.000Z",
    updated_at: "2026-07-21T10:00:00.000Z",
  };
  return {
    strategy,
    paperValidationMock: vi.fn(),
    paperEligibilityMock: vi.fn(),
    schedulerStatusMock: vi.fn(),
    schedulerHistoryMock: vi.fn(),
    paperSignalsMock: vi.fn(),
    paperTradesMock: vi.fn(),
    alertsListMock: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "strat-1" }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: (loader: () => Promise<unknown>) => {
    const key = String(loader);
    if (key.includes("testability")) {
      return {
        data: {
          has_structured_rules: true,
          ready_for_backtest: true,
          structured_rules: null,
        },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    if (key.includes("listVersions")) {
      return {
        data: { items: [], total: 0, limit: 50, offset: 0 },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    return {
      data: strategy,
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  },
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      strategies: {
        ...actual.api.strategies,
        get: vi.fn().mockResolvedValue(strategy),
        paperValidation: (...args: unknown[]) => paperValidationMock(...args),
        paperEligibility: (...args: unknown[]) => paperEligibilityMock(...args),
        schedulerStatus: (...args: unknown[]) => schedulerStatusMock(...args),
        schedulerHistory: (...args: unknown[]) => schedulerHistoryMock(...args),
        paperValidationSignals: (...args: unknown[]) => paperSignalsMock(...args),
        paperValidationTrades: (...args: unknown[]) => paperTradesMock(...args),
      },
      alerts: {
        ...actual.api.alerts,
        list: (...args: unknown[]) => alertsListMock(...args),
      },
    },
  };
});

beforeEach(() => {
  paperValidationMock.mockReset();
  paperEligibilityMock.mockReset();
  schedulerStatusMock.mockReset();
  schedulerHistoryMock.mockReset();
  paperSignalsMock.mockReset();
  paperTradesMock.mockReset();
  alertsListMock.mockReset();

  paperValidationMock.mockResolvedValue({
    strategy_id: "strat-1",
    paper_eligible: true,
    runs: [{ id: "run-1", status: "in_progress", metrics: null }],
    total: 1,
  });
  paperEligibilityMock.mockResolvedValue({
    strategy_id: "strat-1",
    status: "paper_eligible",
    paper_eligible: true,
    recommendation: "continue",
    testability_score: 80,
    limitations: [],
    eligibility_reasons: [],
    blockers: [],
    real_trading_enabled: false,
    accepted_lessons: [],
    unresolved_lesson_candidates: [],
  });
  schedulerStatusMock.mockResolvedValue({
    env_enabled: false,
    tenant_enabled: false,
    effective_enabled: false,
    config: {
      enabled: false,
      interval_seconds: 300,
      max_runs_per_cycle: 5,
      max_scans_per_minute: 10,
    },
    real_trading_enabled: false,
    limitation: "Paper only",
  });
  schedulerHistoryMock.mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
  paperSignalsMock.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  paperTradesMock.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  alertsListMock.mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
});

afterEach(() => {
  cleanup();
});

describe("StrategyDetailPage paper-source honesty", () => {
  it("loads paper sources through one consolidated path and exposes empty states", async () => {
    render(<StrategyDetailPage />);
    expect(screen.getByTestId("strategy-detail-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("strategy-paper-source-paper-trades")).toHaveTextContent(
        /Loaded — empty/i,
      );
    });
    expect(paperValidationMock).toHaveBeenCalled();
    expect(paperEligibilityMock).toHaveBeenCalled();
    expect(paperSignalsMock.mock.calls.length).toBe(paperValidationMock.mock.calls.length);
    expect(paperTradesMock.mock.calls.length).toBe(paperValidationMock.mock.calls.length);
    expect(paperSignalsMock).toHaveBeenCalledWith("run-1");
  });

  it("surfaces paper validation summary failures instead of swallowing them", async () => {
    paperValidationMock.mockRejectedValue(new Error("summary down"));
    render(<StrategyDetailPage />);
    await waitFor(() => {
      expect(
        screen.getByTestId("strategy-paper-source-paper-validation-summary"),
      ).toHaveTextContent(/Unavailable.*summary down/i);
    });
  });
});
