import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import MarketWatcherPage from "./page";

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      env_enabled: false,
      effective_enabled: false,
      watched_symbols: ["BTCUSDT"],
      paper_only: true,
      real_trading_enabled: false,
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("MarketWatcherPage Slice 41", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders market watcher status", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-status")).toBeInTheDocument();
    expect(screen.getByTestId("market-watcher-env-enabled")).toHaveTextContent("false");
  });

  it("renders scan button", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-scan-button")).toBeInTheDocument();
  });

  it("renders disabled state copy", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-disabled-state")).toHaveTextContent("disabled");
  });

  it("renders paper only disclaimer", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-paper-only")).toHaveTextContent("Paper only");
  });
});
