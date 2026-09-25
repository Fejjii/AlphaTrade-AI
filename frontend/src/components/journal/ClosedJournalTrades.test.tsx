import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ClosedJournalTrades } from "./ClosedJournalTrades";

describe("ClosedJournalTrades", () => {
  afterEach(() => cleanup());

  it("shows symbol, timeframe, entry, exit, reason, outcome, fees, and PnL", () => {
    render(
      <ClosedJournalTrades
        trades={[
          {
            id: "trade-1",
            symbol: "BTC-USDT",
            timeframe: "15m",
            direction: "long",
            status: "closed",
            thesis: "Canonical paper execution of an approved TradePlanRevision.",
            entry_price: "100000",
            exit_price: "100010",
            exit_reason: "take_profit",
            fees: "0.5",
            net_pnl: "9.5",
            result: "win",
            strategy_version_id: "strategy-version-1",
            strategy_label: "Pullback",
          },
        ]}
      />,
    );
    const row = screen.getByTestId("closed-journal-trade");
    expect(row).toHaveTextContent("BTC-USDT");
    expect(row).toHaveTextContent("15m");
    expect(row).toHaveTextContent("win");
    expect(row).toHaveTextContent("Entry 100000");
    expect(row).toHaveTextContent("exit 100010");
    expect(row).toHaveTextContent("reason take_profit");
    expect(row).toHaveTextContent("PnL 9.5");
    expect(row).toHaveTextContent("fees 0.5");
    expect(row).toHaveTextContent("Pullback");
    expect(row).toHaveTextContent("Trade reason: Canonical paper execution");
  });
});
