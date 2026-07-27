import { describe, expect, it } from "vitest";

import type { SourceResult } from "@/components/workflows";

import {
  FRESHNESS_UNAVAILABLE_MESSAGE,
  gateSourceByFreshness,
  journalFreshnessTimestamp,
  portfolioFreshnessTimestamp,
  tabSourcesStale,
} from "./sourceFreshness";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

describe("sourceFreshness", () => {
  const nowMs = Date.parse("2026-07-25T12:00:00Z");

  it("treats future-skewed journal generated_at as unavailable", () => {
    const journal = ok({ generated_at: "2026-07-25T12:05:00Z" });
    const gated = gateSourceByFreshness(journal, journalFreshnessTimestamp(journal), nowMs);
    expect(gated?.available).toBe(false);
    expect(gated?.error).toBe(FRESHNESS_UNAVAILABLE_MESSAGE);
  });

  it("treats future-skewed portfolio as_of as unavailable", () => {
    const portfolio = ok({ account: { as_of: "2026-07-25T12:02:00Z" } });
    const gated = gateSourceByFreshness(
      portfolio,
      portfolioFreshnessTimestamp(portfolio),
      nowMs,
    );
    expect(gated?.available).toBe(false);
  });

  it("reports overview tab stale when all available sources are stale", () => {
    const staleTs = "2026-07-25T11:00:00Z";
    const journal = ok({ generated_at: staleTs });
    const portfolio = ok({ account: { as_of: staleTs } });
    expect(tabSourcesStale("overview", journal, portfolio, nowMs)).toBe(true);
  });

  it("does not report overview tab stale when one source is live", () => {
    const journal = ok({ generated_at: "2026-07-25T11:59:00Z" });
    const portfolio = ok({ account: { as_of: "2026-07-25T11:00:00Z" } });
    expect(tabSourcesStale("overview", journal, portfolio, nowMs)).toBe(false);
  });

  it("excludes freshness-unavailable sources from stale tab calculation", () => {
    const journal = ok({ generated_at: "2026-07-25T11:59:00Z" });
    const portfolio = ok({ account: { as_of: "2026-07-25T12:05:00Z" } });
    expect(tabSourcesStale("overview", journal, portfolio, nowMs)).toBe(false);
  });
});
