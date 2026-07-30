import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PaperPortfolioSafetyBanner } from "@/components/portfolio/PaperPortfolioSafetyBanner";

afterEach(cleanup);

describe("PaperPortfolioSafetyBanner (FP2-123)", () => {
  it("suppresses redundant verified paper posture chrome", () => {
    const { container } = render(
      <PaperPortfolioSafetyBanner
        safety={{
          execution_mode: "paper",
          paper_only: true,
          real_trading_enabled: false,
          disclaimer: "Paper-only simulated portfolio.",
        }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId("paper-portfolio-safety-banner")).not.toBeInTheDocument();
  });

  it("keeps honesty visible when real trading is enabled", () => {
    render(
      <PaperPortfolioSafetyBanner
        safety={{
          execution_mode: "paper",
          paper_only: true,
          real_trading_enabled: true,
          disclaimer: "Unexpected real trading posture.",
        }}
      />,
    );
    expect(screen.getByTestId("paper-portfolio-safety-banner")).toBeInTheDocument();
    expect(screen.getByText(/Real trading enabled/i)).toBeInTheDocument();
    expect(screen.getByText(/Unexpected real trading posture/i)).toBeInTheDocument();
  });

  it("keeps honesty visible when paper-only is not confirmed", () => {
    render(
      <PaperPortfolioSafetyBanner
        safety={{
          execution_mode: "live",
          paper_only: false,
          real_trading_enabled: false,
          disclaimer: "Paper-only not confirmed for this portfolio.",
        }}
      />,
    );
    expect(screen.getByTestId("paper-portfolio-safety-banner")).toBeInTheDocument();
    expect(screen.getByTestId("paper-portfolio-paper-only")).toHaveTextContent(
      /Paper-only not confirmed/i,
    );
  });
});
