import type { SourceResult } from "@/components/workflows/sourceResult";
import type { PaginatedJournalEntries, PaginatedPositions } from "@/lib/api/types";

export type SourceCoverage = "complete" | "truncated";

export type NeedsJournalingVerification = "confirmed" | "unverified";

export type NeedsJournalingItem = {
  positionId: string;
  symbol: string;
  direction: string;
  status: string;
  closedAt: string | null;
  realizedPnl: string | null;
  href: string;
  verification: NeedsJournalingVerification;
};

export type NeedsJournalingQueueStatus =
  | "loading"
  | "available"
  | "empty"
  | "unavailable"
  | "limited"
  | "unverified";

export type NeedsJournalingResult = {
  /** True when a count may be shown (definitive or loaded-coverage qualified). */
  countAvailable: boolean;
  /** True only when journal coverage is complete and the count is definitive. */
  countDefinitive: boolean;
  items: NeedsJournalingItem[] | null;
  queueStatus: NeedsJournalingQueueStatus;
  journalCoverage: SourceCoverage | null;
  positionsCoverage: SourceCoverage | null;
  coverageMessage: string | null;
  limitations: string[];
  reasonUnavailable: string | null;
};

function coverageFromPage(
  loaded: number,
  total: number,
): SourceCoverage {
  return loaded < total ? "truncated" : "complete";
}

function journalTruncationMessage(loaded: number, total: number): string {
  return `Needs-journaling status cannot be fully verified because only ${loaded} of ${total} journal entries are loaded.`;
}

/**
 * Derive a needs-journaling queue from closed positions and existing journal links.
 * Never claims a trade definitively needs journaling when journal-entry coverage is truncated.
 */
export function buildNeedsJournalingQueue(
  positions: SourceResult<PaginatedPositions> | null | undefined,
  entries: SourceResult<PaginatedJournalEntries> | null | undefined,
): NeedsJournalingResult {
  if (!positions || !entries) {
    return {
      countAvailable: false,
      countDefinitive: false,
      items: null,
      queueStatus: "loading",
      journalCoverage: null,
      positionsCoverage: null,
      coverageMessage: null,
      limitations: [],
      reasonUnavailable: null,
    };
  }

  if (!positions.available) {
    return {
      countAvailable: false,
      countDefinitive: false,
      items: null,
      queueStatus: "unavailable",
      journalCoverage: null,
      positionsCoverage: null,
      coverageMessage: null,
      limitations: [],
      reasonUnavailable:
        "Closed positions are unavailable, so the needs-journaling queue cannot be built.",
    };
  }

  if (!entries.available) {
    return {
      countAvailable: false,
      countDefinitive: false,
      items: null,
      queueStatus: "unavailable",
      journalCoverage: null,
      positionsCoverage: null,
      coverageMessage: null,
      limitations: [],
      reasonUnavailable:
        "Journal entries are unavailable, so completed trades cannot be confirmed as needing journaling.",
    };
  }

  const positionItems = positions.data?.items ?? [];
  const entryItems = entries.data?.items ?? [];
  const positionTotal = positions.data?.total ?? positionItems.length;
  const entryTotal = entries.data?.total ?? entryItems.length;
  const entryLoaded = entryItems.length;
  const positionLoaded = positionItems.length;

  const journalCoverage = coverageFromPage(entryLoaded, entryTotal);
  const positionsCoverage = coverageFromPage(positionLoaded, positionTotal);
  const journalComplete = journalCoverage === "complete";
  const positionsComplete = positionsCoverage === "complete";
  const bothComplete = journalComplete && positionsComplete;

  const limitations: string[] = [];
  let coverageMessage: string | null = null;

  if (!journalComplete) {
    coverageMessage = journalTruncationMessage(entryLoaded, entryTotal);
    limitations.push(coverageMessage);
  }
  if (!positionsComplete) {
    limitations.push(
      `Closed-position list is truncated (${positionLoaded} of ${positionTotal} loaded). The overall queue may be incomplete.`,
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

  const unmatched = completed.filter((position) => !journaledPositionIds.has(position.id));

  const items: NeedsJournalingItem[] = unmatched
    .map((position) => ({
      positionId: position.id,
      symbol: position.symbol,
      direction: position.direction,
      status: position.status,
      closedAt: position.closed_at ?? null,
      realizedPnl: position.realized_pnl ?? null,
      href: `/journal?position_id=${encodeURIComponent(position.id)}`,
      verification: (journalComplete ? "confirmed" : "unverified") as NeedsJournalingVerification,
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

  const confirmedItems = items.filter((item) => item.verification === "confirmed");

  if (items.length === 0) {
    if (bothComplete) {
      return {
        countAvailable: true,
        countDefinitive: true,
        items: [],
        queueStatus: "empty",
        journalCoverage,
        positionsCoverage,
        coverageMessage: null,
        limitations,
        reasonUnavailable: null,
      };
    }

    return {
      countAvailable: false,
      countDefinitive: false,
      items: [],
      queueStatus: journalComplete ? "limited" : "unverified",
      journalCoverage,
      positionsCoverage,
      coverageMessage,
      limitations,
      reasonUnavailable: null,
    };
  }

  if (!journalComplete) {
    return {
      countAvailable: false,
      countDefinitive: false,
      items,
      queueStatus: "unverified",
      journalCoverage,
      positionsCoverage,
      coverageMessage,
      limitations,
      reasonUnavailable: null,
    };
  }

  if (!positionsComplete) {
    return {
      countAvailable: true,
      countDefinitive: false,
      items: confirmedItems,
      queueStatus: "limited",
      journalCoverage,
      positionsCoverage,
      coverageMessage: null,
      limitations,
      reasonUnavailable: null,
    };
  }

  return {
    countAvailable: true,
    countDefinitive: true,
    items: confirmedItems,
    queueStatus: "available",
    journalCoverage,
    positionsCoverage,
    coverageMessage: null,
    limitations,
    reasonUnavailable: null,
  };
}
