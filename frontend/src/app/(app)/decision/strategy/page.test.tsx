import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionStrategyPage from "./page";

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchStatus: { active: false, execution_blocked: false },
  }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    postureKnown: true,
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      quality: {
        data: {
          total_detectors: 4,
          detectors_with_data: 2,
          total_results: 9,
          ranked: [
            {
              condition: "liquidity_sweep",
              rank: 1,
              quality_score: 0.7,
              sample_size: 12,
              trust_tier: "medium",
              verdict: "watch",
            },
          ],
        },
        available: true,
      },
      learning: {
        data: {
          completed_sessions: 3,
          results_count: 3,
          lessons_count: 1,
        },
        available: true,
      },
      setups: {
        data: {
          setups: [
            {
              setup_type: "htf_trend_pullback",
              proposal_count: 2,
              paper_trade_count: 2,
              winning_paper_trades: 1,
              losing_paper_trades: 1,
              most_common_mistakes: [],
              most_common_lessons: [],
            },
          ],
        },
        available: true,
      },
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("Strategy performance page", () => {
  afterEach(() => cleanup());

  it("renders existing strategy and pattern APIs without promotion claims", () => {
    render(<DecisionStrategyPage />);
    expect(screen.getByTestId("strategy-performance")).toHaveTextContent("liquidity_sweep");
    expect(screen.getByText(/no automatic rule promotion/i)).toBeInTheDocument();
  });
});
