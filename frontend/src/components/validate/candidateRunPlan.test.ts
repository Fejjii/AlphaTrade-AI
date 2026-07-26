import { describe, expect, it } from "vitest";

import {
  buildCandidateRunPlanMap,
  selectRunPlanForCandidate,
} from "@/components/validate/candidateRunPlan";
import type { PaperValidationRunPlanItem } from "@/lib/api/types";

const checklist = {
  trend_checked: true,
  support_resistance_checked: true,
  volume_checked: true,
  risk_reward_checked: true,
  invalidation_checked: true,
  higher_timeframe_checked: true,
  news_or_funding_checked: true,
};

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
    planned_entry_rule: "Enter",
    planned_invalidation_rule: "Invalidate",
    planned_success_criteria: "Success",
    planned_failure_criteria: "Failure",
    created_at: "2026-07-26T12:00:00.000Z",
    ...overrides,
  };
}

describe("candidateRunPlan", () => {
  it("selects one active plan", () => {
    const relation = selectRunPlanForCandidate("cand-1", true, [
      plan({ plan_id: "active-1", plan_status: "planned" }),
    ]);
    expect(relation).toMatchObject({ kind: "active", planId: "active-1", status: "planned" });
  });

  it("selects one archived plan as historical when no active plan exists", () => {
    const relation = selectRunPlanForCandidate("cand-1", true, [
      plan({ plan_id: "arch-1", plan_status: "archived", created_at: "2026-07-20T12:00:00.000Z" }),
    ]);
    expect(relation).toMatchObject({
      kind: "historical",
      planId: "arch-1",
      status: "archived",
    });
  });

  it("prefers active over archived even when archived is newer", () => {
    const relation = selectRunPlanForCandidate("cand-1", true, [
      plan({
        plan_id: "arch-new",
        plan_status: "archived",
        created_at: "2026-07-26T18:00:00.000Z",
      }),
      plan({
        plan_id: "active-old",
        plan_status: "needs_revision",
        created_at: "2026-07-20T12:00:00.000Z",
      }),
    ]);
    expect(relation).toMatchObject({ kind: "active", planId: "active-old" });
  });

  it("picks the newest archived plan among multiple historical plans", () => {
    const relation = selectRunPlanForCandidate("cand-1", true, [
      plan({
        plan_id: "arch-old",
        plan_status: "archived",
        created_at: "2026-07-10T12:00:00.000Z",
      }),
      plan({
        plan_id: "arch-new",
        plan_status: "archived",
        created_at: "2026-07-25T12:00:00.000Z",
      }),
      plan({
        plan_id: "arch-mid",
        plan_status: "archived",
        created_at: "2026-07-20T12:00:00.000Z",
      }),
    ]);
    expect(relation).toMatchObject({ kind: "historical", planId: "arch-new" });
  });

  it("returns source_unavailable when run-plan source failed", () => {
    expect(selectRunPlanForCandidate("cand-1", false, [plan()])).toEqual({
      kind: "source_unavailable",
    });
  });

  it("returns none when no related plan exists", () => {
    expect(
      selectRunPlanForCandidate("cand-1", true, [
        plan({ candidate_id: "other", plan_id: "plan-x" }),
      ]),
    ).toEqual({ kind: "none" });
  });

  it("builds a map for candidate ids", () => {
    const map = buildCandidateRunPlanMap(
      true,
      [plan({ plan_id: "p1", candidate_id: "cand-1" })],
      ["cand-1", "cand-2"],
    );
    expect(map.get("cand-1")).toMatchObject({ kind: "active", planId: "p1" });
    expect(map.get("cand-2")).toEqual({ kind: "none" });
  });
});
