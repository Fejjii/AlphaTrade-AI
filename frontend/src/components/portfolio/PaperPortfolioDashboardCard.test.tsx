import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PaperPortfolioDashboardCard } from "./PaperPortfolioDashboardCard";
import { samplePortfolio } from "@/app/(app)/portfolio/sample-portfolio";

describe("PaperPortfolioDashboardCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows equity, realized PnL, recent daily PnL, and links to /portfolio", () => {
    render(<PaperPortfolioDashboardCard portfolio={samplePortfolio} />);

    expect(screen.getByTestId("dashboard-paper-portfolio")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-portfolio-equity")).toHaveTextContent("10,450");
    expect(screen.getByTestId("dashboard-portfolio-realized-pnl")).toHaveTextContent("450");
    expect(screen.getByTestId("dashboard-portfolio-recent-pnl")).toHaveTextContent("250");
    expect(screen.getByTestId("dashboard-portfolio-link")).toHaveAttribute("href", "/portfolio");
  });
});
