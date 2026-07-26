import { describe, expect, it } from "vitest";

import {
  candidateNextAction,
  draftMissingStructure,
  draftNextAction,
  excursionAvailabilityLabel,
  outcomeStatusLabel,
  runPlanCriteriaIssues,
  runPlanNextAction,
  runSessionNextAction,
} from "@/components/validate/validationDisplay";
import type {
  PaperValidationCandidateItem,
  PaperValidationDraftItem,
  PaperValidationRunPlanItem,
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";

const checklist = {
  trend_checked: true,
  support_resistance_checked: false,
  volume_checked: false,
  risk_reward_checked: true,
  invalidation_checked: true,
  higher_timeframe_checked: true,
  news_or_funding_checked: false,
};

describe("validationDisplay", () => {
  it("derives draft next actions and missing structure", () => {
    const incomplete: PaperValidationDraftItem = {
      draft_id: "d1",
      source_alert_id: "a1",
      risk_mode: "conservative",
      status: "draft",
      created_at: "2026-07-26T10:00:00.000Z",
      prep_status: "needs_review",
      checklist,
      prep_completion_score: 40,
      missing_checklist_items: ["volume_checked"],
      is_ready_for_validation: false,
      thesis: "",
      entry_criteria: "",
      invalidation_criteria: "keep",
    };
    expect(draftMissingStructure(incomplete)).toEqual(
      expect.arrayContaining(["volume_checked", "thesis", "entry_criteria"]),
    );
    expect(draftNextAction(incomplete)).toMatch(/missing checklist/i);

    const ready = { ...incomplete, is_ready_for_validation: true, missing_checklist_items: [] };
    expect(draftNextAction(ready)).toMatch(/QUEUE_PAPER_VALIDATION_CANDIDATE/);
  });

  it("reflects candidate review state in next action", () => {
    const base: PaperValidationCandidateItem = {
      candidate_id: "c1",
      draft_id: "d1",
      source_alert_id: "a1",
      checklist_snapshot: checklist,
      risk_mode: "conservative",
      candidate_status: "queued",
      created_at: "2026-07-26T11:00:00.000Z",
    };
    expect(candidateNextAction(base)).toMatch(/reviewing/i);
    expect(candidateNextAction({ ...base, candidate_status: "reviewing" })).toMatch(
      /CREATE_PAPER_VALIDATION_RUN_PLAN/,
    );
  });

  it("surfaces incomplete or contradictory run-plan criteria without correcting them", () => {
    const broken: PaperValidationRunPlanItem = {
      plan_id: "p1",
      candidate_id: "c1",
      draft_id: "d1",
      source_alert_id: "a1",
      checklist_snapshot: checklist,
      risk_mode: "conservative",
      plan_status: "planned",
      planned_success_criteria: "same",
      planned_failure_criteria: "same",
      created_at: "2026-07-26T12:00:00.000Z",
    };
    const issues = runPlanCriteriaIssues(broken);
    expect(issues).toEqual(
      expect.arrayContaining([
        "Entry criteria missing",
        "Success and failure criteria are identical",
      ]),
    );
    expect(runPlanNextAction(broken)).toMatch(/Revise incomplete/i);
  });

  it("describes active session next action", () => {
    const running: PaperValidationRunSessionItem = {
      session_id: "s1",
      run_plan_id: "p1",
      candidate_id: "c1",
      draft_id: "d1",
      source_alert_id: "a1",
      risk_mode: "conservative",
      session_status: "running",
      created_at: "2026-07-26T13:00:00.000Z",
      started_at: "2026-07-26T13:00:00.000Z",
    };
    expect(runSessionNextAction(running)).toMatch(/Record observations/i);
  });

  it("does not invent MFE/MAE values", () => {
    expect(excursionAvailabilityLabel()).toMatch(/unavailable/i);
    expect(excursionAvailabilityLabel()).toMatch(/not provided/i);
  });

  it("distinguishes unavailable outcomes from confirmed not recorded", () => {
    const recorded: PaperValidationSessionResultItem = {
      result_id: "r1",
      run_session_id: "s1",
      run_plan_id: "p1",
      outcome: "missed_entry",
      success_criteria_met: "not_met",
      failure_criteria_met: "met",
      invalidation_hit: false,
      entry_assessment: "missed_entry",
      discipline_assessment: "should_have_waited",
      recorded_at: "2026-07-26T14:00:00.000Z",
      created_at: "2026-07-26T14:00:00.000Z",
    };
    expect(outcomeStatusLabel(recorded)).toBe("missed entry");
    expect(
      outcomeStatusLabel(null, { resultAvailable: false, resultNotRecorded: false }),
    ).toBe("Outcome source unavailable");
    expect(
      outcomeStatusLabel(null, { resultAvailable: true, resultNotRecorded: true }),
    ).toBe("Outcome not recorded");
    expect(outcomeStatusLabel(null, { resultState: "loading" })).toBe("Loading outcome…");
    expect(outcomeStatusLabel(null, { resultState: "unavailable" })).toBe(
      "Outcome source unavailable",
    );
    expect(outcomeStatusLabel(null, { resultState: "confirmed_not_recorded" })).toBe(
      "Outcome not recorded",
    );
  });
});
