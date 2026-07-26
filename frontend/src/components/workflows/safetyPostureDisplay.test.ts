import { describe, expect, it } from "vitest";

import { describeSafetyPosture } from "@/components/workflows/safetyPostureDisplay";

describe("describeSafetyPosture", () => {
  it("confirms paper only when mode is paper and real trading is disabled", () => {
    const posture = describeSafetyPosture("paper", false);
    expect(posture.paperConfirmed).toBe(true);
    expect(posture.executionLabel).toBe("PAPER mode");
    expect(posture.runtimeBadgeLabel).toBe("Paper only");
    expect(posture.conflictMessage).toBeNull();
  });

  it("flags safety conflict when real trading is enabled", () => {
    const posture = describeSafetyPosture("paper", true);
    expect(posture.paperConfirmed).toBe(false);
    expect(posture.kind).toBe("safety_conflict");
    expect(posture.runtimeBadgeLabel).toBe("Safety conflict");
    expect(posture.conflictMessage).toMatch(/real trading is enabled/i);
  });

  it("does not style live + real-disabled as confirmed paper", () => {
    const posture = describeSafetyPosture("live", false);
    expect(posture.paperConfirmed).toBe(false);
    expect(posture.executionLabel).toBe("LIVE mode");
    expect(posture.runtimeBadgeLabel).toBe("live mode");
  });

  it("marks unknown posture as unverified", () => {
    const posture = describeSafetyPosture(null, null);
    expect(posture.paperConfirmed).toBe(false);
    expect(posture.executionLabel).toBe("Execution unverified");
    expect(posture.runtimeBadgeLabel).toBe("Runtime posture unverified");
  });

  it("marks partial posture as paper mode not confirmed", () => {
    const posture = describeSafetyPosture("paper", null);
    expect(posture.paperConfirmed).toBe(false);
    expect(posture.runtimeBadgeLabel).toBe("Paper mode not confirmed");
  });
});
