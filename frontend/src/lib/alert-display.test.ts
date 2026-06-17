import { describe, expect, it } from "vitest";

import {
  alertNextAction,
  alertSourceLabel,
  alertTypeLabel,
  severityRank,
  severityVariant,
} from "@/lib/alert-display";

describe("alert-display", () => {
  it("maps known alert types to human-readable titles", () => {
    expect(alertTypeLabel("setup_signal_detected")).toBe("Setup signal detected");
    expect(alertTypeLabel("data_stale")).toBe("Market data is stale");
  });

  it("uses calm wording for behavioural alerts", () => {
    expect(alertTypeLabel("overtrading_warning")).toBe("Trading frequency notice");
    expect(alertTypeLabel("daily_loss_lock_warning")).toBe("Daily loss protection notice");
  });

  it("falls back to a readable label for unknown types", () => {
    expect(alertTypeLabel("some_new_type")).toBe("some new type");
  });

  it("maps sources to labels and defaults to paper validation", () => {
    expect(alertSourceLabel("market_watcher_bridge")).toBe("Market watcher bridge");
    expect(alertSourceLabel(undefined)).toBe("Paper validation");
  });

  it("ranks and colours severities", () => {
    expect(severityRank("critical")).toBeGreaterThan(severityRank("warning"));
    expect(severityRank("warning")).toBeGreaterThan(severityRank("info"));
    expect(severityVariant("critical")).toBe("danger");
    expect(severityVariant("info")).toBe("info");
  });

  it("always reminds that alerts never trade", () => {
    expect(alertNextAction("setup_signal_detected")).toContain("never place");
    expect(alertNextAction("unknown")).toContain("never execute trades");
  });
});
