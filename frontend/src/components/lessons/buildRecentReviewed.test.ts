import { describe, expect, it } from "vitest";

import { buildRecentReviewedLessons } from "@/components/lessons/buildRecentReviewed";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

function ok(data: PaginatedLessonCandidates): SourceResult<PaginatedLessonCandidates> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed(error = "down"): SourceResult<PaginatedLessonCandidates> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function lesson(overrides: Partial<LessonCandidate> & { id: string; status: string }): LessonCandidate {
  return {
    organization_id: "org",
    user_id: "user",
    source_type: "journal",
    lesson_text: "Test lesson",
    mistake_type: "early_exit",
    severity: "medium",
    created_at: "2026-07-20T10:00:00.000Z",
    ...overrides,
  };
}

describe("buildRecentReviewedLessons", () => {
  it("merges accepted and rejected history sorted by reviewed_at", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({
        items: [
          lesson({
            id: "a1",
            status: "accepted",
            reviewed_at: "2026-07-21T10:00:00.000Z",
          }),
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      rejected: ok({
        items: [
          lesson({
            id: "r1",
            status: "rejected",
            reviewed_at: "2026-07-22T10:00:00.000Z",
          }),
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.status).toBe("available");
    expect(result.items?.map((item) => item.id)).toEqual(["r1", "a1"]);
  });

  it("keeps partial history when one source fails", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({
        items: [lesson({ id: "a1", status: "accepted" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      rejected: failed("rejected down"),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.status).toBe("partial");
    expect(result.items).toHaveLength(1);
  });
});
