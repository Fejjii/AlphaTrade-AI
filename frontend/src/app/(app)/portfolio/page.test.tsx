import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PaperPortfolioPage from "./page";
import { samplePortfolio } from "./sample-portfolio";

const portfolioMock = vi.fn();
const useAsyncDataMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    performance: {
      portfolio: (...args: unknown[]) => portfolioMock(...args),
    },
  },
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: (...args: unknown[]) => useAsyncDataMock(...args),
}));

describe("PaperPortfolioPage Slice 91B", () => {
  afterEach(() => {
    cleanup();
    portfolioMock.mockClear();
    useAsyncDataMock.mockClear();
  });

  beforeEach(() => {
    useAsyncDataMock.mockReturnValue({
      data: samplePortfolio,
      loading: false,
      error: null,
      reload: vi.fn(),
    });
  });

  it("renders success state with safety banner and summary cards", () => {
    render(<PaperPortfolioPage />);

    expect(screen.getByTestId("paper-portfolio-page")).toBeInTheDocument();
    expect(screen.getByTestId("paper-portfolio-safety-banner")).toBeInTheDocument();
    expect(screen.getByTestId("paper-portfolio-paper-only")).toHaveTextContent(
      /paper-only simulated portfolio/i,
    );
    expect(screen.getByText(/not live trading/i)).toBeInTheDocument();
    expect(screen.getByTestId("paper-portfolio-safety-banner")).toHaveTextContent(
      /not investment advice/i,
    );
    expect(screen.getByTestId("portfolio-current-equity")).toHaveTextContent("10,450");
    expect(screen.getByTestId("portfolio-realized-pnl")).toHaveTextContent("450");
    expect(screen.getByTestId("portfolio-win-rate")).toHaveTextContent("66.7%");
  });

  it("renders charts and breakdown tables", () => {
    render(<PaperPortfolioPage />);

    expect(screen.getByTestId("paper-portfolio-charts")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-equity-chart-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-daily-pnl-chart-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-daily-drawdown-chart-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-breakdown-symbol")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-breakdown-detector")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-breakdown-symbol-row-BTCUSDT")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    useAsyncDataMock.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      reload: vi.fn(),
    });

    render(<PaperPortfolioPage />);
    expect(screen.getByText(/loading paper portfolio/i)).toBeInTheDocument();
  });

  it("renders error state", () => {
    useAsyncDataMock.mockReturnValue({
      data: null,
      loading: false,
      error: "Portfolio unavailable",
      reload: vi.fn(),
    });

    render(<PaperPortfolioPage />);
    expect(screen.getByText("Portfolio unavailable")).toBeInTheDocument();
  });

  it("renders empty state when no data after load", () => {
    useAsyncDataMock.mockReturnValue({
      data: null,
      loading: false,
      error: null,
      reload: vi.fn(),
    });

    render(<PaperPortfolioPage />);
    expect(screen.getByText(/no portfolio data/i)).toBeInTheDocument();
  });

  it("calls portfolio API when filters change", () => {
    useAsyncDataMock.mockImplementation((loader: () => Promise<unknown>, deps: unknown[]) => {
      void loader();
      return {
        data: samplePortfolio,
        loading: false,
        error: null,
        reload: vi.fn(),
        deps,
      };
    });
    portfolioMock.mockResolvedValue(samplePortfolio);

    render(<PaperPortfolioPage />);

    fireEvent.change(screen.getByTestId("portfolio-filter-start-date"), {
      target: { value: "2026-01-01" },
    });
    fireEvent.change(screen.getByTestId("portfolio-filter-source"), {
      target: { value: "proposal_flow" },
    });

    expect(portfolioMock).toHaveBeenCalled();
    const lastCall = portfolioMock.mock.calls.at(-1)?.[0];
    expect(lastCall).toMatchObject({
      start_date: "2026-01-01",
      source: "proposal_flow",
    });
  });

  it("has no unsafe CTAs", () => {
    render(<PaperPortfolioPage />);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy now/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sell now/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enable live trading/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start automation/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send telegram/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve trade/i })).not.toBeInTheDocument();
  });
});
