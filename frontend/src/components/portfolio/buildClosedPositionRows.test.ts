import { describe, expect, it } from "vitest";

import { buildClosedPositionRows } from "@/components/portfolio/buildClosedPositionRows";
import { parseJournalQuery } from "@/components/journal/journalContext";
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

function okWithError<T>(data: T, error: string): SourceResult<T> {
  return { data, available: true, error, fallbackUsed: false };
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
    expect(view.rows?.[0]?.journalHref).toBe("/journal?entry=entry-1");
    expect(view.rows?.[0]?.journalHref).not.toContain("entry_id=");
  });

  it("generates a journal entry deep link understood by parseJournalQuery", () => {
    const view = buildClosedPositionRows(
      ok({ items: [makePosition({ id: "pos-link" })], total: 1, limit: 50, offset: 0 }),
      ok({
        items: [makeEntry({ id: "entry-42", linked_position_id: "pos-link" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
    const href = view.rows?.[0]?.journalHref;
    expect(href).toBeTruthy();
    const params = new URLSearchParams(href!.split("?")[1] ?? "");
    const parsed = parseJournalQuery(params);
    expect(parsed.entryId).toBe("entry-42");
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

  it("keeps liquidated closed positions in the closed history rows (FP2-221)", () => {
    const view = buildClosedPositionRows(
      ok({
        items: [
          makePosition({ id: "pos-closed", status: "closed" }),
          makePosition({ id: "pos-liq", status: "liquidated", symbol: "ETHUSDT" }),
          makePosition({ id: "pos-open", status: "open" }),
        ],
        total: 3,
        limit: 50,
        offset: 0,
      }),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.rows?.map((row) => row.position.id)).toEqual(["pos-closed", "pos-liq"]);
    expect(view.rows?.map((row) => row.position.status)).toEqual(["closed", "liquidated"]);
  });

  it("shows surviving rows with a partial warning when closed source failed (FP2-221)", () => {
    const view = buildClosedPositionRows(
      okWithError(
        {
          items: [makePosition({ id: "pos-liq", status: "liquidated", symbol: "ETHUSDT" })],
          total: 1,
          limit: 50,
          offset: 0,
        },
        "Closed positions unavailable; showing liquidated positions only.",
      ),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.status).toBe("truncated");
    expect(view.rows).toHaveLength(1);
    expect(view.coverage).toBe("unknown");
    expect(view.coverageMessage).toMatch(/Closed positions unavailable/);
    expect(screenSafeEmptyMessage(view)).not.toMatch(/complete coverage/i);
  });

  it("shows surviving rows with a partial warning when liquidated source failed (FP2-221)", () => {
    const view = buildClosedPositionRows(
      okWithError(
        {
          items: [makePosition({ id: "pos-closed", status: "closed" })],
          total: 1,
          limit: 50,
          offset: 0,
        },
        "Liquidated positions unavailable; showing closed positions only.",
      ),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.status).toBe("truncated");
    expect(view.rows).toHaveLength(1);
    expect(view.coverage).toBe("unknown");
    expect(view.coverageMessage).toMatch(/Liquidated positions unavailable/);
  });

  it("never claims complete empty history during partial source failure (FP2-221)", () => {
    const view = buildClosedPositionRows(
      okWithError(
        { items: [], total: 0, limit: 50, offset: 0 },
        "Closed positions unavailable; showing liquidated positions only.",
      ),
      ok({ items: [], total: 0, limit: 50, offset: 0 }),
    );
    expect(view.status).toBe("truncated");
    expect(view.status).not.toBe("empty");
    expect(view.coverage).toBe("unknown");
    expect(view.coverageMessage).toMatch(/Closed positions unavailable/);
    expect(view.coverageMessage).toMatch(/cannot be confirmed/i);
  });
});

function screenSafeEmptyMessage(view: ReturnType<typeof buildClosedPositionRows>): string {
  return view.status === "empty" ? "No closed paper positions in complete coverage." : "";
}
