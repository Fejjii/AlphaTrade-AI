import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PerpetualMarketStatusCard } from "./PerpetualMarketStatusCard";
import type { PerpetualMarketStatusView } from "@/lib/canonical-decision/types";

function replayStatus(): PerpetualMarketStatusView {
  return {
    symbol: "BTCUSDT",
    mode: "replay",
    availability: "replay",
    reason: "replay_fixture",
    lastUpdate: "2026-01-15T16:15:04.000Z",
    sourceLabel: "binance USD-M perpetual · BTCUSDT",
    providerName: "binance-usdm-perpetual-replay",
    providerHealth: "healthy",
    perpetual: true,
    watcherActivated: false,
    currentPrice: {
      usableAsCurrentMarketPrice: false,
      presentation: "replay_fixture",
      price: "91234.5",
      sourceTime: "2026-01-15T16:15:04.000Z",
      venueTradeId: "agg-1",
      isLive: false,
      isMock: true,
      fallbackUsed: false,
      freshnessState: "replay",
      freshnessPolicyVersion: "first-slice-btc-usdt-usdm-freshness/v1",
      ageSeconds: "1",
    },
    streamLabel: "continuous · gap none · warm-up complete",
    ohlcvLabel: "15m complete · 4h complete",
    cvdLabel: "complete · Δ -12.5",
    summary: "Replay fixture stream. This price is not a current live perpetual mark.",
  };
}

describe("PerpetualMarketStatusCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("labels replay fixture prices as not current live marks", () => {
    render(<PerpetualMarketStatusCard status={replayStatus()} />);
    const panel = screen.getByTestId("monitor-current-price");
    expect(panel).toHaveTextContent(/replay fixture/i);
    expect(panel).toHaveTextContent(/not a current live perpetual price/i);
    expect(screen.getByTestId("monitor-current-price-value")).toHaveTextContent("91,234.5");
    expect(screen.getByTestId("monitor-watcher-off")).toHaveTextContent(/watcher is not activated/i);
    expect(screen.queryByText("Live mark")).not.toBeInTheDocument();
  });

  it("shows rollback activation without calling the fixture a live mark", () => {
    render(
      <PerpetualMarketStatusCard
        status={{
          ...replayStatus(),
          activationLabel: "inactive · replay · 10s freshness · read-only",
        }}
      />,
    );
    expect(screen.getByTestId("monitor-activation")).toHaveTextContent(/inactive · replay/i);
    expect(screen.getByTestId("monitor-activation")).toHaveTextContent(/no exchange credentials/i);
    expect(screen.queryByText("Live mark")).not.toBeInTheDocument();
  });

  it("hides unusable live prices instead of showing a compatibility mark", () => {
    const unavailable: PerpetualMarketStatusView = {
      ...replayStatus(),
      mode: "live_perpetual",
      availability: "unavailable",
      reason: "provider_unavailable",
      currentPrice: {
        ...replayStatus().currentPrice,
        usableAsCurrentMarketPrice: false,
        presentation: "provider_unavailable",
        price: "65000",
        isLive: true,
        isMock: false,
        freshnessState: "unavailable",
      },
      summary: "Perpetual monitor failed closed.",
    };
    render(<PerpetualMarketStatusCard status={unavailable} />);
    expect(screen.getByTestId("monitor-current-price-value")).not.toHaveTextContent("65,000");
    expect(screen.getByTestId("monitor-current-price-label")).toHaveTextContent(
      /not a current live perpetual price/i,
    );
  });
});
