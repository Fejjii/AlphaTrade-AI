import { describe, expect, it } from "vitest";

import {
  candidateDetailHref,
  draftDetailHref,
  relatedObjectAvailable,
  relatedObjectHref,
  runPlanDetailHref,
  runSessionDetailHref,
  validateHubHref,
} from "@/components/validate/validationLinks";

describe("validationLinks", () => {
  it("builds dynamic detail links from existing ids", () => {
    expect(validateHubHref()).toBe("/paper-validation");
    expect(draftDetailHref("draft-1")).toBe("/paper-validation/drafts/draft-1");
    expect(candidateDetailHref("cand-1")).toBe("/paper-validation/candidates/cand-1");
    expect(runPlanDetailHref("plan-1")).toBe("/paper-validation/run-plans/plan-1");
    expect(runSessionDetailHref("sess-1")).toBe("/paper-validation/run-sessions/sess-1");
  });

  it("falls back safely when related object ids are missing", () => {
    expect(relatedObjectAvailable(null)).toBe(false);
    expect(relatedObjectAvailable("")).toBe(false);
    expect(relatedObjectHref("draft", null)).toBe("/paper-validation/drafts");
    expect(relatedObjectHref("candidate", "  ")).toBe("/paper-validation/candidates");
    expect(relatedObjectHref("run_plan", undefined)).toBe("/paper-validation/run-plans");
    expect(relatedObjectHref("run_session", null)).toBe("/paper-validation/run-sessions");
  });

  it("does not create self-referential empty-id loops", () => {
    const fallback = relatedObjectHref("candidate", null);
    expect(fallback).toBe("/paper-validation/candidates");
    expect(fallback.includes("null")).toBe(false);
    expect(fallback.endsWith("/")).toBe(false);
  });
});
