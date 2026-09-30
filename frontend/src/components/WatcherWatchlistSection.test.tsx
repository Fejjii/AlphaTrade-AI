import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_WATCHLIST_SLOTS,
  WatcherWatchlistEditor,
} from "@/components/WatcherWatchlistSection";
import type { WatcherSymbolRuntimeStatus } from "@/lib/api/types";

const statuses: WatcherSymbolRuntimeStatus[] = DEFAULT_WATCHLIST_SLOTS.map((slot) => ({
  position: slot.position,
  symbol: slot.symbol,
  enabled: slot.enabled,
  market_source: slot.symbol === "BTCUSDT" ? "replay" : "unavailable",
  freshness: slot.symbol === "BTCUSDT" ? "unknown" : "unavailable",
  last_successful_scan: null,
  last_failed_scan: null,
  setup_state: slot.symbol === "BTCUSDT" ? "not_scanned" : "unavailable",
  strategy_matches: [],
  alert_state: "none",
  error_state: slot.symbol === "BTCUSDT" ? null : "contract_unverified",
}));

afterEach(cleanup);

describe("WatcherWatchlistEditor", () => {
  it("shows five slots with live status beside each symbol", () => {
    render(
      <WatcherWatchlistEditor
        slots={DEFAULT_WATCHLIST_SLOTS}
        statuses={statuses}
        onChange={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId(/watchlist-slot-/)).toHaveLength(5);
    expect(screen.getByLabelText("Symbol for slot 1")).toHaveValue("BTCUSDT");
    expect(screen.getByTestId("watchlist-status-1")).toHaveTextContent("replay");
    expect(screen.getByTestId("watchlist-status-2")).toHaveTextContent("contract_unverified");
  });

  it("toggles enable, edits a symbol, and reorders", () => {
    const onChange = vi.fn();
    render(
      <WatcherWatchlistEditor
        slots={DEFAULT_WATCHLIST_SLOTS}
        statuses={statuses}
        onChange={onChange}
        onSave={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Enable slot 2"));
    expect(onChange).toHaveBeenCalled();
    const disabled = onChange.mock.calls[0]?.[0] as typeof DEFAULT_WATCHLIST_SLOTS;
    expect(disabled[1]?.enabled).toBe(false);

    fireEvent.change(screen.getByLabelText("Symbol for slot 3"), {
      target: { value: "solusdt" },
    });
    const replaced = onChange.mock.calls.at(-1)?.[0] as typeof DEFAULT_WATCHLIST_SLOTS;
    expect(replaced[2]?.symbol).toBe("SOLUSDT");

    fireEvent.click(screen.getByLabelText("Move slot 1 down"));
    const reordered = onChange.mock.calls.at(-1)?.[0] as typeof DEFAULT_WATCHLIST_SLOTS;
    expect(reordered[0]?.symbol).toBe("ZECUSDT");
    expect(reordered[1]?.symbol).toBe("BTCUSDT");
  });
});
