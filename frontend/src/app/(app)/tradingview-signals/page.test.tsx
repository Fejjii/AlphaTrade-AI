import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TradingViewSignalsPage from "./page";
import { CREATE_TRADINGVIEW_PAPER_CANDIDATE } from "@/lib/api";
import type { TradingViewSignalListResponse } from "@/lib/api/types";

const SIGNAL_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const sampleList: TradingViewSignalListResponse = {
  items: [
    {
      id: SIGNAL_ID,
      organization_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      external_alert_id: "tv-alert-1",
      idempotency_key: "tv-alert-1",
      status: "validated",
      symbol: "BTCUSDT",
      timeframe: "15m",
      direction: "long",
      setup_name: "HTF Pullback",
      setup_version: 1,
      setup_definition_id: null,
      strategy_id: null,
      strategy_version_id: null,
      trigger_level: 65000,
      invalidation_level: 64000,
      take_profit_level: 67000,
      stop_loss_level: 64000,
      confidence: 0.72,
      source_metadata: { chart: "BTCUSDT.P" },
      validation_errors: null,
      rejection_reason: null,
      received_at: "2026-07-25T04:00:00Z",
      validated_at: "2026-07-25T04:00:01Z",
      occurred_at: null,
      duplicate_of_signal_id: null,
      links: {
        setup_definition_id: null,
        strategy_id: null,
        strategy_version_id: null,
        source_alert_id: null,
        draft_id: null,
        candidate_id: null,
        journal_trade_id: null,
        backtest_run_id: null,
        paper_candidate_path: null,
        strategy_path: null,
        journal_path: null,
      },
      note: "Advisory TradingView intake only. Never creates live orders.",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
};

const mockReload = vi.fn();
const mockCreate = vi.fn();
const mockPush = vi.fn();
const mockReplace = vi.fn();
const search = new URLSearchParams();

type Loaded = {
  forbidden: false;
  tradingView: {
    data: TradingViewSignalListResponse;
    available: boolean;
    error: string | null;
    fallbackUsed: boolean;
  };
  alerts: { data: { items: []; total: 0 }; available: boolean; error: null; fallbackUsed: false };
  setupReviews: {
    data: { items: []; total: 0; limit: 50; offset: 0 };
    available: boolean;
    error: null;
    fallbackUsed: false;
  };
  watcherSummary: { data: null; available: boolean; error: string | null; fallbackUsed: false };
};

let asyncState: {
  data: Loaded | { forbidden: true } | null;
  loading: boolean;
  error: string | null;
};

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "mock",
  postureKnown: true,
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => search,
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ health: null, providers: { providers: [] } }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: asyncState.data,
    loading: asyncState.loading,
    error: asyncState.error,
    reload: mockReload,
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      tradingview: {
        listSignals: vi.fn(),
        getSignal: vi.fn(),
        createCandidate: (...args: unknown[]) => mockCreate(...args),
      },
      alerts: {
        ...actual.api.alerts,
        list: vi.fn(),
        setupReview: vi.fn(),
        updateSetupReview: vi.fn(),
        markRead: vi.fn(),
      },
      marketWatcher: {
        ...actual.api.marketWatcher,
        summary: vi.fn(),
      },
    },
  };
});

function loaded(
  tradingView: TradingViewSignalListResponse = sampleList,
  options?: { alertsAvailable?: boolean; setupAvailable?: boolean; watcherAvailable?: boolean },
): Loaded {
  return {
    forbidden: false,
    tradingView: { data: tradingView, available: true, error: null, fallbackUsed: false },
    alerts: {
      data: { items: [], total: 0 },
      available: options?.alertsAvailable ?? true,
      error: null,
      fallbackUsed: false,
    },
    setupReviews: {
      data: { items: [], total: 0, limit: 50, offset: 0 },
      available: options?.setupAvailable ?? true,
      error: null,
      fallbackUsed: false,
    },
    watcherSummary: {
      data: null,
      available: options?.watcherAvailable ?? true,
      error: options?.watcherAvailable === false ? "down" : null,
      fallbackUsed: false,
    },
  };
}

describe("Signals inbox Phase C1 corrections", () => {
  beforeEach(() => {
    safetyPosture.executionMode = "paper";
    safetyPosture.realTradingEnabled = false;
    safetyPosture.postureKnown = true;
    search.delete("signal");
    asyncState = {
      data: loaded(),
      loading: false,
      error: null,
    };
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows paper mode only when runtime safety is verified", () => {
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode active",
    );
  });

  it("renders source availability and create paper candidate action", () => {
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("signals-source-availability")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /create paper candidate/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /hide for this session/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /dismiss with reason/i })).not.toBeInTheDocument();
  });

  it("carries plan trade context in the typed query", () => {
    render(<TradingViewSignalsPage />);
    fireEvent.click(screen.getAllByRole("button", { name: /plan trade/i })[0]);
    expect(mockPush).toHaveBeenCalledWith(
      `/workspace?source=tradingview&signal=${SIGNAL_ID}`,
    );
  });

  it("does not select an unrelated signal for a missing deep link", () => {
    search.set("signal", "missing-signal-id");
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("signal-deep-link-missing")).toHaveTextContent(
      /requested signal not found/i,
    );
    expect(screen.queryByTestId("tradingview-signal-detail")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /clear stale link/i }));
    expect(mockReplace).toHaveBeenCalledWith("/tradingview-signals");
  });

  it("shows partial inbox data when optional sources fail", () => {
    asyncState = {
      data: loaded(sampleList, { alertsAvailable: false, watcherAvailable: false }),
      loading: false,
      error: null,
    };
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("signals-partial-data")).toHaveTextContent(/partial inbox data/i);
    expect(screen.getByTestId("signals-unavailable-sources")).toHaveTextContent("Alerts");
  });

  it("does not claim a complete empty inbox when sources failed", () => {
    asyncState = {
      data: loaded(
        { ...sampleList, items: [], total: 0 },
        { alertsAvailable: false, setupAvailable: false },
      ),
      loading: false,
      error: null,
    };
    render(<TradingViewSignalsPage />);
    expect(screen.getByText(/no signals found in the available sources/i)).toBeInTheDocument();
    expect(screen.queryByText(/^No signals need review$/)).not.toBeInTheDocument();
  });

  it("requires confirmation before creating a paper candidate", async () => {
    mockCreate.mockResolvedValue({
      signal: sampleList.items[0],
      candidate_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
      draft_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
      source_alert_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      already_exists: false,
      note: "Paper-validation candidate only.",
    });
    render(<TradingViewSignalsPage />);
    const detail = screen.getByTestId("tradingview-signal-detail");
    const button = within(detail).getByRole("button", { name: /create paper candidate/i });
    expect(button).toBeDisabled();
    fireEvent.change(within(detail).getByLabelText(/candidate confirmation phrase/i), {
      target: { value: CREATE_TRADINGVIEW_PAPER_CANDIDATE },
    });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    expect(mockCreate).toHaveBeenCalledWith(SIGNAL_ID, {
      confirm: CREATE_TRADINGVIEW_PAPER_CANDIDATE,
    });
  });

  it("renders forbidden state", () => {
    asyncState = { data: { forbidden: true }, loading: false, error: null };
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("tradingview-signals-forbidden")).toBeInTheDocument();
  });
});
