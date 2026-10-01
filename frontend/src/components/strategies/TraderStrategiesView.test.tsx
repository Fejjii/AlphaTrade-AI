import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TraderStrategiesView } from "@/components/strategies/TraderStrategiesView";
import { okSource } from "@/components/workflows/sourceResult";
import type {
  JournalEntry,
  JournalStatsResponse,
  PaginatedUserStrategies,
  UserStrategy,
} from "@/lib/api/types";

const listVersions = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({
  api: {
    strategies: {
      listVersions: listVersions,
    },
  },
}));

const strategy = {
  id: "s1",
  name: "HTF Pullback",
  setup_type: "htf_pullback",
  current_version: 3,
  enabled: true,
  latest_card: {
    strategy_name: "HTF Pullback",
    market_type: "perp",
    asset_universe: ["BTCUSDT"],
    timeframes: ["1h"],
    entry_conditions: ["Pullback to the level"],
    confirmation_conditions: ["Rejection wick"],
    invalidation: ["Close beyond the level"],
    stop_loss: ["Below the swing"],
    take_profit_plan: [],
    runner_plan: [],
    position_sizing: [],
    add_rules: [],
    no_trade_rules: ["Skip news"],
    backtest_rules: [],
    success_criteria: [],
    validation_status: "draft",
  },
  validation_status: "draft",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
} as unknown as UserStrategy;

describe("Trader strategies", () => {
  afterEach(() => {
    cleanup();
    listVersions.mockReset();
  });

  it("shows rules, matched performance, evidence, and versions", async () => {
    listVersions.mockResolvedValue({
      items: [{ id: "v3", version: 3, validation_status: "draft" }],
      total: 1,
      limit: 20,
      offset: 0,
    });
    render(
      <TraderStrategiesView
        data={{
          strategies: okSource({ items: [strategy], total: 1, limit: 50, offset: 0 } as PaginatedUserStrategies),
          stats: okSource({
            buckets: [
              {
                key: "s1",
                group_id: "s1",
                label: "HTF Pullback",
                metrics: { trade_count: 2, win_rate: 0.5, net_pnl_total: "10" },
              },
            ],
          } as JournalStatsResponse),
          journal: okSource({
            items: [
              {
                id: "j1",
                strategy_id: "s1",
                screenshot_refs: ["https://example.com/chart.png", "local-note"],
              } as unknown as JournalEntry,
            ],
          }),
        }}
      />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Strategies" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Strategy Lab" })).toHaveAttribute("href", "/strategy-lab");
    expect(screen.getByRole("link", { name: "Knowledge" })).toHaveAttribute("href", "/knowledge");
    fireEvent.click(screen.getByTestId("strategy-row"));
    expect(await screen.findByText("Pullback to the level")).toBeInTheDocument();
    expect(screen.getByText("Skip news")).toBeInTheDocument();
    expect(screen.getByText(/win rate 50.0%/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "https://example.com/chart.png" })).toHaveAttribute(
      "href",
      "https://example.com/chart.png",
    );
    expect(screen.getByText("local-note")).toBeInTheDocument();
    expect(await screen.findByText("v3 · draft")).toBeInTheDocument();
    expect(listVersions).toHaveBeenCalledWith("s1");
  });
});
