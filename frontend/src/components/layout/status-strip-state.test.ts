import { describe, expect, it } from "vitest";

import {
  resolveExecutionDisplay,
  resolveRiskDisplay,
} from "@/components/layout/status-strip-state";
import type { KillSwitchStatus } from "@/lib/api/types";

function killSwitch(partial: Partial<KillSwitchStatus>): KillSwitchStatus {
  return {
    organization_id: "org",
    active: false,
    reason: null,
    activated_by: null,
    activated_at: null,
    deactivated_by: null,
    deactivated_at: null,
    version: 1,
    scope: "organization",
    global_active: false,
    execution_blocked: false,
    ...partial,
  };
}

describe("AT-040 StatusStrip safety truth", () => {
  it("paper + real disabled shows PAPER with paper tone", () => {
    const display = resolveExecutionDisplay("paper", false, true);
    expect(display.paperConfirmed).toBe(true);
    expect(display.label).toBe("PAPER");
    expect(display.tone).toBe("paper");
  });

  it("paper + real enabled is a safety conflict without paper styling", () => {
    const display = resolveExecutionDisplay("paper", true, true);
    expect(display.paperConfirmed).toBe(false);
    expect(display.label).toBe("Safety conflict");
    expect(display.tone).not.toBe("paper");
    expect(display.label.toLowerCase()).not.toContain("paper");
  });

  it("live + real disabled never uses paper tone", () => {
    const display = resolveExecutionDisplay("live", false, true);
    expect(display.paperConfirmed).toBe(false);
    expect(display.tone).not.toBe("paper");
    expect(display.label).toBe("LIVE");
  });

  it("missing health posture is unverified", () => {
    const display = resolveExecutionDisplay(null, null, false);
    expect(display.paperConfirmed).toBe(false);
    expect(display.label).toBe("Execution unverified");
    expect(display.tone).toBe("warn");
  });

  it("partial posture is unverified and never paper", () => {
    expect(resolveExecutionDisplay("paper", null, true).label).toBe("Execution unverified");
    expect(resolveExecutionDisplay(null, false, true).label).toBe("Execution unverified");
    expect(resolveExecutionDisplay("paper", null, true).tone).not.toBe("paper");
  });

  it("contradictory states never return a PAPER badge label", () => {
    const cases: Array<[string | null, boolean | null, boolean]> = [
      ["paper", true, true],
      ["live", false, true],
      ["live", true, true],
      [null, null, false],
      ["paper", null, true],
      [null, false, true],
    ];
    for (const [mode, real, known] of cases) {
      const display = resolveExecutionDisplay(mode, real, known);
      expect(display.label).not.toBe("PAPER");
      expect(display.tone).not.toBe("paper");
    }
  });

  it("kill-switch loaded and inactive shows Risk low", () => {
    const risk = resolveRiskDisplay({
      killSwitchStatus: killSwitch({ execution_blocked: false, active: false }),
      killSwitchError: null,
      statusLoading: false,
    });
    expect(risk.level).toBe("low");
    expect(risk.label).toBe("Risk low");
    expect(risk.known).toBe(true);
  });

  it("kill-switch blocked shows critical risk", () => {
    const risk = resolveRiskDisplay({
      killSwitchStatus: killSwitch({ execution_blocked: true, active: true }),
      killSwitchError: null,
      statusLoading: false,
    });
    expect(risk.level).toBe("critical");
    expect(risk.label).toBe("Risk critical");
  });

  it("kill-switch status missing never becomes Risk low", () => {
    const risk = resolveRiskDisplay({
      killSwitchStatus: null,
      killSwitchError: null,
      statusLoading: false,
    });
    expect(risk.level).toBeNull();
    expect(risk.label).toBe("Risk unknown");
    expect(risk.known).toBe(false);
  });

  it("kill-switch request error shows Risk unknown", () => {
    const risk = resolveRiskDisplay({
      killSwitchStatus: null,
      killSwitchError: "Failed to load kill switch",
      statusLoading: false,
    });
    expect(risk.level).toBeNull();
    expect(risk.label).toBe("Risk unknown");
  });

  it("kill-switch still loading with null status shows Risk unknown", () => {
    const risk = resolveRiskDisplay({
      killSwitchStatus: null,
      killSwitchError: null,
      statusLoading: true,
    });
    expect(risk.level).toBeNull();
    expect(risk.label).toBe("Risk unknown");
  });
});
