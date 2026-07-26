import type { SourceResult } from "@/components/workflows/sourceResult";
import type { PaginatedJournalEntries, PaginatedPositions } from "@/lib/api/types";

export type NeedsJournalingItem = {
  positionId: string;
  symbol: string;
  direction: string;
  status: string;
  closedAt: string | null;
  realizedPnl: string | null;
  href: string;
};

export type NeedsJournalingQueueStatus =
  | "loading"
  | "available"
  | "empty"
  | "unavailable"
  | "limited";

export type NeedsJournalingResult = {
  /** True only when both sources loaded and a count may be shown honestly. */
  countAvailable: boolean;
  items: NeedsJournalingItem[] | null;
  queueStatus: NeedsJournalingQueueStatus;
  limitations: string[];
  reasonUnavailable: string | null;
};

/**
 * Derive a needs-journaling queue from closed positions and existing journal links.
 * Never claims a trade needs journaling when either source is unavailable.
 */
export function buildNeedsJournalingQueue(
  positions: SourceResult<PaginatedPositions> | null | undefined,
  entries: SourceResult<PaginatedJournalEntries> | null | undefined,
): NeedsJournalingResult {
  if (!positions || !entries) {
    return {
      countAvailable: false,
      items: null,
      queueStatus: "loading",
      limitations: [],
      reasonUnavailable: null,
    };
  }

  if (!positions.available) {
    return {
      countAvailable: false,
      items: null,
      queueStatus: "unavailable",
      limitations: [],
      reasonUnavailable:
        "Closed positions are unavailable, so the needs-journaling queue cannot be built.",
    };
  }

  if (!entries.available) {
    return {
      countAvailable: false,
      items: null,
      queueStatus: "unavailable",
      limitations: [],
      reasonUnavailable:
        "Journal entries are unavailable, so completed trades cannot be confirmed as needing journaling.",
    };
  }

  const positionItems = positions.data?.items ?? [];
  const entryItems = entries.data?.items ?? [];
  const positionTotal = positions.data?.total ?? positionItems.length;
  const entryTotal = entries.data?.total ?? entryItems.length;

  const limitations: string[] = [];
  if (positionItems.length < positionTotal) {
    limitations.push(
      `Closed-position list is truncated (${positionItems.length} of ${positionTotal} loaded). Queue may be incomplete.`,
    );
  }
  if (entryItems.length < entryTotal) {
    limitations.push(
      `Journal entry list is truncated (${entryItems.length} of ${entryTotal} loaded). Some positions may already be journaled outside this page.`,
    );
  }

  const journaledPositionIds = new Set(
    entryItems
      .map((entry) => entry.linked_position_id)
      .filter((id): id is string => Boolean(id)),
  );

  const completed = positionItems.filter(
    (position) => position.status === "closed" || position.status === "liquidated",
  );

  const items = completed
    .filter((position) => !journaledPositionIds.has(position.id))
    .map((position) => ({
      positionId: position.id,
      symbol: position.symbol,
      direction: position.direction,
      status: position.status,
      closedAt: position.closed_at ?? null,
      realizedPnl: position.realized_pnl ?? null,
      href: `/journal?position_id=${encodeURIComponent(position.id)}`,
    }))
    .sort((a, b) => {
      const aTime = a.closedAt ? Date.parse(a.closedAt) : Number.NaN;
      const bTime = b.closedAt ? Date.parse(b.closedAt) : Number.NaN;
      const aValid = Number.isFinite(aTime);
      const bValid = Number.isFinite(bTime);
      if (aValid && bValid) return bTime - aTime;
      if (aValid) return -1;
      if (bValid) return 1;
      return a.symbol.localeCompare(b.symbol);
    });

  return {
    countAvailable: true,
    items,
    queueStatus: items.length === 0 ? "empty" : limitations.length > 0 ? "limited" : "available",
    limitations,
    reasonUnavailable: null,
  };
}
