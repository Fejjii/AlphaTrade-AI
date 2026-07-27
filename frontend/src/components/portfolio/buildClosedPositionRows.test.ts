import { describe, expect, it } from "vitest";

import { buildClosedPositionRows } from "@/components/portfolio/buildClosedPositionRows";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { JournalEntry, PaginatedJournalEntries, PaginatedPositions, Position } from "@/lib/api/types";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function makePosition(overrides: Partial<Position> & { id: string }): Position {
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
    realized_pnl: "25",
    risk_state: {},
    status: "closed",
    opened_at: "2026-07-20T10:00:00.000Z",
    closed_at: "2026-07-21T10:00:00.000Z",
    ...overrides,
  };
}

function makeEntry(overrides: Partial<JournalEntry> & { id: string }): JournalEntry {
  return {
    organization_id: "org",
    user_id: "user",
    symbol: "BTCUSDT",
    timeframe: "1h",
    direction: "long",
    entry_rationale: "Plan followed",
    emotions: [],
    mistakes: [],
    result: "win",
    tags: [],
    screenshot_refs: [],
    created_at: "2026-07-21T12:00:00.000Z",
    ...overrides,
  };
}

describe("buildClosedPositionRows", () => {
  it("returns unavailable when closed positions fail", () => {
    const view = buildClosedPositionRows(failed(), ok({ items: [], total: 0, limit: 50, offset: 0 }));
    expect(view.status).toBe("unavailable");
    expect(view.rows).toBeNull();
  });

  it("marks journaled when a linked journal entry id exists", () => {
    const view = buildClosedPositionRows(
      ok<PaginatedPositions>({
        items: [makePosition({ id: "pos-1" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      ok<PaginatedJournalEntries>({
        items: [makeEntry({ id: "entry-1", linked_position_id: "pos-1" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
    expect(view.rows?.[0]?.journalStatus).toBe("journaled");
    expect(view.rows?.[0]?.journalHref).toContain("entry_id=entry-1");
  });

  it("marks not journaled only with complete journal coverage", () => {
    const view = buildClosedPositionRows(
      ok({ items: [makePosition({ id: "pos-2" })], total: 1, limit: 50, offset: 0 }),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.rows?.[0]?.journalStatus).toBe("not_journaled");
    expect(view.rows?.[0]?.journalHref).toContain("position_id=pos-2");
  });

  it("marks journal status unverified when journal coverage is truncated", () => {
    const view = buildClosedPositionRows(
      ok({ items: [makePosition({ id: "pos-3" })], total: 1, limit: 50, offset: 0 }),
      ok({
        items: [makeEntry({ id: "entry-x", linked_position_id: "other" })],
        total: 80,
        limit: 1,
        offset: 0,
      }),
    );
    expect(view.rows?.[0]?.journalStatus).toBe("unverified");
  });

  it("marks journal status unavailable when journal source failed", () => {
    const view = buildClosedPositionRows(
      ok({ items: [makePosition({ id: "pos-4" })], total: 1, limit: 50, offset: 0 }),
      failed("journal down"),
    );
    expect(view.rows?.[0]?.journalStatus).toBe("unavailable");
    expect(view.rows?.[0]?.journalHref).toBeNull();
  });

  it("reports truncated closed-position coverage honestly", () => {
    const view = buildClosedPositionRows(
      ok({ items: [makePosition({ id: "pos-5" })], total: 12, limit: 1, offset: 0 }),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.status).toBe("truncated");
    expect(view.coverageMessage).toMatch(/1 of 12/);
  });

  it("passes through realised pnl without fabricating a zero substitute", () => {
    const view = buildClosedPositionRows(
      ok({
        items: [makePosition({ id: "pos-6", realized_pnl: "33.5" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.rows?.[0]?.realizedPnl).toBe("33.5");
  });
});
