import { describe, expect, it } from "vitest";

import {
  buildAttentionItems,
  groupAttentionItems,
  sortAttentionItems,
} from "@/components/workflows/buildAttentionItems";

describe("buildAttentionItems", () => {
  it("orders actionable sections by Dashboard priority", () => {
    const items = buildAttentionItems({
      executionMode: "paper",
      realTradingEnabled: false,
      paperOnlyConfirmed: true,
      pendingApprovals: 2,
      pendingProposals: 1,
      unreadAlerts: 3,
      unreviewedSetupAlerts: 1,
      validatedSignalsNeedingReview: 1,
      activeValidations: 1,
      draftsReady: 0,
      candidatesQueued: 2,
      runPlansPending: 0,
      openPaperPositions: 1,
      riskAlertsActive: false,
      lossLockActive: false,
      greenDayProtectionActive: false,
      overtradingWarningActive: false,
      pendingLessons: 4,
    });

    const sections = groupAttentionItems(items).map((group) => group.section);
    expect(sections).toEqual([
      "pending_decisions",
      "new_signals",
      "validation_work",
      "positions_risk",
      "lessons",
    ]);
    expect(items[0]?.section).toBe("pending_decisions");
    expect(sortAttentionItems(items).map((item) => item.priority)).toEqual(
      items.map((item) => item.priority).sort((a, b) => a - b),
    );
  });

  it("surfaces safety problems before other work", () => {
    const items = buildAttentionItems({
      executionMode: null,
      realTradingEnabled: null,
      paperOnlyConfirmed: false,
      pendingApprovals: 1,
      pendingProposals: 0,
      unreadAlerts: 0,
      unreviewedSetupAlerts: 0,
      validatedSignalsNeedingReview: 0,
      activeValidations: 0,
      draftsReady: 0,
      candidatesQueued: 0,
      runPlansPending: 0,
      openPaperPositions: 0,
      riskAlertsActive: false,
      lossLockActive: true,
      greenDayProtectionActive: false,
      overtradingWarningActive: false,
      pendingLessons: 0,
    });
    expect(items[0]?.id).toBe("safety-unverified");
    expect(items.some((item) => item.id === "safety-loss-lock")).toBe(true);
  });

  it("returns an empty actionable queue when nothing needs attention", () => {
    const items = buildAttentionItems({
      executionMode: "paper",
      realTradingEnabled: false,
      paperOnlyConfirmed: true,
      pendingApprovals: 0,
      pendingProposals: 0,
      unreadAlerts: 0,
      unreviewedSetupAlerts: 0,
      validatedSignalsNeedingReview: 0,
      activeValidations: 0,
      draftsReady: 0,
      candidatesQueued: 0,
      runPlansPending: 0,
      openPaperPositions: 0,
      riskAlertsActive: false,
      lossLockActive: false,
      greenDayProtectionActive: false,
      overtradingWarningActive: false,
      pendingLessons: 0,
    });
    expect(items).toEqual([]);
  });
});
