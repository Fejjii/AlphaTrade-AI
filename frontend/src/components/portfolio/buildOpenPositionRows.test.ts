import { describe, expect, it } from "vitest";

import { buildOpenPositionRows } from "@/components/portfolio/buildOpenPositionRows";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { OpenPaperTradesSummary, PaginatedPositions, Position } from "@/lib/api/types";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "positions down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function makePosition(overrides: Partial<Position> & { id: string }): Position {
  return {
    organization_id: "org",
    user_id: "user",
    symbol: "BTCUSDT",
    direction: "long",
    size: "0.5",
    entry_price: "100",
    leverage: "2",
    take_profits: [],
    unrealized_pnl: "12",
    realized_pnl: "0",
    risk_state: {},
    status: "open",
    opened_at: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

describe("buildOpenPositionRows", () => {
  it("returns loading when source is absent", () => {
    expect(buildOpenPositionRows(null, null).status).toBe("loading");
  });

  it("does not treat failed open-position source as empty", () => {
    const view = buildOpenPositionRows(failed(), null);
    expect(view.status).toBe("unavailable");
    expect(view.rows).toBeNull();
    expect(view.reasonUnavailable).toMatch(/positions down|unavailable/i);
  });

  it("confirms empty open positions only with complete coverage", () => {
    const view = buildOpenPositionRows(
      ok<PaginatedPositions>({ items: [], total: 0, limit: 50, offset: 0 }),
      null,
    );
    expect(view.status).toBe("empty");
    expect(view.coverage).toBe("complete");
  });

  it("marks truncated coverage when page is incomplete", () => {
    const view = buildOpenPositionRows(
      ok<PaginatedPositions>({
        items: [makePosition({ id: "pos-1" })],
        total: 5,
        limit: 1,
        offset: 0,
      }),
      null,
    );
    expect(view.status).toBe("truncated");
    expect(view.coverageMessage).toMatch(/1 of 5/);
  });

  it("links strategy only when dashboard provides a real strategy_id for the position", () => {
    const summary: OpenPaperTradesSummary = {
      proposal_flow_count: 1,
      paper_validation_count: 0,
      total_count: 1,
      total_open_exposure: "100",
      items: [
        {
          position_id: "pos-1",
          strategy_id: "strat-1",
          strategy_name: "HTF Pullback",
          symbol: "BTCUSDT",
          direction: "long",
          unrealized_pnl: "12",
          status: "open",
        },
      ],
      limitations: [],
    };
    const view = buildOpenPositionRows(
      ok({ items: [makePosition({ id: "pos-1" })], total: 1, limit: 50, offset: 0 }),
      summary,
    );
    expect(view.rows?.[0]?.relationships.strategyHref).toBe("/strategy-lab/strat-1");
  });

  it("omits strategy link when no real identifier exists", () => {
    const view = buildOpenPositionRows(
      ok({ items: [makePosition({ id: "pos-2" })], total: 1, limit: 50, offset: 0 }),
      {
        proposal_flow_count: 0,
        paper_validation_count: 0,
        total_count: 0,
        total_open_exposure: null,
        items: [],
        limitations: [],
      },
    );
    expect(view.rows?.[0]?.relationships.strategyHref).toBeNull();
    expect(view.rows?.[0]?.markPrice).toBeNull();
  });
});
