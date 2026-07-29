import { describe, expect, it } from "vitest";

import { setupGroupCopy, setupWinRateAriaLabel } from "./setupGroupCopy";
import * as sourceLabels from "./sourceLabels";

describe("setupGroupCopy", () => {
  it("describes strategies when group_by is strategy", () => {
    const copy = setupGroupCopy("strategy");
    expect(copy.winRateChartTitle).toMatch(/strategies/i);
    expect(copy.winRateSourceLabel).toContain("strategy win rate");
    expect(copy.bucketTableTitle).toBe("Strategy buckets");
    expect(copy.bucketTableEmptyTitle).toMatch(/strategy buckets/i);
    expect(copy.winRateListAriaLabel).toBe("Strategy win rates");
  });

  it("describes setup versions when group_by is setup_version", () => {
    const copy = setupGroupCopy("setup_version");
    expect(copy.winRateChartTitle).toMatch(/setup versions/i);
    expect(copy.bucketTableTitle).toBe("Setup version buckets");
  });

  it("builds strategy win-rate aria labels", () => {
    const label = setupWinRateAriaLabel("strategy", 3, "Breakout", "60.0%");
    expect(label).toContain("Strategy win-rate chart");
    expect(label).toContain("journal strategies buckets");
    expect(label).toContain("Breakout");
  });

  it("uses product voice labels without raw API path copy", () => {
    for (const group of ["setup", "setup_version", "strategy"] as const) {
      const copy = setupGroupCopy(group);
      for (const value of Object.values(copy)) {
        expect(value).not.toContain("GET /");
      }
    }
  });
});

describe("sourceLabels", () => {
  it("keeps provenance labels free of developer endpoint copy", () => {
    for (const value of Object.values(sourceLabels)) {
      expect(value).not.toContain("GET /");
    }
  });
});
