import { describe, expect, it } from "vitest";

import { strategyStatusView } from "@/lib/strategy-status";

describe("strategyStatusView", () => {
  it("returns Needs structure for a draft strategy", () => {
    const view = strategyStatusView({ validation_status: "draft", backtest_status: "not_run" });
    expect(view.label).toBe("Needs structure");
    expect(view.variant).toBe("muted");
  });

  it("returns Ready for backtest when validated but not yet run", () => {
    const view = strategyStatusView({ validation_status: "validated", backtest_status: "not_run" });
    expect(view.label).toBe("Ready for backtest");
  });

  it("returns Needs more sample after a completed backtest without eligibility", () => {
    const view = strategyStatusView({ backtest_status: "completed", paper_eligible: false });
    expect(view.label).toBe("Needs more sample");
    expect(view.variant).toBe("warning");
  });

  it("returns Paper eligible when eligible", () => {
    const view = strategyStatusView({ backtest_status: "completed", paper_eligible: true });
    expect(view.label).toBe("Paper eligible");
    expect(view.variant).toBe("success");
  });

  it("returns Paper validation running when active", () => {
    const view = strategyStatusView({ paper_validation_status: "running" });
    expect(view.label).toBe("Paper validation running");
    expect(view.variant).toBe("info");
  });

  it("returns Paper validated when validated", () => {
    const view = strategyStatusView({ paper_validation_status: "validated" });
    expect(view.label).toBe("Paper validated");
  });

  it("returns Restricted when blocked", () => {
    const view = strategyStatusView({ paper_validation_status: "restricted" });
    expect(view.label).toBe("Restricted");
    expect(view.variant).toBe("danger");
  });
});
