import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import WatcherPage from "./page";

const summary = {
  scanner_enabled: false,
  manual_scan_available: true,
  worker_enabled: false,
  worker_running: false,
  symbols_supported: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  timeframes_supported: ["15m", "1h"],
  last_scan_at: null,
  last_scan_status: null,
  last_scan_alerts_created: 0,
  last_scan_error: null,
  paper_only: true,
  readiness: "ready" as const,
  warnings: [],
  generated_at: new Date().toISOString(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: summary,
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    marketWatcher: {
      summary: vi.fn(),
      scan: vi.fn(),
    },
  },
}));

describe("WatcherPage Slice 72", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders watcher scanner panel with dry-run default on", () => {
    render(<WatcherPage />);
    expect(screen.getByTestId("market-watcher-scanner-card")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-scan-panel")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-dry-run-toggle").querySelector("input")).toBeChecked();
    expect(screen.getByTestId("watcher-run-scan-button")).toBeDisabled();
  });

  it("requires confirmation before enabling scan", () => {
    render(<WatcherPage />);
    fireEvent.change(screen.getByTestId("watcher-confirm-input"), {
      target: { value: "RUN_READ_ONLY_SCAN" },
    });
    expect(screen.getByTestId("watcher-run-scan-button")).toBeEnabled();
  });
});
