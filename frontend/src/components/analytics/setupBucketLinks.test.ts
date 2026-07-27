import { describe, expect, it } from "vitest";

import { buildSetupBucketLinks } from "./setupBucketLinks";
import type { SetupBucketRow } from "./setupBucketTransforms";

function row(partial: Partial<SetupBucketRow> & Pick<SetupBucketRow, "key" | "label">): SetupBucketRow {
  return {
    groupId: null,
    displayLabel: partial.label,
    tradeCount: 5,
    wins: 3,
    losses: 2,
    breakeven: 0,
    winRate: 0.6,
    winRatePct: 60,
    expectancy: 1,
    expectancyRaw: "1",
    averageR: null,
    rSampleCount: 0,
    confidence: "moderate",
    insufficient: false,
    unassigned: partial.key === "unassigned",
    noPnlData: false,
    ...partial,
  };
}

describe("buildSetupBucketLinks", () => {
  it("group_by=setup never invents setup_id from name key or label", () => {
    const links = buildSetupBucketLinks(
      row({ key: "Breakout", label: "Breakout", groupId: null }),
      "setup",
    );
    expect(links.journalHref).toBe("/journal/statistics");
    expect(links.analyticsHref).toBe("/analytics?tab=setups");
    expect(links.analyticsHref).not.toContain("setup_id=");
    expect(links.journalHref).not.toContain("setup_id=");
    expect(links.identityParam).toBeNull();
    expect(links.exactFilterNote).toMatch(/Setup version grouping/i);
  });

  it("group_by=setup_version uses group_id as setup_id and never the label", () => {
    const setupId = "11111111-1111-1111-1111-111111111111";
    const links = buildSetupBucketLinks(
      row({
        key: setupId,
        label: "Breakout",
        displayLabel: "Breakout",
        groupId: setupId,
      }),
      "setup_version",
    );
    expect(links.identityParam).toBe("setup_id");
    expect(links.identityValue).toBe(setupId);
    expect(links.journalHref).toBe(`/journal/statistics?setup_id=${setupId}`);
    expect(links.analyticsHref).toContain(`setup_id=${setupId}`);
    expect(links.analyticsHref).toContain("group_by=setup_version");
    expect(links.analyticsHref).not.toContain("Breakout");
    expect(links.analyticsHref).not.toContain("user_strategy_id=");
  });

  it("group_by=strategy uses group_id as user_strategy_id and never as setup_id", () => {
    const strategyId = "22222222-2222-2222-2222-222222222222";
    const links = buildSetupBucketLinks(
      row({
        key: strategyId,
        label: "Breakout",
        displayLabel: "Breakout",
        groupId: strategyId,
      }),
      "strategy",
    );
    expect(links.identityParam).toBe("user_strategy_id");
    expect(links.identityValue).toBe(strategyId);
    expect(links.journalHref).toBe(`/journal/statistics?user_strategy_id=${strategyId}`);
    expect(links.analyticsHref).toContain(`user_strategy_id=${strategyId}`);
    expect(links.analyticsHref).toContain("group_by=strategy");
    expect(links.analyticsHref).not.toContain("setup_id=");
    expect(links.journalHref).not.toContain("setup_id=");
  });

  it("preserves unassigned without fabricating identities", () => {
    const links = buildSetupBucketLinks(
      row({ key: "unassigned", label: "Unassigned", unassigned: true, groupId: null }),
      "setup_version",
    );
    expect(links.journalHref).toBe("/journal/statistics");
    expect(links.identityParam).toBeNull();
    expect(links.analyticsHref).toContain("tab=setups");
    expect(links.analyticsHref).not.toContain("setup_id=");
  });

  it("keeps colliding display names as distinct rows by group_id", () => {
    const a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    const b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
    const left = buildSetupBucketLinks(
      row({ key: a, label: "Breakout", groupId: a }),
      "setup_version",
    );
    const right = buildSetupBucketLinks(
      row({ key: b, label: "Breakout", groupId: b }),
      "setup_version",
    );
    expect(left.identityValue).toBe(a);
    expect(right.identityValue).toBe(b);
    expect(left.analyticsHref).not.toBe(right.analyticsHref);
  });
});
