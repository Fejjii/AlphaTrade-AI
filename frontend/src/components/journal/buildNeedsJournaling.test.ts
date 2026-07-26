import { describe, expect, it } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";
import type { PaginatedJournalEntries, PaginatedPositions, Position } from "@/lib/api/types";

import { buildNeedsJournalingQueue } from "./buildNeedsJournaling";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(): SourceResult<T> {
  return { data: null, available: false, error: "down", fallbackUsed: false };
}

function position(overrides: Partial<Position> & { id: string; symbol: string }): Position {
  return {
    organization_id: "org",
    user_id: "user",
    direction: "long",
    size: "1",
    entry_price: "100",
    leverage: "1",
    take_profits: [],
    unrealized_pnl: "0",
    realized_pnl: "10",
    risk_state: {},
    status: "closed",
    opened_at: "2026-07-20T10:00:00.000Z",
    closed_at: "2026-07-21T10:00:00.000Z",
    ...overrides,
  };
}

describe("buildNeedsJournalingQueue", () => {
  it("returns loading when sources are not ready", () => {
    const result = buildNeedsJournalingQueue(null, null);
    expect(result.queueStatus).toBe("loading");
    expect(result.countAvailable).toBe(false);
    expect(result.items).toBeNull();
  });

  it("does not claim needs-journaling when positions fail", () => {
    const result = buildNeedsJournalingQueue(
      failed(),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(result.queueStatus).toBe("unavailable");
    expect(result.countAvailable).toBe(false);
    expect(result.items).toBeNull();
    expect(result.reasonUnavailable).toMatch(/positions are unavailable/i);
  });

  it("does not claim needs-journaling when journal entries fail", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      failed(),
    );
    expect(result.queueStatus).toBe("unavailable");
    expect(result.countAvailable).toBe(false);
    expect(result.items).toBeNull();
    expect(result.reasonUnavailable).toMatch(/cannot be confirmed/i);
  });

  it("lists closed positions without a linked journal entry", () => {
    const positions: SourceResult<PaginatedPositions> = ok({
      items: [
        position({ id: "p1", symbol: "BTCUSDT", closed_at: "2026-07-22T12:00:00.000Z" }),
        position({ id: "p2", symbol: "ETHUSDT", closed_at: "2026-07-21T12:00:00.000Z" }),
      ],
      total: 2,
      limit: 50,
      offset: 0,
    });
    const entries: SourceResult<PaginatedJournalEntries> = ok({
      items: [
        {
          id: "j1",
          organization_id: "org",
          user_id: "user",
          symbol: "ETHUSDT",
          timeframe: "1h",
          direction: "long",
          entry_rationale: "done",
          emotions: [],
          mistakes: [],
          result: "win",
          tags: [],
          screenshot_refs: [],
          linked_position_id: "p2",
          created_at: "2026-07-21T13:00:00.000Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    const result = buildNeedsJournalingQueue(positions, entries);
    expect(result.countAvailable).toBe(true);
    expect(result.queueStatus).toBe("available");
    expect(result.items).toHaveLength(1);
    expect(result.items?.[0]?.positionId).toBe("p1");
    expect(result.items?.[0]?.href).toBe("/journal?position_id=p1");
  });

  it("returns honest empty when every closed position is already journaled", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      ok({
        items: [
          {
            id: "j1",
            organization_id: "org",
            user_id: "user",
            symbol: "BTCUSDT",
            timeframe: "1h",
            direction: "long",
            entry_rationale: "done",
            emotions: [],
            mistakes: [],
            result: "win",
            tags: [],
            screenshot_refs: [],
            linked_position_id: "p1",
            created_at: "2026-07-21T13:00:00.000Z",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
    expect(result.queueStatus).toBe("empty");
    expect(result.countAvailable).toBe(true);
    expect(result.items).toEqual([]);
  });

  it("marks truncated lists as limited without fabricating a full queue", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 12,
        limit: 50,
        offset: 0,
      }),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(result.queueStatus).toBe("limited");
    expect(result.limitations[0]).toMatch(/truncated/i);
    expect(result.items).toHaveLength(1);
  });
});
