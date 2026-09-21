import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DecisionMarketPage from "./page";
import type { CanonicalEvidenceRead, CanonicalMarketMonitorStatusRead } from "@/lib/api/types";

const mockGetEvidence = vi.fn();
const mockGetMarketStatus = vi.fn();

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
  postureKnown: true,
};

vi.mock("next/navigation", () => ({
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/decision/market",
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchStatus: { active: false, execution_blocked: false },
  }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/lib/api", () => ({
  api: {
    canonical: {
      getEvidence: (...args: unknown[]) => mockGetEvidence(...args),
      getMarketStatus: (...args: unknown[]) => mockGetMarketStatus(...args),
    },
  },
}));

const replay: CanonicalEvidenceRead = {
  authority: "canonical",
  live_executable: false,
  watcher_activated: false,
  organization_id: "org",
  symbol: "BTCUSDT",
  source: {
    venue: "binance",
    market_type: "perpetual",
    instrument_id: "binance:usdm_futures:perpetual:BTCUSDT",
    provider_symbol: "BTCUSDT",
    provider_name: "binance-usdm-perpetual-replay",
    source_family: "replay_fixture",
    adapter_version: "binance-usdm-perpetual/v1",
    is_live: false,
    is_mock: true,
    fallback_used: false,
  },
  current_price: {
    usable_as_current_market_price: false,
    presentation: "replay_fixture",
    price: "91234.5",
    source_time: "2026-01-15T16:15:04.000Z",
    venue_trade_id: "agg-1",
    is_live: false,
    is_mock: true,
    fallback_used: false,
    freshness: {
      policy_version: "first-slice-btc-usdt-usdm-freshness/v1",
      state: "fresh",
      evaluated_at: "2026-01-15T16:15:05.000Z",
      source_time: "2026-01-15T16:15:04.000Z",
      age_seconds: "1",
    },
  },
  setup_evidence: {
    available: true,
    evidence_window_hash: "ab".repeat(32),
    completeness: {
      ohlcv_15m: "complete",
      ohlcv_4h: "complete",
      cvd: "complete",
      signed_flow: "complete",
    },
  },
  timestamps: { evaluated_at: "2026-01-15T16:15:05.000Z" },
  unavailable_reason: "replay_fixture",
};

const replayStatus: CanonicalMarketMonitorStatusRead = {
  authority: "canonical_market_monitor",
  live_executable: false,
  watcher_activated: false,
  compatibility_price_used: false,
  symbol: "BTCUSDT",
  mode: "replay",
  availability: "replay",
  reason: "replay_fixture",
  perpetual: true,
  source: replay.source,
  current_price: replay.current_price,
  last_update: "2026-01-15T16:15:04.000Z",
  evaluated_at: "2026-01-15T16:15:05.000Z",
  stream: {
    reconnect_state: "continuous",
    gap_state: "none",
    warm_up_status: "complete",
    last_sequence: 1,
    reconnect_count: 0,
  },
  coverage: { completeness: "complete", gap_state: "none" },
  cvd: { available: true, signed_quote_delta: "-12.5", event_count: 4 },
  ohlcv: { available: true, completeness_15m: "complete", completeness_4h: "complete" },
  provider: {
    name: "binance-usdm-perpetual-replay",
    health: "healthy",
    is_mock: true,
    using_fallback: false,
  },
  backoff: { active: false, attempt: 0 },
  content_hash: "ab".repeat(32),
  unavailable_reason: "replay_fixture",
};

describe("Decision market canonical evidence", () => {
  beforeEach(() => {
    mockGetEvidence.mockResolvedValue(replay);
    mockGetMarketStatus.mockResolvedValue(replayStatus);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("reads GET /canonical/evidence and does not present replay as Live", async () => {
    render(<DecisionMarketPage />);
    await waitFor(() => expect(mockGetEvidence).toHaveBeenCalled());
    expect(mockGetEvidence).toHaveBeenCalledWith({ symbol: "BTCUSDT" });
    expect(mockGetMarketStatus).toHaveBeenCalledWith({ symbol: "BTCUSDT" });
    expect(screen.getByTestId("perpetual-market-status")).toHaveTextContent(/replay fixture/i);
    expect(screen.getByRole("heading", { level: 1, name: "Market assessment" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /read canonical evidence/i })).toBeInTheDocument();
    const panel = await screen.findByTestId("canonical-current-price");
    expect(panel).toHaveTextContent(/replay fixture/i);
    expect(panel).toHaveTextContent(/not a current market price/i);
    expect(panel).not.toHaveTextContent("Live");
    expect(screen.getAllByText(/watcher is not activated/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId("monitor-watcher-off")).toBeInTheDocument();
  });
});
