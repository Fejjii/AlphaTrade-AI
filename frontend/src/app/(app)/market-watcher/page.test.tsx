import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import MarketWatcherPage from "./page";

let hookIndex = 0;

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => {
    const index = hookIndex++;
    if (index === 0) {
      return {
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
      };
    }
    if (index === 1) {
      return {
        data: {
          env_enabled: false,
          auto_tick_enabled: false,
          effective_enabled: false,
          decisions_last_tick: 0,
          scans_triggered_last_tick: 0,
          paper_only: true,
          real_trading_enabled: false,
        },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    if (index === 2) {
      return {
        data: { items: [], total: 0, limit: 10, offset: 0 },
        loading: false,
        error: null,
        reload: vi.fn(),
      };
    }
    return {
      data: {
        items: [
          {
            id: "dec-1",
            decision: "skipped_disabled",
            symbol: "BTCUSDT",
            reason: "Bridge disabled",
            blockers: [],
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      },
      loading: false,
      error: null,
      reload: vi.fn(),
    };
  },
}));

describe("MarketWatcherPage Slice 42", () => {
  afterEach(() => {
    hookIndex = 0;
    cleanup();
  });

  it("renders market watcher status", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-status")).toBeInTheDocument();
    expect(screen.getByTestId("market-watcher-env-enabled")).toHaveTextContent("false");
  });

  it("renders bridge status", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-bridge-status")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-env-enabled")).toHaveTextContent("false");
  });

  it("renders bridge decision history with human-readable labels", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("bridge-decision-history")).toBeInTheDocument();
    expect(screen.getByTestId("bridge-skipped-reason")).toHaveTextContent("Bridge disabled");
    expect(screen.getByTestId("bridge-decision-label")).toHaveTextContent("Skipped — bridge disabled");
  });

  it("explains what the action buttons do", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-action-help")).toHaveTextContent("never places");
  });

  it("does not render bridge tick when disabled", () => {
    render(<MarketWatcherPage />);
    expect(screen.queryByTestId("market-watcher-bridge-tick-button")).toBeNull();
  });

  it("renders scan button", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-scan-button")).toBeInTheDocument();
  });

  it("renders paper only disclaimer", () => {
    render(<MarketWatcherPage />);
    expect(screen.getByTestId("market-watcher-paper-only")).toHaveTextContent("Paper only");
  });
});
