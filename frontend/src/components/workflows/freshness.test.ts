import { describe, expect, it } from "vitest";

import {
  ageLabelFromTimestamp,
  aggregateShellFreshness,
  freshnessFromTimestamp,
  pickNewestTimestamp,
} from "@/components/workflows/freshness";

describe("workflow freshness helpers", () => {
  const nowMs = Date.parse("2026-07-26T12:00:00.000Z");
  const liveTs = "2026-07-26T11:59:00.000Z";
  const staleTs = "2026-07-26T11:00:00.000Z";
  const futureTs = "2026-07-26T12:10:00.000Z";

  it("does not invent freshness without a timestamp", () => {
    expect(freshnessFromTimestamp(null)).toBeNull();
    expect(freshnessFromTimestamp(undefined)).toBeNull();
    expect(freshnessFromTimestamp("not-a-date")).toBeNull();
  });

  it("maps known timestamps to live/delayed/stale honestly", () => {
    expect(freshnessFromTimestamp(liveTs, { nowMs })?.state).toBe("live");
    expect(
      freshnessFromTimestamp("2026-07-26T11:50:00.000Z", { nowMs })?.state,
    ).toBe("delayed");
    expect(freshnessFromTimestamp(staleTs, { nowMs })?.state).toBe("stale");
  });

  it("marks fallback when the source reports fallback_used", () => {
    expect(
      freshnessFromTimestamp(liveTs, {
        nowMs,
        fallbackUsed: true,
      }),
    ).toMatchObject({ state: "fallback" });
  });

  it("treats materially future timestamps as unavailable clock skew", () => {
    expect(freshnessFromTimestamp(futureTs, { nowMs })?.state).toBe("unavailable");
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

  it("live plus missing timestamp equals unavailable", () => {
    const result = aggregateShellFreshness(
      [
        { name: "live", available: true, required: true, timestamp: liveTs },
        { name: "missing", available: true, required: true, timestamp: null },
      ],
      { nowMs },
    );
    expect(result.state).toBe("unavailable");
  });

  it("live plus invalid timestamp equals unavailable", () => {
    const result = aggregateShellFreshness(
      [
        { name: "live", available: true, required: true, timestamp: liveTs },
        { name: "invalid", available: true, required: true, timestamp: "not-a-date" },
      ],
      { nowMs },
    );
    expect(result.state).toBe("unavailable");
  });

  it("live plus future timestamp equals unavailable", () => {
    const result = aggregateShellFreshness(
      [
        { name: "live", available: true, required: true, timestamp: liveTs },
        { name: "future", available: true, required: true, timestamp: futureTs },
      ],
      { nowMs },
    );
    expect(result.state).toBe("unavailable");
  });

  it("live plus stale equals stale", () => {
    const result = aggregateShellFreshness(
      [
        { name: "live", available: true, required: true, timestamp: liveTs },
        { name: "stale", available: true, required: true, timestamp: staleTs },
      ],
      { nowMs },
    );
    expect(result.state).toBe("stale");
  });

  it("live plus failed required source equals unavailable", () => {
    const result = aggregateShellFreshness(
      [
        { name: "live", available: true, required: true, timestamp: liveTs },
        { name: "failed", available: false, required: true, timestamp: null },
      ],
      { nowMs },
    );
    expect(result.state).toBe("unavailable");
  });

  it("all live equals live", () => {
    const result = aggregateShellFreshness(
      [
        { name: "a", available: true, required: true, timestamp: liveTs },
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

  it("fallback plus live equals fallback", () => {
    const result = aggregateShellFreshness(
      [
        {
          name: "fallback",
          available: true,
          required: true,
          timestamp: liveTs,
          fallbackUsed: true,
        },
        { name: "live", available: true, required: true, timestamp: liveTs },
      ],
      { nowMs },
    );
    expect(result.state).toBe("fallback");
  });

  it("no applicable sources leaves freshness unavailable", () => {
    expect(aggregateShellFreshness([], { nowMs }).state).toBe("unavailable");
  });

  it("empty timestamp on available source contributes unavailable, not silent drop", () => {
    const result = aggregateShellFreshness(
      [{ name: "empty", available: true, required: true, timestamp: "" }],
      { nowMs },
    );
    expect(result.state).toBe("unavailable");
  });
});
