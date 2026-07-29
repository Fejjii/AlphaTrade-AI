import type { SourceResult } from "@/components/workflows";
import { freshnessFromTimestamp } from "@/components/workflows/freshness";

import type { AnalyticsTab } from "./filterValidation";

export const FRESHNESS_UNAVAILABLE_MESSAGE =
  "Source timestamp is invalid or clock-skewed — data treated as unavailable.";

export const NO_SERVER_FRESHNESS_TIMESTAMP_NOTE =
  "This source does not provide a freshness timestamp.";

export function journalFreshnessTimestamp(
  journal: SourceResult<{ generated_at?: string | null }> | null,
): string | null {
  if (!journal?.available || !journal.data) return null;
  return journal.data.generated_at ?? null;
}

export function portfolioFreshnessTimestamp(
  portfolio: SourceResult<{ account: { as_of?: string | null } }> | null,
): string | null {
  if (!portfolio?.available || !portfolio.data) return null;
  return portfolio.data.account.as_of ?? null;
}

/** True when a journal statistics source with generated_at is stale (not unavailable). */
export function journalSourceStale(
  journal: SourceResult<{ generated_at?: string | null }> | null,
  nowMs?: number,
): boolean {
  const timestamp = journalFreshnessTimestamp(journal);
  if (!journal?.available || !timestamp) return false;
  return freshnessFromTimestamp(timestamp, { nowMs })?.state === "stale";
}

/** Treat future-skewed or invalid timestamps as unavailable for display. */
export function gateSourceByFreshness<T>(
  source: SourceResult<T> | null,
  timestamp: string | null,
  nowMs?: number,
): SourceResult<T> | null {
  if (!source?.available) return source;
  const freshness = freshnessFromTimestamp(timestamp, { nowMs });
  if (freshness?.state === "unavailable") {
    return {
      ...source,
      available: false,
      error: FRESHNESS_UNAVAILABLE_MESSAGE,
    };
  }
  return source;
}

type Timestamped = SourceResult<{ generated_at?: string | null }> | null;

export function tabSourcesStale(
  tab: AnalyticsTab,
  journal: SourceResult<{ generated_at?: string | null }> | null,
  portfolio: SourceResult<{ account: { as_of?: string | null } }> | null,
  nowMs?: number,
  extras: Timestamped[] = [],
): boolean {
  const entries =
    tab === "overview"
      ? [
          { source: journal, timestamp: journalFreshnessTimestamp(journal) },
          { source: portfolio, timestamp: portfolioFreshnessTimestamp(portfolio) },
        ]
      : tab === "setups"
        ? [{ source: journal, timestamp: journalFreshnessTimestamp(journal) }]
        : tab === "performance"
          ? [{ source: portfolio, timestamp: portfolioFreshnessTimestamp(portfolio) }]
          : extras.map((source) => ({
              source,
              timestamp: journalFreshnessTimestamp(source),
            }));

  const freshAvailable = entries.filter(({ source, timestamp }) => {
    if (!source?.available || !timestamp) return false;
    const freshness = freshnessFromTimestamp(timestamp, { nowMs });
    return freshness?.state !== "unavailable";
  });

  if (!freshAvailable.length) return false;

  const states = freshAvailable.map(
    ({ timestamp }) => freshnessFromTimestamp(timestamp, { nowMs })?.state,
  );

  return states.length > 0 && states.every((state) => state === "stale");
}
