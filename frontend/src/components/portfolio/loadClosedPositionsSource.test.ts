import { describe, expect, it, vi } from "vitest";

import {
  loadClosedPositionsSource,
  mergeClosedAndLiquidatedSources,
} from "@/components/portfolio/loadClosedPositionsSource";
import type { SourceResult } from "@/components/workflows";
import type { PaginatedPositions, Position } from "@/lib/api/types";

function ok(items: Position[], total = items.length): SourceResult<PaginatedPositions> {
  return {
    data: { items, total, limit: 50, offset: 0 },
    available: true,
    error: null,
    fallbackUsed: false,
  };
}

function failed(error = "down"): SourceResult<PaginatedPositions> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function makePosition(overrides: Partial<Position> & { id: string; status: Position["status"] }): Position {
  return {
    organization_id: "org",
    user_id: "user",
    symbol: "BTCUSDT",
    direction: "long",
    size: "1",
    entry_price: "100",
    leverage: "1",
    take_profits: [],
    unrealized_pnl: "0",
    realized_pnl: "10",
    risk_state: {},
    opened_at: "2026-07-20T10:00:00.000Z",
    closed_at: "2026-07-21T10:00:00.000Z",
    ...overrides,
  };
}

describe("mergeClosedAndLiquidatedSources (FP2-221)", () => {
  it("merges closed and liquidated rows and preserves totals", () => {
    const closed = makePosition({ id: "c1", status: "closed", closed_at: "2026-07-21T10:00:00.000Z" });
    const liquidated = makePosition({
      id: "l1",
      status: "liquidated",
      symbol: "ETHUSDT",
      closed_at: "2026-07-22T10:00:00.000Z",
    });
    const merged = mergeClosedAndLiquidatedSources(ok([closed], 1), ok([liquidated], 1));
    expect(merged.available).toBe(true);
    expect(merged.data?.items.map((item) => item.id)).toEqual(["l1", "c1"]);
    expect(merged.data?.total).toBe(2);
  });

  it("fails only when both sources fail", () => {
    const merged = mergeClosedAndLiquidatedSources(failed("closed down"), failed("liq down"));
    expect(merged.available).toBe(false);
    expect(merged.error).toMatch(/closed down|liq down/);
  });

  it("keeps liquidated rows when the closed source fails", () => {
    const liquidated = makePosition({ id: "l1", status: "liquidated" });
    const merged = mergeClosedAndLiquidatedSources(failed("closed down"), ok([liquidated], 1));
    expect(merged.available).toBe(true);
    expect(merged.data?.items).toHaveLength(1);
    expect(merged.data?.items[0]?.status).toBe("liquidated");
    expect(merged.error).toBe("closed down");
  });
});

describe("loadClosedPositionsSource (FP2-221)", () => {
  it("requests both closed and liquidated status filters", async () => {
    const list = vi.fn(async ({ status }: { status: string }) => ({
      items: [
        makePosition({
          id: status === "closed" ? "c1" : "l1",
          status: status as Position["status"],
        }),
      ],
      total: 1,
      limit: 50,
      offset: 0,
    }));

    const result = await loadClosedPositionsSource(list);
    expect(list).toHaveBeenCalledWith({ status: "closed", limit: 50 });
    expect(list).toHaveBeenCalledWith({ status: "liquidated", limit: 50 });
    expect(result.data?.items.map((item) => item.id).sort()).toEqual(["c1", "l1"]);
  });
});
