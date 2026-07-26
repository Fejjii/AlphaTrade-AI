import { describe, expect, it } from "vitest";

import { failedSource, okSource } from "@/components/workflows/sourceResult";
import { buildValidationPipeline } from "@/components/validate/buildValidationPipeline";
import type { RecentResultLoad } from "@/components/validate/sessionExtras";
import { VALIDATION_STAGE_ORDER } from "@/components/validate/types";
import type {
  PaperValidationCandidateItem,
  PaperValidationDraftItem,
  PaperValidationRunPlanItem,
  PaperValidationRunSessionItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";

const checklist = {
  trend_checked: true,
  support_resistance_checked: true,
  volume_checked: true,
  risk_reward_checked: true,
  invalidation_checked: true,
  higher_timeframe_checked: true,
  news_or_funding_checked: false,
};

function draft(overrides: Partial<PaperValidationDraftItem> = {}): PaperValidationDraftItem {
  return {
    draft_id: "draft-1",
    source_alert_id: "alert-1",
    symbol: "BTCUSDT",
    timeframe: "15m",
    condition: "order_block",
    direction: "long",
    confidence: 0.8,
    risk_mode: "conservative",
    status: "draft",
    created_at: "2026-07-26T10:00:00.000Z",
    prep_status: "ready_for_validation",
    checklist,
    prep_completion_score: 90,
    missing_checklist_items: [],
    is_ready_for_validation: true,
    thesis: "Thesis",
    entry_criteria: "Entry",
    invalidation_criteria: "Invalidation",
    ...overrides,
  };
}

function candidate(
  overrides: Partial<PaperValidationCandidateItem> = {},
): PaperValidationCandidateItem {
  return {
    candidate_id: "cand-1",
    draft_id: "draft-1",
    source_alert_id: "alert-1",
    symbol: "BTCUSDT",
    timeframe: "15m",
    condition: "order_block",
    direction: "long",
    confidence: 0.8,
    checklist_snapshot: checklist,
    risk_mode: "conservative",
    candidate_status: "reviewing",
    created_at: "2026-07-26T11:00:00.000Z",
    ...overrides,
  };
}

function plan(overrides: Partial<PaperValidationRunPlanItem> = {}): PaperValidationRunPlanItem {
  return {
    plan_id: "plan-1",
    candidate_id: "cand-1",
    draft_id: "draft-1",
    source_alert_id: "alert-1",
    symbol: "BTCUSDT",
    timeframe: "15m",
    condition: "order_block",
    direction: "long",
    checklist_snapshot: checklist,
    risk_mode: "conservative",
    plan_status: "planned",
    validation_window: "intraday",
    observation_timeframe: "1h",
    max_duration_minutes: 240,
    planned_entry_rule: "Enter near trigger",
    planned_invalidation_rule: "Invalidate below level",
    planned_success_criteria: "Target hit",
    planned_failure_criteria: "Invalidation hit",
    created_at: "2026-07-26T12:00:00.000Z",
    ...overrides,
  };
}

function session(
  overrides: Partial<PaperValidationRunSessionItem> = {},
): PaperValidationRunSessionItem {
  return {
    session_id: "sess-1",
    run_plan_id: "plan-1",
    candidate_id: "cand-1",
    draft_id: "draft-1",
    source_alert_id: "alert-1",
    symbol: "BTCUSDT",
    timeframe: "15m",
    condition: "order_block",
    direction: "long",
    risk_mode: "conservative",
    session_status: "running",
    started_at: "2026-07-26T13:00:00.000Z",
    created_at: "2026-07-26T13:00:00.000Z",
    ...overrides,
  };
}

function list<T>(items: T[]) {
  return { items, total: items.length, limit: 50, offset: 0 };
}

function recentResult(
  sessionId: string,
  overrides: Partial<RecentResultLoad> = {},
): RecentResultLoad {
  return {
    sessionId,
    data: null,
    available: true,
    error: null,
    fallbackUsed: false,
    resultNotRecorded: false,
    ...overrides,
  };
}

function loadedResult(sessionId: string, resultItem: PaperValidationSessionResultItem): RecentResultLoad {
  return recentResult(sessionId, {
    data: resultItem,
    available: true,
    resultNotRecorded: false,
  });
}

describe("buildValidationPipeline", () => {
  it("preserves correct stage order", () => {
    const model = buildValidationPipeline({
      drafts: okSource(list([draft()])),
      candidates: okSource(list([candidate()])),
      runPlans: okSource(list([plan()])),
      runSessions: okSource(list([session()])),
      recentResults: [],
    });
    expect(model.stages.map((s) => s.id)).toEqual([...VALIDATION_STAGE_ORDER]);
  });

  it("reports honest pipeline counts", () => {
    const completedResult: PaperValidationSessionResultItem = {
      result_id: "res-2",
      run_session_id: "sess-2",
      run_plan_id: "plan-1",
      outcome: "success",
      success_criteria_met: "met",
      failure_criteria_met: "not_met",
      invalidation_hit: false,
      entry_assessment: "entered_as_planned",
      discipline_assessment: "disciplined",
      recorded_at: "2026-07-26T14:00:00.000Z",
      created_at: "2026-07-26T14:00:00.000Z",
    };
    const model = buildValidationPipeline({
      drafts: okSource(list([draft(), draft({ draft_id: "draft-2", is_ready_for_validation: false })])),
      candidates: okSource(list([candidate()])),
      runPlans: okSource(list([plan()])),
      runSessions: okSource(list([session(), session({ session_id: "sess-2", session_status: "completed" })])),
      recentResults: [loadedResult("sess-2", completedResult)],
    });
    expect(model.counts.draft).toBe(2);
    expect(model.counts.candidate).toBe(1);
    expect(model.counts.run_plan).toBe(1);
    expect(model.counts.run_session).toBe(2);
    expect(model.counts.observation).toBe(1);
    expect(model.counts.outcome).toBe(1);
    expect(model.outcomeCoverage).toEqual({
      completedSessionsProbed: 1,
      resultsLoaded: 1,
      resultsUnavailable: 0,
      resultsNotRecorded: 0,
    });
  });

  it("keeps unavailable counts null under partial source availability", () => {
    const model = buildValidationPipeline({
      drafts: okSource(list([draft()])),
      candidates: failedSource("down"),
      runPlans: okSource(list([plan()])),
      runSessions: failedSource("down"),
      recentResults: [],
    });
    expect(model.counts.draft).toBe(1);
    expect(model.counts.candidate).toBeNull();
    expect(model.counts.run_plan).toBe(1);
    expect(model.counts.run_session).toBeNull();
    expect(model.counts.observation).toBeNull();
    expect(model.counts.outcome).toBeNull();
    expect(model.stages.find((s) => s.id === "candidate")?.available).toBe(false);
  });

  it("does not invent zeros when all sources are unavailable", () => {
    const model = buildValidationPipeline({
      drafts: failedSource("down"),
      candidates: failedSource("down"),
      runPlans: failedSource("down"),
      runSessions: failedSource("down"),
      recentResults: [],
    });
    for (const stage of model.stages) {
      expect(stage.count).toBeNull();
      expect(stage.statusLabel).toMatch(/unavailable/i);
    }
    expect(model.attention).toEqual([]);
    expect(model.activeSessions).toEqual([]);
  });

  it("builds attention for ready drafts and active sessions", () => {
    const model = buildValidationPipeline({
      drafts: okSource(list([draft()])),
      candidates: okSource(list([candidate({ candidate_status: "queued" })])),
      runPlans: okSource(list([plan()])),
      runSessions: okSource(list([session()])),
      recentResults: [],
    });
    expect(model.attention.some((item) => item.id.includes("draft-ready"))).toBe(true);
    expect(model.attention.some((item) => item.id.includes("session-running"))).toBe(true);
    expect(model.activeSessions).toHaveLength(1);
  });

  it("summarizes recent outcomes without inventing result payloads", () => {
    const completed = session({ session_id: "sess-done", session_status: "completed" });
    const result: PaperValidationSessionResultItem = {
      result_id: "res-1",
      run_session_id: "sess-done",
      run_plan_id: "plan-1",
      outcome: "success",
      success_criteria_met: "met",
      failure_criteria_met: "not_met",
      invalidation_hit: false,
      entry_assessment: "entered_as_planned",
      discipline_assessment: "disciplined",
      recorded_at: "2026-07-26T14:00:00.000Z",
      created_at: "2026-07-26T14:00:00.000Z",
    };
    const model = buildValidationPipeline({
      drafts: okSource(list([])),
      candidates: okSource(list([])),
      runPlans: okSource(list([])),
      runSessions: okSource(list([completed])),
      recentResults: [loadedResult("sess-done", result)],
    });
    expect(model.recentOutcomes).toHaveLength(1);
    expect(model.recentOutcomes[0]?.outcome).toBe("success");
    expect(model.recentOutcomes[0]?.href).toBe("/paper-validation/run-sessions/sess-done");
  });

  it("never shows outcome count 0 when all result probes failed", () => {
    const completed = Array.from({ length: 5 }, (_, i) =>
      session({ session_id: `sess-${i}`, session_status: "completed" }),
    );
    const recentResults = completed.map((item) =>
      recentResult(item.session_id, {
        available: false,
        error: "down",
        resultNotRecorded: false,
      }),
    );
    const model = buildValidationPipeline({
      drafts: okSource(list([])),
      candidates: okSource(list([])),
      runPlans: okSource(list([])),
      runSessions: okSource(list(completed)),
      recentResults,
    });
    expect(model.counts.outcome).toBeNull();
    expect(model.stages.find((s) => s.id === "outcome")?.statusLabel).toMatch(
      /Outcome results unavailable/i,
    );
    expect(model.outcomeCoverage.resultsUnavailable).toBe(5);
  });

  it("shows partial outcome coverage when some result probes fail", () => {
    const completed = Array.from({ length: 5 }, (_, i) =>
      session({ session_id: `sess-${i}`, session_status: "completed" }),
    );
    const resultItem: PaperValidationSessionResultItem = {
      result_id: "res-1",
      run_session_id: "sess-0",
      run_plan_id: "plan-1",
      outcome: "success",
      success_criteria_met: "met",
      failure_criteria_met: "not_met",
      invalidation_hit: false,
      entry_assessment: "entered_as_planned",
      discipline_assessment: "disciplined",
      recorded_at: "2026-07-26T14:00:00.000Z",
      created_at: "2026-07-26T14:00:00.000Z",
    };
    const recentResults: RecentResultLoad[] = [
      loadedResult("sess-0", resultItem),
      loadedResult("sess-1", { ...resultItem, result_id: "res-2", run_session_id: "sess-1" }),
      loadedResult("sess-2", { ...resultItem, result_id: "res-3", run_session_id: "sess-2" }),
      recentResult("sess-3", { available: false, error: "down" }),
      recentResult("sess-4", { available: false, error: "down" }),
    ];
    const model = buildValidationPipeline({
      drafts: okSource(list([])),
      candidates: okSource(list([])),
      runPlans: okSource(list([])),
      runSessions: okSource(list(completed)),
      recentResults,
    });
    expect(model.counts.outcome).toBe(3);
    expect(model.stages.find((s) => s.id === "outcome")?.statusLabel).toBe(
      "3 of 5 recent outcomes loaded",
    );
    expect(model.limitations.some((item) => /unavailable/i.test(item))).toBe(true);
  });

  it("labels confirmed missing outcomes as not recorded", () => {
    const completed = session({ session_id: "sess-done", session_status: "completed" });
    const model = buildValidationPipeline({
      drafts: okSource(list([])),
      candidates: okSource(list([])),
      runPlans: okSource(list([])),
      runSessions: okSource(list([completed])),
      recentResults: [
        recentResult("sess-done", { available: true, resultNotRecorded: true, data: null }),
      ],
    });
    expect(model.counts.outcome).toBe(0);
    expect(model.recentOutcomes[0]?.resultNotRecorded).toBe(true);
    expect(model.outcomeCoverage.resultsNotRecorded).toBe(1);
  });

  it("keeps outcome count 0 when there are no completed sessions", () => {
    const model = buildValidationPipeline({
      drafts: okSource(list([])),
      candidates: okSource(list([])),
      runPlans: okSource(list([])),
      runSessions: okSource(list([session()])),
      recentResults: [],
    });
    expect(model.counts.outcome).toBe(0);
    expect(model.stages.find((s) => s.id === "outcome")?.statusLabel).toMatch(
      /No completed sessions/i,
    );
  });

  it("marks outcome unavailable when run-session source is unavailable", () => {
    const model = buildValidationPipeline({
      drafts: okSource(list([])),
      candidates: okSource(list([])),
      runPlans: okSource(list([])),
      runSessions: failedSource("down"),
      recentResults: [],
    });
    expect(model.counts.outcome).toBeNull();
    expect(model.stages.find((s) => s.id === "outcome")?.available).toBe(false);
  });
});
