import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WatchlistPage from "./page";
import type { WatchlistItem } from "@/lib/api/types";

const mockReload = vi.fn<() => Promise<void>>();
const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockDelete = vi.fn();

let asyncState: {
  data: WatchlistItem[] | null;
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
    watchlist: {
      list: vi.fn(),
      create: (...args: unknown[]) => mockCreate(...args),
      update: (...args: unknown[]) => mockUpdate(...args),
      delete: (...args: unknown[]) => mockDelete(...args),
    },
  },
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/components/WatchlistCard", () => ({
  WatchlistCard: ({
    item,
    onToggle,
    onDelete,
  }: {
    item: WatchlistItem;
    onToggle: (id: string, enabled: boolean) => Promise<void>;
    onDelete: (id: string) => Promise<void>;
  }) => (
    <div data-testid={`watchlist-card-${item.id}`}>
      <span>{item.symbol}</span>
      <button type="button" onClick={() => void onToggle(item.id, !item.enabled)}>
        Toggle
      </button>
      <button type="button" onClick={() => void onDelete(item.id)}>
        Delete
      </button>
    </div>
  ),
}));

function makeItem(overrides: Partial<WatchlistItem> = {}): WatchlistItem {
  return {
    id: "wl-1",
    organization_id: "org-1",
    user_id: "user-1",
    symbol: "BTCUSDT",
    exchange: "mock",
    timeframes: ["1h", "4h"],
    strategy_ids: ["htf_trend_pullback"],
    enabled: true,
    created_at: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

describe("Watchlist route (/watchlist) — FP2-129", () => {
  beforeEach(() => {
    asyncState = { data: null, loading: true, error: null };
    mockReload.mockResolvedValue(undefined);
    mockCreate.mockResolvedValue(makeItem());
    mockUpdate.mockResolvedValue(makeItem({ enabled: false }));
    mockDelete.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders loading without fabricated watchlist rows", () => {
    render(<WatchlistPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByTestId("watchlist-card-wl-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
  });

  it("renders failed request with retry and no empty success", () => {
    asyncState = { data: null, loading: false, error: "Watchlist failed" };
    render(<WatchlistPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent("Watchlist failed");
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(mockReload).toHaveBeenCalledTimes(1);
  });

  it("renders honest empty state only after a successful empty load", () => {
    asyncState = { data: [], loading: false, error: null };
    render(<WatchlistPage />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(/Watchlist is empty/i);
    expect(screen.queryByTestId("watchlist-card-wl-1")).not.toBeInTheDocument();
  });

  it("renders successful items and supports add as the primary action", async () => {
    asyncState = { data: [makeItem()], loading: false, error: null };
    render(<WatchlistPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent("Watchlist");
    expect(screen.getByTestId("watchlist-card-wl-1")).toHaveTextContent("BTCUSDT");
    expect(screen.getByRole("button", { name: /Kill switch/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Add to watchlist/i }));
    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: "BTCUSDT",
        exchange: "mock",
        enabled: true,
      }),
    );
    expect(mockReload).toHaveBeenCalled();
  });
});
