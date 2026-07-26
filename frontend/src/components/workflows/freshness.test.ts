import { describe, expect, it } from "vitest";

import {
  ageLabelFromTimestamp,
  aggregateShellFreshness,
  freshnessFromTimestamp,
  pickNewestTimestamp,
} from "@/components/workflows/freshness";

describe("workflow freshness helpers", () => {
  const nowMs = Date.parse("2026-07-26T12:00:00.000Z");

  it("does not invent freshness without a timestamp", () => {
    expect(freshnessFromTimestamp(null)).toBeNull();
    expect(freshnessFromTimestamp(undefined)).toBeNull();
    expect(freshnessFromTimestamp("not-a-date")).toBeNull();
  });

  it("maps known timestamps to live/delayed/stale honestly", () => {
    expect(
      freshnessFromTimestamp("2026-07-26T11:59:00.000Z", { nowMs })?.state,
    ).toBe("live");
    expect(
      freshnessFromTimestamp("2026-07-26T11:50:00.000Z", { nowMs })?.state,
    ).toBe("delayed");
    expect(
      freshnessFromTimestamp("2026-07-26T11:00:00.000Z", { nowMs })?.state,
    ).toBe("stale");
  });

  it("marks fallback when the source reports fallback_used", () => {
    expect(
      freshnessFromTimestamp("2026-07-26T11:59:00.000Z", {
        nowMs,
        fallbackUsed: true,
      }),
    ).toMatchObject({ state: "fallback" });
  });

  it("treats materially future timestamps as unavailable clock skew", () => {
    expect(
      freshnessFromTimestamp("2026-07-26T12:10:00.000Z", { nowMs })?.state,
    ).toBe("unavailable");
  });

  it("picks the newest available timestamp only", () => {
    expect(
      pickNewestTimestamp([null, "2026-07-26T10:00:00.000Z", "2026-07-26T11:00:00.000Z"]),
    ).toBe("2026-07-26T11:00:00.000Z");
    expect(pickNewestTimestamp([null, undefined, ""])).toBeNull();
  });

  it("formats age labels from known timestamps", () => {
    expect(ageLabelFromTimestamp("2026-07-26T11:55:00.000Z", nowMs)).toBe("5m");
  });

  it("aggregates conservatively: live + stale => stale", () => {
    const result = aggregateShellFreshness(
      [
        {
          name: "a",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:59:00.000Z",
        },
        {
          name: "b",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:00:00.000Z",
        },
      ],
      { nowMs },
    );
    expect(result.state).toBe("stale");
  });

  it("aggregates conservatively: live + failed required => unavailable", () => {
    const result = aggregateShellFreshness(
      [
        {
          name: "a",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:59:00.000Z",
        },
        {
          name: "b",
          available: false,
          required: true,
          timestamp: null,
        },
      ],
      { nowMs },
    );
    expect(result.state).toBe("unavailable");
  });

  it("aggregates all live sources as live", () => {
    const result = aggregateShellFreshness(
      [
        {
          name: "a",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:59:00.000Z",
        },
        {
          name: "b",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:58:00.000Z",
        },
      ],
      { nowMs },
    );
    expect(result.state).toBe("live");
  });

  it("returns unavailable default when timestamps are missing", () => {
    const result = aggregateShellFreshness(
      [
        { name: "a", available: true, required: true, timestamp: null },
        { name: "b", available: true, required: true, timestamp: null },
      ],
      { nowMs },
    );
    expect(result.state).toBeNull();
  });

  it("prefers fallback when a source reports fallback_used", () => {
    const result = aggregateShellFreshness(
      [
        {
          name: "a",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:59:00.000Z",
          fallbackUsed: true,
        },
        {
          name: "b",
          available: true,
          required: true,
          timestamp: "2026-07-26T11:58:00.000Z",
        },
      ],
      { nowMs },
    );
    expect(result.state).toBe("fallback");
  });
});
