import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";

describe("PaperValidationPanel", () => {
  it("renders dashboard controls and disclaimer", () => {
    render(
      <PaperValidationPanel
        summary={{
          strategy_id: "s1",
          paper_eligible: true,
          runs: [
            {
              id: "run1",
              strategy_id: "s1",
              status: "in_progress",
              runtime_mode: "scan_only",
              paper_eligible: true,
              metrics: {
                paper_trades_count: 2,
                win_rate: 0.5,
                net_pnl: "10",
                profit_factor: 1.2,
                expectancy: "5",
                max_drawdown_pct: 3.5,
              },
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-01-01T00:00:00Z",
            },
          ],
          total: 1,
        }}
        eligibility={{
          strategy_id: "s1",
          status: "paper_eligible",
          paper_eligible: true,
          recommendation: "continue",
          testability_score: 80,
          limitations: ["Paper only"],
          eligibility_reasons: [],
          blockers: [],
          real_trading_enabled: false,
          accepted_lessons: [],
          unresolved_lesson_candidates: [],
        }}
        busy={false}
        signals={[
          {
            id: "sig1",
            triggered: true,
            status: "detected",
            symbol: "BTCUSDT",
            direction: "long",
            confidence: 0.8,
            created_at: "2024-01-01T00:00:00Z",
          },
        ]}
        trades={[
          {
            id: "t1",
            status: "closed",
            symbol: "BTCUSDT",
            direction: "long",
            net_pnl: "5",
            exit_reason: "take_profit_1",
            created_at: "2024-01-01T00:00:00Z",
          },
        ]}
        onStart={vi.fn()}
        onScan={vi.fn()}
        onTick={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    expect(screen.getByTestId("paper-validation-panel")).toBeInTheDocument();
    expect(screen.getByTestId("paper-only-disclaimer")).toBeInTheDocument();
    expect(screen.getByTestId("start-paper-validation")).toBeInTheDocument();
    expect(screen.getByTestId("scan-paper-validation")).toBeInTheDocument();
    expect(screen.getByTestId("tick-paper-validation")).toBeInTheDocument();
    expect(screen.getByTestId("paper-signals-list")).toBeInTheDocument();
    expect(screen.getByTestId("paper-trades-table")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-metrics")).toBeInTheDocument();
    expect(screen.getByTestId("max-drawdown-metric")).toHaveTextContent("Max DD");
  });
});
