import { describe, expect, it } from "vitest";

import {
  ageLabelFromTimestamp,
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

  it("picks the newest available timestamp only", () => {
    expect(
      pickNewestTimestamp([null, "2026-07-26T10:00:00.000Z", "2026-07-26T11:00:00.000Z"]),
    ).toBe("2026-07-26T11:00:00.000Z");
    expect(pickNewestTimestamp([null, undefined, ""])).toBeNull();
  });

  it("formats age labels from known timestamps", () => {
    expect(ageLabelFromTimestamp("2026-07-26T11:55:00.000Z", nowMs)).toBe("5m");
  });
});
