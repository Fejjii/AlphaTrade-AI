import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderStatusCard } from "@/components/ProviderStatusCard";
import { StatusBadge } from "@/components/StatusBadge";

describe("Market status UI", () => {
  it("renders live market badge", () => {
    render(<StatusBadge label="Live market data" tone="healthy" />);
    expect(screen.getByText("Live market data")).toBeInTheDocument();
  });

  it("renders mock market badge", () => {
    render(<StatusBadge label="Mock market data" tone="paper" />);
    expect(screen.getByText("Mock market data")).toBeInTheDocument();
  });

  it("renders market data provider status card", () => {
    render(
      <ProviderStatusCard
        provider={{
          name: "binance-public",
          kind: "market_data",
          health: "healthy",
          using_fallback: false,
          is_mock: false,
          detail: "Binance public REST (read-only, no API key).",
          last_success_at: "2026-06-01T12:00:00Z",
        }}
      />,
    );
    expect(screen.getByText("binance-public")).toBeInTheDocument();
    expect(screen.getByText(/Binance public REST/)).toBeInTheDocument();
  });
});
