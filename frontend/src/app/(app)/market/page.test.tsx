import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MarketPage from "./page";
import type { MarketAnalyzeResponse, MarketSnapshotResponse } from "@/lib/api/types";

const mockReload = vi.fn<() => Promise<void>>();
const mockSnapshot = vi.fn();
const mockAnalyze = vi.fn();

let asyncState: {
  data: MarketSnapshotResponse | null;
  loading: boolean;
  error: string | null;
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: asyncState.data,
    loading: asyncState.loading,
    error: asyncState.error,
    reload: mockReload,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    market: {
      snapshot: (...args: unknown[]) => mockSnapshot(...args),
      analyze: (...args: unknown[]) => mockAnalyze(...args),
    },
  },
}));

function makeSnapshot(overrides: Partial<MarketSnapshotResponse> = {}): MarketSnapshotResponse {
  const meta = {
    symbol: "BTCUSDT",
    exchange: "binance",
    timeframe: "1h" as const,
    timestamp: "2026-07-27T10:00:00.000Z",
    source: "mock",
    is_live: false,
    is_stale: false,
    fallback_used: true,
    cache_hit: false,
    retrieved_at: "2026-07-27T10:00:00.000Z",
    stale_reason: null,
    provider_name: "mock",
  };
  return {
    meta,
    ticker: {
      meta,
      last_price: "50123.45",
      bid: null,
      ask: null,
      volume_24h: null,
    },
    latest_bar: {
      open: "50000",
      high: "50500",
      low: "49800",
      close: "50123.45",
      volume: "12.5",
      timestamp: "2026-07-27T09:00:00.000Z",
    },
    indicators: {
      symbol: "BTCUSDT",
      timeframe: "1h",
      rsi: 55,
      ema_fast: "50010",
      macd: 1.2,
      atr: "250",
      timestamp: "2026-07-27T10:00:00.000Z",
    },
    ...overrides,
  };
}

describe("MarketPage route honesty (FP2-129)", () => {
  beforeEach(() => {
    asyncState = { data: null, loading: true, error: null };
    mockReload.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders a single h1 and read-only / no-execution posture copy", () => {
    asyncState = { data: makeSnapshot(), loading: false, error: null };
    render(<MarketPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent("Market Monitor");
    expect(screen.getByText(/no exchange execution/i)).toBeInTheDocument();
  });

  it("renders loading without an empty or fabricated snapshot", () => {
    asyncState = { data: null, loading: true, error: null };
    render(<MarketPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No snapshot/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/50123/)).not.toBeInTheDocument();
  });

  it("renders failed request with retry and no empty success", () => {
    asyncState = { data: null, loading: false, error: "Market snapshot failed" };
    render(<MarketPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent("Market snapshot failed");
    expect(screen.queryByText(/No snapshot/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(mockReload).toHaveBeenCalledTimes(1);
  });

  it("renders honest empty state only when load succeeds with no data", () => {
    asyncState = { data: null, loading: false, error: null };
    render(<MarketPage />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(/No snapshot/i);
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("renders successful mock fallback content without claiming live prices", () => {
    asyncState = { data: makeSnapshot(), loading: false, error: null };
    render(<MarketPage />);
    expect(screen.getAllByText(/50123/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Using mock fallback — prices are not live exchange data/i),
    ).toBeInTheDocument();
  });

  it("runs analyze as a user action without inventing prior analysis", async () => {
    const snapshot = makeSnapshot();
    const analysis: MarketAnalyzeResponse = {
      snapshot,
      indicators: snapshot.indicators!,
      strategy_signals: [],
      data_quality: "mock",
      confidence_penalty_applied: false,
    };
    mockAnalyze.mockResolvedValue(analysis);
    asyncState = { data: makeSnapshot(), loading: false, error: null };
    render(<MarketPage />);
    expect(screen.queryByText(/No strategy signals/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^analyze$/i }));
    await waitFor(() => expect(mockAnalyze).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/No strategy signals/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Strategy signals/i })).toBeInTheDocument();
  });
});
