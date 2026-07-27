import type { SourceResult } from "@/components/workflows/sourceResult";
import { coverageFromPage } from "@/components/portfolio/portfolioMetricDisplay";
import type {
  OpenPaperTradeItem,
  OpenPaperTradesSummary,
  PaginatedPositions,
  Position,
} from "@/lib/api/types";

export type OpenPositionRelationship = {
  strategyId: string | null;
  strategyHref: string | null;
  strategyName: string | null;
  paperTradeId: string | null;
  positionDetailHref: string;
};

export type OpenPositionRow = {
  position: Position;
  unrealizedPnl: string | null;
  size: string | null;
  leverage: string | null;
  entry: string | null;
  markPrice: string | null;
  relationships: OpenPositionRelationship;
};

export type OpenPositionsView = {
  status: "loading" | "available" | "empty" | "unavailable" | "truncated";
  rows: OpenPositionRow[] | null;
  coverage: "complete" | "truncated" | null;
  coverageMessage: string | null;
  loaded: number | null;
  total: number | null;
  reasonUnavailable: string | null;
};

function relationshipForPosition(
  position: Position,
  openTradeByPositionId: Map<string, OpenPaperTradeItem>,
): OpenPositionRelationship {
  const related = openTradeByPositionId.get(position.id);
  const strategyId = related?.strategy_id ?? null;
  return {
    strategyId,
    strategyHref: strategyId ? `/strategy-lab/${encodeURIComponent(strategyId)}` : null,
    strategyName: related?.strategy_name ?? null,
    paperTradeId: related?.paper_trade_id ?? null,
    // No dedicated position-detail route exists; link to the positions surface only.
    positionDetailHref: "/positions",
  };
}

/**
 * Build open-position rows from the positions API.
 * Dashboard open-trade items may enrich relationships only when position_id matches.
 * Never treats a failed positions source as "no open positions".
 */
export function buildOpenPositionRows(
  positions: SourceResult<PaginatedPositions> | null | undefined,
  openTradesSummary: OpenPaperTradesSummary | null | undefined,
): OpenPositionsView {
  if (!positions) {
    return {
      status: "loading",
      rows: null,
      coverage: null,
      coverageMessage: null,
      loaded: null,
      total: null,
      reasonUnavailable: null,
    };
  }

  if (!positions.available || !positions.data) {
    return {
      status: "unavailable",
      rows: null,
      coverage: null,
      coverageMessage: null,
      loaded: null,
      total: null,
      reasonUnavailable:
        positions.error ??
        "Open paper positions are unavailable. This is not confirmed empty exposure.",
    };
  }

  const openItems = positions.data.items.filter((position) => position.status === "open");
  const loaded = positions.data.items.length;
  const total = positions.data.total;
  const coverage = coverageFromPage(loaded, total);
  const coverageMessage =
    coverage === "truncated"
      ? `Showing ${loaded} of ${total} positions (truncated coverage).`
      : null;

  const openTradeByPositionId = new Map<string, OpenPaperTradeItem>();
  for (const item of openTradesSummary?.items ?? []) {
    if (item.position_id) {
      openTradeByPositionId.set(item.position_id, item);
    }
  }

  const rows: OpenPositionRow[] = openItems.map((position) => ({
    position,
    unrealizedPnl: position.unrealized_pnl ?? null,
    size: position.size ?? null,
    leverage: position.leverage ?? null,
    entry: position.entry_price ?? null,
    // Position API does not currently return a mark/current price field.
    markPrice: null,
    relationships: relationshipForPosition(position, openTradeByPositionId),
  }));

  if (rows.length === 0) {
    if (coverage === "complete") {
      return {
        status: "empty",
        rows: [],
        coverage,
        coverageMessage: null,
        loaded,
        total,
        reasonUnavailable: null,
      };
    }
    return {
      status: "truncated",
      rows: [],
      coverage,
      coverageMessage:
        coverageMessage ??
        "Loaded open-position page is empty, but full coverage is not confirmed.",
      loaded,
      total,
      reasonUnavailable: null,
    };
  }

  return {
    status: coverage === "truncated" ? "truncated" : "available",
    rows,
    coverage,
    coverageMessage,
    loaded,
    total,
    reasonUnavailable: null,
  };
}
