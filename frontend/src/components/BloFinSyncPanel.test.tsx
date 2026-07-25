import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BloFinSyncPanel } from "./BloFinSyncPanel";
import type { BloFinSyncSnapshotItem } from "@/lib/api/types";

const snapshot: BloFinSyncSnapshotItem = {
  id: "11111111-1111-1111-1111-111111111111",
  organization_id: "22222222-2222-2222-2222-222222222222",
  user_id: "33333333-3333-3333-3333-333333333333",
  synced_at: "2026-07-25T04:10:00Z",
  health_status: "ok",
  provider: "blofin_demo",
  exchange_mode: "paper_exchange_demo",
  account_snapshot: { balances: [{ asset: "USDT", total: "1000", available: "900" }] },
  positions_snapshot: { items: [] },
  market_context: { symbols: [] },
  provenance: { read_only: true, order_mutations: false },
  is_stale: false,
  stale_reason: null,
  error_summary: null,
  position_count: 0,
  balance_count: 1,
  note: "BloFin demo read-only snapshot.",
};

const mockReload = vi.fn();
const mockLatest = vi.fn();
const mockSync = vi.fn();

let asyncState: {
  data:
    | { empty: boolean; forbidden: boolean; snapshot: BloFinSyncSnapshotItem | null }
    | null;
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

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      exchange: {
        ...actual.api.exchange,
        blofinSyncLatest: (...args: unknown[]) => mockLatest(...args),
        blofinSync: (...args: unknown[]) => mockSync(...args),
      },
    },
  };
});

describe("BloFinSyncPanel AT-037", () => {
  beforeEach(() => {
    asyncState = {
      data: { empty: false, forbidden: false, snapshot },
      loading: false,
      error: null,
    };
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders loading and empty states", () => {
    asyncState = { data: null, loading: true, error: null };
    const { unmount } = render(<BloFinSyncPanel />);
    expect(screen.getByText(/loading blofin demo sync status/i)).toBeInTheDocument();
    unmount();

    asyncState = {
      data: { empty: true, forbidden: false, snapshot: null },
      loading: false,
      error: null,
    };
    render(<BloFinSyncPanel />);
    expect(screen.getByText(/no blofin demo snapshot yet/i)).toBeInTheDocument();
  });

  it("renders snapshot health and sync action", () => {
    mockSync.mockResolvedValue({ snapshot, note: "ok" });
    render(<BloFinSyncPanel />);
    expect(screen.getByTestId("blofin-sync-panel")).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("never")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    expect(mockSync).toHaveBeenCalled();
  });

  it("renders stale and error summaries", () => {
    asyncState = {
      data: {
        empty: false,
        forbidden: false,
        snapshot: {
          ...snapshot,
          health_status: "stale",
          is_stale: true,
          stale_reason: "Snapshot older than configured freshness window.",
          error_summary: "Demo key cannot read account data.",
        },
      },
      loading: false,
      error: null,
    };
    render(<BloFinSyncPanel />);
    expect(screen.getByText(/snapshot older than configured freshness window/i)).toBeInTheDocument();
    expect(screen.getByText(/demo key cannot read account data/i)).toBeInTheDocument();
  });
});
