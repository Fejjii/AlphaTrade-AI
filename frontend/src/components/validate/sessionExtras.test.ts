import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  loadObservationsSource,
  loadRecentSessionResults,
  loadSessionResultSource,
  summarizeOutcomeCoverage,
} from "@/components/validate/sessionExtras";
import type { PaperValidationSessionResultItem } from "@/lib/api/types";

function result(
  overrides: Partial<PaperValidationSessionResultItem> = {},
): PaperValidationSessionResultItem {
  return {
    result_id: "res-1",
    run_session_id: "sess-1",
    run_plan_id: "plan-1",
    outcome: "success",
    success_criteria_met: "met",
    failure_criteria_met: "not_met",
    invalidation_hit: false,
    entry_assessment: "entered_as_planned",
    discipline_assessment: "disciplined",
    recorded_at: "2026-07-26T14:00:00.000Z",
    created_at: "2026-07-26T14:00:00.000Z",
    ...overrides,
  };
}

describe("sessionExtras", () => {
  it("treats 404 ApiError as confirmed not recorded", async () => {
    const source = await loadSessionResultSource(
      Promise.reject(new ApiError("Session result not found.", 404, {})),
    );
    expect(source.available).toBe(true);
    expect(source.resultNotRecorded).toBe(true);
    expect(source.data).toBeNull();
    expect(source.error).toBeNull();
  });

  it("treats non-404 failures as unavailable, not as not recorded", async () => {
    const source = await loadSessionResultSource(
      Promise.reject(new ApiError("boom", 500, {})),
    );
    expect(source.available).toBe(false);
    expect(source.resultNotRecorded).toBe(false);
    expect(source.data).toBeNull();
    expect(source.error).toMatch(/boom/i);
  });

  it("does not treat generic Error as not recorded", async () => {
    const source = await loadSessionResultSource(Promise.reject(new Error("not found")));
    expect(source.available).toBe(false);
    expect(source.resultNotRecorded).toBe(false);
  });

  it("loads a recorded result", async () => {
    const source = await loadSessionResultSource(Promise.resolve(result()));
    expect(source.available).toBe(true);
    expect(source.resultNotRecorded).toBe(false);
    expect(source.data?.outcome).toBe("success");
  });

  it("preserves observation failures as unavailable", async () => {
    const source = await loadObservationsSource(Promise.reject(new Error("obs down")));
    expect(source.available).toBe(false);
    expect(source.data).toBeNull();
    expect(source.error).toMatch(/obs down/i);
  });

  it("summarizes five completed sessions with five loaded results", async () => {
    const sessions = Array.from({ length: 5 }, (_, i) => ({
      session_id: `sess-${i}`,
      session_status: "completed",
    }));
    const fetchResult = vi.fn(async (id: string) => result({ run_session_id: id, result_id: id }));
    const recent = await loadRecentSessionResults(sessions, fetchResult, 5);
    expect(recent).toHaveLength(5);
    expect(summarizeOutcomeCoverage(recent)).toEqual({
      completedSessionsProbed: 5,
      resultsLoaded: 5,
      resultsUnavailable: 0,
      resultsNotRecorded: 0,
    });
  });

  it("summarizes three loaded and two failed result requests", async () => {
    const sessions = Array.from({ length: 5 }, (_, i) => ({
      session_id: `sess-${i}`,
      session_status: "completed",
    }));
    const fetchResult = vi.fn(async (id: string) => {
      if (id === "sess-3" || id === "sess-4") {
        throw new ApiError("down", 503, {});
      }
      return result({ run_session_id: id, result_id: id });
    });
    const recent = await loadRecentSessionResults(sessions, fetchResult, 5);
    expect(summarizeOutcomeCoverage(recent)).toEqual({
      completedSessionsProbed: 5,
      resultsLoaded: 3,
      resultsUnavailable: 2,
      resultsNotRecorded: 0,
    });
  });

  it("summarizes all result requests failed", async () => {
    const sessions = Array.from({ length: 5 }, (_, i) => ({
      session_id: `sess-${i}`,
      session_status: "completed",
    }));
    const fetchResult = vi.fn(async () => {
      throw new Error("down");
    });
    const recent = await loadRecentSessionResults(sessions, fetchResult, 5);
    expect(summarizeOutcomeCoverage(recent)).toEqual({
      completedSessionsProbed: 5,
      resultsLoaded: 0,
      resultsUnavailable: 5,
      resultsNotRecorded: 0,
    });
  });

  it("summarizes confirmed no result for a completed session", async () => {
    const recent = await loadRecentSessionResults(
      [{ session_id: "sess-1", session_status: "completed" }],
      async () => {
        throw new ApiError("Session result not found.", 404, {});
      },
    );
    expect(summarizeOutcomeCoverage(recent)).toEqual({
      completedSessionsProbed: 1,
      resultsLoaded: 0,
      resultsUnavailable: 0,
      resultsNotRecorded: 1,
    });
  });

  it("summarizes no completed sessions as empty coverage", async () => {
    const recent = await loadRecentSessionResults(
      [{ session_id: "sess-1", session_status: "running" }],
      async () => result(),
    );
    expect(recent).toEqual([]);
    expect(summarizeOutcomeCoverage(recent)).toEqual({
      completedSessionsProbed: 0,
      resultsLoaded: 0,
      resultsUnavailable: 0,
      resultsNotRecorded: 0,
    });
  });
});
