import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  PortfolioSourceAvailability,
  type PortfolioSourceStatus,
} from "@/components/portfolio/PortfolioSourceAvailability";

function healthySource(name: string): PortfolioSourceStatus {
  return { name, available: true, error: null, coverage: "complete", required: true };
}

describe("PortfolioSourceAvailability (FP2-221 partial coverage)", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows the all-healthy banner only when every source has complete coverage", () => {
    render(
      <PortfolioSourceAvailability
        sources={[
          healthySource("Portfolio performance"),
          healthySource("Closed positions"),
        ]}
      />,
    );
    expect(screen.getByTestId("portfolio-sources-all-healthy")).toBeInTheDocument();
  });

  it("suppresses the all-healthy banner when an available source reports partial failure", () => {
    render(
      <PortfolioSourceAvailability
        sources={[
          healthySource("Portfolio performance"),
          {
            name: "Closed positions",
            available: true,
            error: "Closed positions unavailable; showing liquidated positions only.",
            coverage: "unknown",
            required: true,
          },
        ]}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("portfolio-sources-all-healthy")).not.toBeInTheDocument();
    expect(screen.getByTestId("portfolio-sources-partial")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-source-badge-closed-positions")).toHaveTextContent(
      "Partial",
    );
    expect(screen.getByTestId("portfolio-source-error-closed-positions")).toHaveTextContent(
      /Closed positions unavailable/,
    );
    expect(screen.getByTestId("portfolio-sources-retry")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-source-list")).toBeInTheDocument();
  });

  it("exposes Retry sources for partial coverage without hiding source detail", () => {
    const onRetry = vi.fn();
    render(
      <PortfolioSourceAvailability
        sources={[
          healthySource("Portfolio performance"),
          {
            name: "Closed positions",
            available: true,
            error: "Liquidated positions unavailable; showing closed positions only.",
            coverage: "unknown",
            required: true,
          },
        ]}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(screen.getByTestId("portfolio-sources-retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("portfolio-sources-toggle")).not.toBeInTheDocument();
  });
});
