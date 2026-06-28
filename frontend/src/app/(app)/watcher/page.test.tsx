import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import WatcherPage from "./page";
import { api } from "@/lib/api";

const summary = {
  scanner_enabled: false,
  manual_scan_available: true,
  worker_enabled: false,
  worker_running: false,
  symbols_supported: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  timeframes_supported: ["15m", "1h"],
  detectors_enabled: ["liquidity_sweep", "sfp", "trend_pullback"],
  detector_versions: {
    liquidity_sweep: "1.0.0",
    sfp: "1.0.0",
    trend_pullback: "1.0.0",
  },
  last_scan_at: null,
  last_scan_status: null,
  last_scan_alerts_created: 0,
  last_scan_conditions_found: [],
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

describe("WatcherPage Slice 72/73/74", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders watcher scanner panel with dry-run default on", () => {
    render(<WatcherPage />);
    expect(screen.getByTestId("market-watcher-scanner-card")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-scan-panel")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-dry-run-toggle").querySelector("input")).toBeChecked();
    expect(screen.getByTestId("watcher-run-scan-button")).toBeDisabled();
    expect(screen.getByTestId("market-watcher-detectors")).toBeInTheDocument();
  });

  it("requires confirmation before enabling scan", () => {
    render(<WatcherPage />);
    fireEvent.change(screen.getByTestId("watcher-confirm-input"), {
      target: { value: "RUN_READ_ONLY_SCAN" },
    });
    expect(screen.getByTestId("watcher-run-scan-button")).toBeEnabled();
  });

  it("requires second confirmation when dry-run is off", () => {
    render(<WatcherPage />);
    fireEvent.click(screen.getByTestId("watcher-dry-run-toggle").querySelector("input")!);
    fireEvent.change(screen.getByTestId("watcher-confirm-input"), {
      target: { value: "RUN_READ_ONLY_SCAN" },
    });
    expect(screen.getByTestId("watcher-run-scan-button")).toBeDisabled();
    expect(screen.getByTestId("watcher-in-app-only-warning")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-create-alerts-confirm-input")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("watcher-create-alerts-confirm-input"), {
      target: { value: "CREATE_IN_APP_ALERTS_ONLY" },
    });
    expect(screen.getByTestId("watcher-run-scan-button")).toBeEnabled();
  });

  it("renders setup detector candidates with reason and levels", async () => {
    vi.mocked(api.marketWatcher.scan).mockResolvedValue({
      scanned_at: new Date().toISOString(),
      env_enabled: false,
      effective_enabled: true,
      symbols_scanned: 1,
      observations_created: 1,
      setup_signals: [],
      decisions: [],
      paper_only: true,
      dry_run: true,
      status: "ok",
      alerts_created: 0,
      alerts_deduped: 0,
      candidates: [
        {
          symbol: "BTCUSDT",
          timeframe: "15m",
          condition: "liquidity_sweep",
          message: "watch",
          severity: "info",
          metrics: {},
          direction: "long",
          confidence: 68.5,
          reason: "Swept liquidity below prior swing low and closed back above it.",
          trigger_level: 98000,
          invalidation_level: 97500,
          source: "market_watcher",
          detector_version: "1.0.0",
        },
      ],
    });

    render(<WatcherPage />);
    fireEvent.change(screen.getByTestId("watcher-confirm-input"), {
      target: { value: "RUN_READ_ONLY_SCAN" },
    });
    fireEvent.click(screen.getByTestId("watcher-run-scan-button"));

    await waitFor(() => {
      expect(screen.getByTestId("watcher-setup-liquidity_sweep")).toBeInTheDocument();
    });
    expect(screen.getByTestId("watcher-candidate-reason")).toHaveTextContent("Swept liquidity");
    expect(screen.getByTestId("watcher-candidate-confidence")).toHaveTextContent("68.5");
    expect(screen.getByTestId("watcher-candidate-levels")).toHaveTextContent("Trigger:");
    expect(screen.getByTestId("watcher-candidate-levels")).toHaveTextContent("Invalidation:");
  });

  it("does not render Telegram send or order UI controls", () => {
    render(<WatcherPage />);
    expect(screen.queryByTestId("watcher-telegram-send-button")).toBeNull();
    expect(screen.queryByTestId("watcher-place-order-button")).toBeNull();
    expect(screen.queryByTestId("watcher-deliver-telegram-button")).toBeNull();
  });
});
