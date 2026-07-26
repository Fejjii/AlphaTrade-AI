import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

type Loaded = {
  forbidden: false;
  tradingView: TradingViewSignalListResponse;
  alerts: { items: []; total: 0 };
  setupReviews: { items: []; total: 0; limit: 50; offset: 0 };
  watcherSummary: null;
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
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => new URLSearchParams(),
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

function loaded(tradingView: TradingViewSignalListResponse = sampleList): Loaded {
  return {
    forbidden: false,
    tradingView,
    alerts: { items: [], total: 0 },
    setupReviews: { items: [], total: 0, limit: 50, offset: 0 },
    watcherSummary: null,
  };
}

describe("Signals inbox Phase C1", () => {
  beforeEach(() => {
    safetyPosture.executionMode = "paper";
    safetyPosture.realTradingEnabled = false;
    safetyPosture.postureKnown = true;
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

  it("fails closed when runtime safety is missing", () => {
    safetyPosture.executionMode = null;
    safetyPosture.realTradingEnabled = null;
    safetyPosture.postureKnown = false;
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("paper-mode-indicator")).toHaveAttribute(
      "aria-label",
      "Paper mode not confirmed",
    );
  });

  it("renders loading state", () => {
    asyncState = { data: null, loading: true, error: null };
    render(<TradingViewSignalsPage />);
    expect(screen.getByText(/loading tradingview signals/i)).toBeInTheDocument();
  });

  it("renders empty state", () => {
    asyncState = {
      data: loaded({ ...sampleList, items: [], total: 0 }),
      loading: false,
      error: null,
    };
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("tradingview-signals-page")).toBeInTheDocument();
    expect(screen.getByText(/no signals need review/i)).toBeInTheDocument();
  });

  it("renders error state", () => {
    asyncState = { data: null, loading: false, error: "Network error" };
    render(<TradingViewSignalsPage />);
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders forbidden state", () => {
    asyncState = { data: { forbidden: true }, loading: false, error: null };
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("tradingview-signals-forbidden")).toBeInTheDocument();
  });

  it("renders signal source/freshness and actions", () => {
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("signals-inbox")).toBeInTheDocument();
    expect(screen.getByText("TradingView")).toBeInTheDocument();
    expect(screen.getByTestId("freshness-pill")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /review evidence/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /plan trade/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dismiss with reason/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /advanced orchestration/i })).toHaveAttribute(
      "href",
      "/paper-signal-orchestration",
    );
  });

  it("renders signal detail and rejection explanations", () => {
    asyncState = {
      data: loaded({
        ...sampleList,
        items: [
          {
            ...sampleList.items[0],
            status: "rejected",
            rejection_reason: "strategy_id does not belong to this organization.",
            validation_errors: ["strategy_id does not belong to this organization."],
          },
        ],
      }),
      loading: false,
      error: null,
    };
    render(<TradingViewSignalsPage />);
    expect(screen.getByTestId("tradingview-signal-detail")).toBeInTheDocument();
    expect(screen.getByTestId("tradingview-rejection")).toHaveTextContent(
      /strategy_id does not belong/i,
    );
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
    const button = screen.getByRole("button", { name: /create paper candidate/i });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/candidate confirmation phrase/i), {
      target: { value: CREATE_TRADINGVIEW_PAPER_CANDIDATE },
    });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    expect(mockCreate).toHaveBeenCalledWith(SIGNAL_ID, {
      confirm: CREATE_TRADINGVIEW_PAPER_CANDIDATE,
    });
  });

  it("keeps existing deep links reachable", () => {
    render(<TradingViewSignalsPage />);
    expect(screen.getByRole("link", { name: "Alerts" })).toHaveAttribute("href", "/alerts");
    expect(screen.getByRole("link", { name: "Setup review" })).toHaveAttribute(
      "href",
      "/alerts/review",
    );
    expect(screen.getByRole("link", { name: "Watcher scanner" })).toHaveAttribute(
      "href",
      "/watcher",
    );
  });
});
