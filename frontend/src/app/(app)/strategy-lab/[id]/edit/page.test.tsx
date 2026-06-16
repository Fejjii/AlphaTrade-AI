import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import EditStrategyPage from "@/app/(app)/strategy-lab/[id]/edit/page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "test-id" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      setup_type: "htf_trend_pullback",
      latest_card: {
        strategy_name: "Test",
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
        validation_status: "draft",
      },
    },
    loading: false,
    error: null,
  }),
}));

describe("EditStrategyPage", () => {
  it("renders strategy edit form", () => {
    render(<EditStrategyPage />);
    expect(screen.getByText("Edit strategy")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Test")).toBeInTheDocument();
  });
});
