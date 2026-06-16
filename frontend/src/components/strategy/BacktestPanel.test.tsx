import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BacktestPanel } from "@/components/strategy/BacktestPanel";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";

describe("BacktestPanel", () => {
  it("renders backtest form and disclaimer", () => {
    render(
      <BacktestPanel
        strategyId="s1"
        onRun={vi.fn()}
        onLoadTrades={vi.fn()}
      />,
    );
    expect(screen.getByText(/Backtest v1/)).toBeInTheDocument();
    expect(screen.getByText(/Real trading remains disabled/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run backtest/i })).toBeInTheDocument();
  });
});

describe("PaperValidationPanel", () => {
  it("renders paper validation metrics section", () => {
    render(
      <PaperValidationPanel
        summary={{
          strategy_id: "s1",
          paper_eligible: false,
          runs: [
            {
              id: "r1",
              strategy_id: "s1",
              status: "in_progress",
              paper_eligible: false,
              metrics: {
                paper_trades_count: 2,
                win_rate: 0.5,
                net_pnl: "10",
                profit_factor: 1.2,
                expectancy: "5",
                max_drawdown_pct: 3,
              },
              created_at: "",
              updated_at: "",
            },
          ],
          total: 1,
        }}
        busy={false}
        onStart={vi.fn()}
      />,
    );
    expect(screen.getByText(/Paper validation metrics/)).toBeInTheDocument();
    expect(screen.getByText(/Paper trades: 2/)).toBeInTheDocument();
  });
});
