import type { SourceResult } from "@/components/workflows";
import { freshnessFromTimestamp } from "@/components/workflows/freshness";

export const FRESHNESS_UNAVAILABLE_MESSAGE =
  "Source timestamp is invalid or clock-skewed — data treated as unavailable.";

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

export function tabSourcesStale(
  tab: "overview" | "performance" | "setups",
  journal: SourceResult<{ generated_at?: string | null }> | null,
  portfolio: SourceResult<{ account: { as_of?: string | null } }> | null,
  nowMs?: number,
): boolean {
  const entries =
    tab === "overview"
      ? [
          { source: journal, timestamp: journalFreshnessTimestamp(journal) },
          { source: portfolio, timestamp: portfolioFreshnessTimestamp(portfolio) },
        ]
      : tab === "setups"
        ? [{ source: journal, timestamp: journalFreshnessTimestamp(journal) }]
        : [{ source: portfolio, timestamp: portfolioFreshnessTimestamp(portfolio) }];

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
