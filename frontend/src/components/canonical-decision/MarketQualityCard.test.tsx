import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarketQualityCard } from "@/components/canonical-decision/MarketQualityCard";
import type { MarketQualityView } from "@/lib/canonical-decision/types";

function replayQuality(): MarketQualityView {
  return {
    authority: "canonical",
    grade: "unknown",
    setupState: "unknown",
    dataQuality: "complete",
    confidence: null,
    confidencePenaltyApplied: false,
    symbol: "BTCUSDT",
    timeframe: "15m",
    direction: null,
    evidence: [
      {
        label: "Source",
        detail: "binance · perpetual · BTCUSDT · replay_fixture",
        isLive: false,
        fallbackUsed: false,
        stale: false,
        freshnessState: "replay",
      },
    ],
    summary: "Replay fixture evidence. Prices here are not live market marks.",
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
    doesNotGrantEligibility: true,
  };
}

describe("MarketQualityCard current-price honesty", () => {
  afterEach(() => cleanup());

  it("labels replay fixture prices and never shows Live for them", () => {
    render(<MarketQualityCard quality={replayQuality()} />);
    const panel = screen.getByTestId("canonical-current-price");
    expect(panel).toHaveTextContent("Replay fixture");
    expect(panel).toHaveTextContent("not a current market price");
    expect(screen.getByTestId("canonical-current-price-value")).toHaveTextContent("91,234.5");
    expect(panel.querySelector("[data-testid='freshness-pill']")).toHaveTextContent("Replay fixture");
    expect(panel).not.toHaveTextContent("Live");
  });

  it("does not invent a current price on compatibility views", () => {
    const quality = replayQuality();
    quality.authority = "compatibility_projection";
    quality.currentPrice = null;
    quality.evidence = [
      {
        label: "Market data",
        detail: "mock · mock-market-data (compatibility snapshot, not a canonical current price)",
        isLive: false,
        fallbackUsed: false,
        stale: false,
        freshnessState: "unavailable",
      },
    ];
    render(<MarketQualityCard quality={quality} />);
    expect(screen.queryByTestId("canonical-current-price")).not.toBeInTheDocument();
    expect(screen.getByText(/compatibility snapshot/i)).toBeInTheDocument();
    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });
});
