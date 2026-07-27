import { describe, expect, it } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";
import type { Position } from "@/lib/api/types";

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

function entryForPosition(positionId: string, symbol: string) {
  return {
    id: `j-${positionId}`,
    organization_id: "org",
    user_id: "user",
    symbol,
    timeframe: "1h" as const,
    direction: "long" as const,
    entry_rationale: "done",
    emotions: [],
    mistakes: [],
    result: "win",
    tags: [],
    screenshot_refs: [],
    linked_position_id: positionId,
    created_at: "2026-07-21T13:00:00.000Z",
  };
}

describe("buildNeedsJournalingQueue", () => {
  it("returns loading when sources are not ready", () => {
    const result = buildNeedsJournalingQueue(null, null);
    expect(result.queueStatus).toBe("loading");
    expect(result.countAvailable).toBe(false);
    expect(result.countDefinitive).toBe(false);
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

  it("lists confirmed items when both sources are complete", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [
          position({ id: "p1", symbol: "BTCUSDT", closed_at: "2026-07-22T12:00:00.000Z" }),
          position({ id: "p2", symbol: "ETHUSDT", closed_at: "2026-07-21T12:00:00.000Z" }),
        ],
        total: 2,
        limit: 50,
        offset: 0,
      }),
      ok({
        items: [entryForPosition("p2", "ETHUSDT")],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );

    expect(result.journalCoverage).toBe("complete");
    expect(result.positionsCoverage).toBe("complete");
    expect(result.countDefinitive).toBe(true);
    expect(result.queueStatus).toBe("available");
    expect(result.items).toHaveLength(1);
    expect(result.items?.[0]?.positionId).toBe("p1");
    expect(result.items?.[0]?.verification).toBe("confirmed");
  });

  it("returns definitive empty when both sources complete and all positions journaled", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      ok({
        items: [entryForPosition("p1", "BTCUSDT")],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
    expect(result.queueStatus).toBe("empty");
    expect(result.countDefinitive).toBe(true);
    expect(result.items).toEqual([]);
  });

  it("does not show definitive count when journal entries are truncated", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      ok({ items: [], total: 120, limit: 50, offset: 0 }),
    );

    expect(result.journalCoverage).toBe("truncated");
    expect(result.countDefinitive).toBe(false);
    expect(result.countAvailable).toBe(false);
    expect(result.queueStatus).toBe("unverified");
    expect(result.coverageMessage).toMatch(/only 0 of 120 journal entries are loaded/i);
    expect(result.items?.[0]?.verification).toBe("unverified");
  });

  it("labels unmatched positions as unverified when journal coverage is truncated", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [
          position({ id: "p1", symbol: "BTCUSDT" }),
          position({ id: "p2", symbol: "ETHUSDT" }),
        ],
        total: 2,
        limit: 50,
        offset: 0,
      }),
      ok({
        items: [entryForPosition("p2", "ETHUSDT")],
        total: 75,
        limit: 50,
        offset: 0,
      }),
    );

    expect(result.queueStatus).toBe("unverified");
    expect(result.items).toHaveLength(1);
    expect(result.items?.[0]?.positionId).toBe("p1");
    expect(result.items?.[0]?.verification).toBe("unverified");
    expect(result.coverageMessage).toMatch(/only 1 of 75 journal entries are loaded/i);
  });

  it("shows loaded-coverage count when journal is complete but positions are truncated", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 12,
        limit: 50,
        offset: 0,
      }),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );

    expect(result.journalCoverage).toBe("complete");
    expect(result.positionsCoverage).toBe("truncated");
    expect(result.countAvailable).toBe(true);
    expect(result.countDefinitive).toBe(false);
    expect(result.queueStatus).toBe("limited");
    expect(result.items?.[0]?.verification).toBe("confirmed");
    expect(result.limitations[0]).toMatch(/overall queue may be incomplete/i);
  });

  it("treats both truncated sources as unverified for unmatched positions", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 20,
        limit: 50,
        offset: 0,
      }),
      ok({ items: [], total: 80, limit: 50, offset: 0 }),
    );

    expect(result.journalCoverage).toBe("truncated");
    expect(result.positionsCoverage).toBe("truncated");
    expect(result.queueStatus).toBe("unverified");
    expect(result.countDefinitive).toBe(false);
    expect(result.countAvailable).toBe(false);
  });

  it("does not allow definitive empty when journal coverage is truncated with no unmatched loaded positions", () => {
    const result = buildNeedsJournalingQueue(
      ok({
        items: [position({ id: "p1", symbol: "BTCUSDT" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      ok({
        items: [entryForPosition("p1", "BTCUSDT")],
        total: 100,
        limit: 50,
        offset: 0,
      }),
    );

    expect(result.items).toEqual([]);
    expect(result.queueStatus).not.toBe("empty");
    expect(result.countDefinitive).toBe(false);
    expect(result.coverageMessage).toMatch(/cannot be fully verified/i);
  });
});
