import { journalEntryHref } from "@/components/journal/journalContext";
import { coverageFromPage } from "@/components/portfolio/portfolioMetricDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { JournalEntry, PaginatedJournalEntries, PaginatedPositions, Position } from "@/lib/api/types";

export type JournalLinkStatus =
  | "journaled"
  | "not_journaled"
  | "unverified"
  | "unavailable";

export type ClosedPositionRow = {
  position: Position;
  realizedPnl: string | null;
  closedAt: string | null;
  journalStatus: JournalLinkStatus;
  journalStatusLabel: string;
  journalHref: string | null;
  journalEntryId: string | null;
};

export type ClosedPositionsView = {
  status: "loading" | "available" | "empty" | "unavailable" | "truncated";
  rows: ClosedPositionRow[] | null;
  coverage: "complete" | "truncated" | null;
  coverageMessage: string | null;
  loaded: number | null;
  total: number | null;
  reasonUnavailable: string | null;
};

function journalStatusForPosition(
  positionId: string,
  journal: SourceResult<PaginatedJournalEntries>,
  journalByPosition: Map<string, JournalEntry>,
): Pick<ClosedPositionRow, "journalStatus" | "journalStatusLabel" | "journalHref" | "journalEntryId"> {
  if (!journal.available || !journal.data) {
    return {
      journalStatus: "unavailable",
      journalStatusLabel: "Journal status unavailable",
      journalHref: null,
      journalEntryId: null,
    };
  }

  const loaded = journal.data.items.length;
  const total = journal.data.total;
  const complete = coverageFromPage(loaded, total) === "complete";
  const entry = journalByPosition.get(positionId);

  if (entry?.id) {
    return {
      journalStatus: "journaled",
      journalStatusLabel: "Journaled",
      journalHref: journalEntryHref(entry.id),
      journalEntryId: entry.id,
    };
  }

  if (!complete) {
    return {
      journalStatus: "unverified",
      journalStatusLabel: "Journal status unverified (truncated coverage)",
      journalHref: `/journal?position_id=${encodeURIComponent(positionId)}`,
      journalEntryId: null,
    };
  }

  return {
    journalStatus: "not_journaled",
    journalStatusLabel: "Not journaled",
    journalHref: `/journal?position_id=${encodeURIComponent(positionId)}`,
    journalEntryId: null,
  };
}

/**
 * Build closed-position rows with honest pagination and journal relationship status.
 */
export function buildClosedPositionRows(
  positions: SourceResult<PaginatedPositions> | null | undefined,
  journal: SourceResult<PaginatedJournalEntries> | null | undefined,
): ClosedPositionsView {
  if (!positions || !journal) {
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
        "Closed paper positions are unavailable. This is not an empty trade history.",
    };
  }

  const items = positions.data.items.filter(
    (position) => position.status === "closed" || position.status === "liquidated",
  );
  const loaded = positions.data.items.length;
  const total = positions.data.total;
  const coverage = coverageFromPage(loaded, total);
  const coverageMessage =
    coverage === "truncated"
      ? `Showing ${loaded} of ${total} closed positions (truncated coverage).`
      : null;

  const journalByPosition = new Map<string, JournalEntry>();
  if (journal.available && journal.data) {
    for (const entry of journal.data.items) {
      if (entry.linked_position_id && !journalByPosition.has(entry.linked_position_id)) {
        journalByPosition.set(entry.linked_position_id, entry);
      }
    }
  }

  const rows: ClosedPositionRow[] = items
    .map((position) => {
      const journalFields = journalStatusForPosition(position.id, journal, journalByPosition);
      return {
        position,
        realizedPnl: position.realized_pnl ?? null,
        closedAt: position.closed_at ?? null,
        ...journalFields,
      };
    })
    .sort((a, b) => {
      const aTime = a.closedAt ? Date.parse(a.closedAt) : Number.NaN;
      const bTime = b.closedAt ? Date.parse(b.closedAt) : Number.NaN;
      const aValid = Number.isFinite(aTime);
      const bValid = Number.isFinite(bTime);
      if (aValid && bValid) return bTime - aTime;
      if (aValid) return -1;
      if (bValid) return 1;
      return a.position.symbol.localeCompare(b.position.symbol);
    });

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
        "Loaded closed-position page is empty, but full coverage is not confirmed.",
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
