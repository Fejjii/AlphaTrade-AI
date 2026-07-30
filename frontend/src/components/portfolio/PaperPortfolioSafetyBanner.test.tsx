import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  PaperPortfolioSafetyBanner,
  STANDARD_PAPER_PORTFOLIO_DISCLAIMER,
  executionModeHonestyLabel,
  shouldSuppressPaperPortfolioSafetyBanner,
} from "@/components/portfolio/PaperPortfolioSafetyBanner";
import type { PaperPortfolioSafetyBanner as SafetyBanner } from "@/lib/api/types";

afterEach(cleanup);

function safety(overrides: Partial<SafetyBanner> = {}): SafetyBanner {
  return {
    execution_mode: "paper",
    paper_only: true,
    real_trading_enabled: false,
    disclaimer: STANDARD_PAPER_PORTFOLIO_DISCLAIMER,
    ...overrides,
  };
}

describe("PaperPortfolioSafetyBanner (FP2-123 honesty)", () => {
  it("suppresses only redundant standard verified-paper copy", () => {
    expect(shouldSuppressPaperPortfolioSafetyBanner(safety())).toBe(true);
    const { container } = render(<PaperPortfolioSafetyBanner safety={safety()} />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId("paper-portfolio-safety-banner")).not.toBeInTheDocument();
    expect(screen.queryByText(/Not live trading/i)).not.toBeInTheDocument();
  });

  it("never suppresses live execution mode even when paper_only and real trading disabled", () => {
    const payload = safety({ execution_mode: "live" });
    expect(shouldSuppressPaperPortfolioSafetyBanner(payload)).toBe(false);
    render(<PaperPortfolioSafetyBanner safety={payload} />);
    expect(screen.getByTestId("paper-portfolio-safety-banner")).toBeInTheDocument();
    expect(screen.getByTestId("paper-portfolio-execution-mode")).toHaveTextContent(
      "Live execution mode",
    );
    expect(screen.queryByText(/Not live trading/i)).not.toBeInTheDocument();
  });

  it("never suppresses trade execution mode and labels it as live", () => {
    render(<PaperPortfolioSafetyBanner safety={safety({ execution_mode: "trade" })} />);
    expect(screen.getByTestId("paper-portfolio-execution-mode")).toHaveTextContent(
      "Live execution mode",
    );
    expect(screen.queryByText(/Not live trading/i)).not.toBeInTheDocument();
  });

  it("never suppresses unknown or unexpected execution modes", () => {
    for (const mode of ["", "   ", "read_only", "shadow"]) {
      cleanup();
      const payload = safety({ execution_mode: mode });
      expect(shouldSuppressPaperPortfolioSafetyBanner(payload)).toBe(false);
      render(<PaperPortfolioSafetyBanner safety={payload} />);
      expect(screen.getByTestId("paper-portfolio-safety-banner")).toBeInTheDocument();
      expect(screen.getByTestId("paper-portfolio-execution-mode")).toHaveTextContent(
        executionModeHonestyLabel(mode),
      );
      expect(screen.queryByText(/Not live trading/i)).not.toBeInTheDocument();
    }
    expect(executionModeHonestyLabel("")).toBe("Execution mode unverified/unknown");
    expect(executionModeHonestyLabel("read_only")).toBe("Read Only execution mode");
  });

  it("keeps real trading enabled as a danger state", () => {
    render(
      <PaperPortfolioSafetyBanner
        safety={safety({
          real_trading_enabled: true,
          disclaimer: "Unexpected real trading posture.",
        })}
      />,
    );
    expect(screen.getByTestId("paper-portfolio-real-trading")).toHaveTextContent(
      /Real trading enabled/i,
    );
    expect(screen.getByTestId("paper-portfolio-disclaimer")).toHaveTextContent(
      /Unexpected real trading posture/i,
    );
    expect(screen.queryByText(/Not live trading/i)).not.toBeInTheDocument();
  });

  it("keeps paper_only false visible", () => {
    render(
      <PaperPortfolioSafetyBanner
        safety={safety({
          paper_only: false,
          disclaimer: "Paper-only not confirmed for this portfolio.",
        })}
      />,
    );
    expect(screen.getByTestId("paper-portfolio-paper-only")).toHaveTextContent(
      /Paper-only not confirmed/i,
    );
    expect(screen.getByTestId("paper-portfolio-no-real-money")).toHaveTextContent(
      /Does not indicate readiness for real money/i,
    );
  });

  it("never silently discards a dynamic disclaimer warning", () => {
    const dynamic =
      "Paper-only simulated portfolio. WARNING: venue mirror degraded — review before trusting exposure.";
    const payload = safety({ disclaimer: dynamic });
    expect(shouldSuppressPaperPortfolioSafetyBanner(payload)).toBe(false);
    render(<PaperPortfolioSafetyBanner safety={payload} />);
    expect(screen.getByTestId("paper-portfolio-disclaimer")).toHaveTextContent(dynamic);
    expect(screen.getByTestId("paper-portfolio-execution-mode")).toHaveTextContent(
      "Paper execution mode",
    );
  });

  it("preserves independent honesty fields when degraded", () => {
    render(
      <PaperPortfolioSafetyBanner
        safety={safety({
          execution_mode: "live",
          paper_only: false,
          real_trading_enabled: true,
          disclaimer: "Conflicting safety payload from backend.",
        })}
      />,
    );
    expect(screen.getByTestId("paper-portfolio-execution-mode")).toHaveTextContent(
      "Live execution mode",
    );
    expect(screen.getByTestId("paper-portfolio-paper-only")).toHaveTextContent(
      /Paper-only not confirmed/i,
    );
    expect(screen.getByTestId("paper-portfolio-real-trading")).toHaveTextContent(
      /Real trading enabled/i,
    );
    expect(screen.getByTestId("paper-portfolio-disclaimer")).toHaveTextContent(
      /Conflicting safety payload/i,
    );
    expect(screen.getByTestId("paper-portfolio-no-real-money")).toBeInTheDocument();
    expect(screen.queryByText(/Not live trading/i)).not.toBeInTheDocument();
  });
});
