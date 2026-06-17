import { describe, expect, it } from "vitest";

import { buildPaperValidationView } from "@/lib/paper-validation-summary";
import type { PaperValidationRun } from "@/lib/api/types";

const baseRun: PaperValidationRun = {
  id: "run1",
  strategy_id: "s1",
  status: "running",
  runtime_mode: "scan_only",
  paper_eligible: true,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("buildPaperValidationView", () => {
  it("describes a not-started state with eligibility guidance", () => {
    const view = buildPaperValidationView(null, null, []);
    expect(view.running).toBe(false);
    expect(view.statusLabel).toBe("Not started");
    expect(view.nextAction).toContain("Resolve eligibility blockers");
  });

  it("invites starting when eligible and no run yet", () => {
    const view = buildPaperValidationView(
      null,
      {
        strategy_id: "s1",
        status: "paper_eligible",
        paper_eligible: true,
        testability_score: 80,
        blockers: [],
        eligibility_reasons: [],
        accepted_lessons: [],
        unresolved_lesson_candidates: [],
        recommendation: "continue",
        real_trading_enabled: false,
        limitations: [],
      },
      [],
    );
    expect(view.nextAction).toContain("Start paper validation");
  });

  it("summarises a scan that opened a paper trade", () => {
    const view = buildPaperValidationView(
      {
        ...baseRun,
        last_scan_at: "2024-01-01T01:00:00Z",
        last_scan_result: { triggered: true, trade_created: true },
      },
      null,
      [],
    );
    expect(view.running).toBe(true);
    expect(view.tradeOpened).toBe(true);
    expect(view.lastScanSummary).toContain("opened a simulated paper trade");
  });

  it("summarises a scan with no setup", () => {
    const view = buildPaperValidationView(
      {
        ...baseRun,
        last_scan_at: "2024-01-01T01:00:00Z",
        last_scan_result: { triggered: false, trade_created: false },
      },
      null,
      [],
    );
    expect(view.lastScanSummary).toContain("no qualifying setup");
  });

  it("surfaces blockers as skip reason", () => {
    const view = buildPaperValidationView(
      { ...baseRun, blockers: ["Daily loss protection engaged"] },
      null,
      [],
    );
    expect(view.skipReason).toBe("Daily loss protection engaged");
  });
});
