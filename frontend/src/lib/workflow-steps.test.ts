import { describe, expect, it } from "vitest";

import { buildWorkflowSteps, firstActionableStep } from "@/lib/workflow-steps";

describe("buildWorkflowSteps", () => {
  it("marks idea complete and structure current for a fresh strategy", () => {
    const steps = buildWorkflowSteps({ strategyId: "s1" });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(byKey.idea.status).toBe("complete");
    expect(byKey.structure.status).toBe("current");
    expect(byKey.backtest.status).toBe("blocked");
    expect(byKey.paper_validate.status).toBe("blocked");
  });

  it("unblocks backtest once structured rules exist", () => {
    const steps = buildWorkflowSteps({ strategyId: "s1", hasStructuredRules: true });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(byKey.structure.status).toBe("complete");
    expect(byKey.backtest.status).toBe("current");
  });

  it("unblocks paper validation when backtest done and eligible", () => {
    const steps = buildWorkflowSteps({
      strategyId: "s1",
      hasStructuredRules: true,
      backtestStatus: "completed",
      paperEligible: true,
    });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(byKey.backtest.status).toBe("complete");
    expect(byKey.paper_validate.status).toBe("current");
  });

  it("blocks paper validation when not eligible despite completed backtest", () => {
    const steps = buildWorkflowSteps({
      strategyId: "s1",
      hasStructuredRules: true,
      backtestStatus: "completed",
      paperEligible: false,
    });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(byKey.paper_validate.status).toBe("blocked");
  });

  it("flags review lessons as current when unresolved signals exist", () => {
    const steps = buildWorkflowSteps({
      strategyId: "s1",
      hasStructuredRules: true,
      backtestStatus: "completed",
      paperEligible: true,
      paperValidationStatus: "running",
      unresolvedLessonCount: 2,
    });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(byKey.review_lessons.status).toBe("current");
    expect(byKey.review_lessons.nextAction).toContain("2 learning signals");
  });

  it("marks paper validation blocked when restricted", () => {
    const steps = buildWorkflowSteps({
      strategyId: "s1",
      hasStructuredRules: true,
      backtestStatus: "completed",
      paperValidationStatus: "restricted",
    });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(byKey.paper_validate.status).toBe("blocked");
  });
});

describe("firstActionableStep", () => {
  it("returns the first current step", () => {
    const steps = buildWorkflowSteps({ strategyId: "s1", hasStructuredRules: true });
    expect(firstActionableStep(steps)?.key).toBe("backtest");
  });

  it("returns blocked step when nothing is current before it", () => {
    const steps = buildWorkflowSteps({
      strategyId: "s1",
      hasStructuredRules: true,
      backtestStatus: "completed",
      paperEligible: false,
    });
    // structure complete, backtest complete, paper blocked -> first actionable is the blocked paper step
    expect(firstActionableStep(steps)?.key).toBe("paper_validate");
  });
});
