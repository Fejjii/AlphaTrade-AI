import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BacktestPanel } from "@/components/strategy/BacktestPanel";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";
import type { BacktestRun, BacktestRunCreate } from "@/lib/api/types";

const completedRun: BacktestRun = {
  id: "run-abc-123",
  strategy_id: "s1",
  strategy_version_id: null,
  organization_id: "org-1",
  user_id: "user-1",
  status: "completed",
  assumptions: {
    symbol: "BTCUSDT",
    exchange: "binance",
    timeframe: "4h",
    initial_capital: "10000",
    fees_bps: "4",
    slippage_bps: "5",
    risk_per_trade_pct: "1",
  },
  result: {
    metrics: {
      trade_count: 5,
      win_rate: 0.6,
      profit_factor: 1.5,
      expectancy: "25",
      max_drawdown_pct: 4,
      average_win: "100",
      average_loss: "50",
      largest_win: "200",
      largest_loss: "80",
      consecutive_losses: 1,
      average_time_in_trade_bars: 3,
      total_fees: "10",
      total_slippage: "5",
      net_pnl: "125",
      return_pct: 1.25,
      ending_equity: "10125",
      symbol: "BTCUSDT",
      timeframe: "4h",
    },
    recommendation: "backtested",
    note: "Historical simulation only — not a guarantee of future performance. Real trading remains disabled.",
  },
  created_at: "2026-07-24T10:00:00Z",
  updated_at: "2026-07-24T10:05:00Z",
};

describe("BacktestPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders backtest form and disclaimer", () => {
    render(
      <BacktestPanel
        strategyId="s1"
        onRun={vi.fn()}
        onLoadTrades={vi.fn()}
      />,
    );
    expect(screen.getByText(/Backtest v2/)).toBeInTheDocument();
    expect(screen.getByText(/Real trading remains disabled/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run backtest/i })).toBeInTheDocument();
  });

  it("submits expanded assumptions with idempotency_key and split_config", async () => {
    const onRun = vi.fn().mockResolvedValue(completedRun);
    const onLoadTrades = vi.fn().mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    render(
      <BacktestPanel
        strategyId="s1"
        onRun={onRun}
        onLoadTrades={onLoadTrades}
      />,
    );

    fireEvent.change(screen.getByLabelText("Funding rate (bps / 8h)"), {
      target: { value: "2.5" },
    });
    fireEvent.change(screen.getByLabelText("Runner trail %"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Mode"), { target: { value: "holdout" } });
    fireEvent.change(screen.getByLabelText("OOS fraction (0–1)"), { target: { value: "0.25" } });

    fireEvent.click(screen.getByRole("button", { name: /Run backtest/i }));

    await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));

    const body = onRun.mock.calls[0][0] as BacktestRunCreate;
    expect(body.idempotency_key).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(body.assumptions?.funding_rate_bps_per_8h).toBe("2.5");
    expect(body.assumptions?.runner_trail_pct).toBe("2");
    expect(body.assumptions?.split_config).toEqual({
      mode: "holdout",
      oos_fraction: 0.25,
      window_bars: null,
      step_bars: null,
    });
    expect(body.assumptions?.start_date).toBe("2024-01-01");
    expect(body.assumptions?.end_date).toBe("2024-06-01");
    expect(body.assumptions?.initial_capital).toBe("10000");

    expect(await screen.findByRole("link", { name: /View run detail/i })).toHaveAttribute(
      "href",
      "/backtests/run-abc-123",
    );
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
        eligibility={null}
        busy={false}
        signals={[]}
        trades={[]}
        onStart={vi.fn()}
        onScan={vi.fn()}
        onTick={vi.fn()}
        onStop={vi.fn()}
        scheduler={null}
        history={[]}
        alerts={[]}
        onSchedulerTick={vi.fn()}
        onMarkAlertRead={vi.fn()}
      />,
    );
    expect(screen.getByText(/Paper validation/)).toBeInTheDocument();
    expect(screen.getByText(/Paper trades: 2/)).toBeInTheDocument();
  });
});
