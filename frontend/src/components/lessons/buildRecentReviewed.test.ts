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
  it("merges accepted and rejected history when both complete", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({
        items: [lesson({ id: "a1", status: "accepted", reviewed_at: "2026-07-21T10:00:00.000Z" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      rejected: ok({
        items: [lesson({ id: "r1", status: "rejected", reviewed_at: "2026-07-22T10:00:00.000Z" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.status).toBe("available");
    expect(result.acceptedCoverage).toBe("complete");
    expect(result.rejectedCoverage).toBe("complete");
  });

  it("marks accepted truncated independently", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({
        items: [lesson({ id: "a1", status: "accepted" })],
        total: 4,
        limit: 1,
        offset: 0,
      }),
      rejected: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.acceptedCoverage).toBe("truncated");
    expect(result.rejectedCoverage).toBe("complete");
    expect(result.status).toBe("partial_truncated");
    expect(result.coverageMessage).toMatch(/accepted history is truncated/i);
  });

  it("marks rejected truncated independently", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      rejected: ok({
        items: [lesson({ id: "r1", status: "rejected" })],
        total: 3,
        limit: 1,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.rejectedCoverage).toBe("truncated");
    expect(result.status).toBe("partial_truncated");
  });

  it("marks both reviewed sources truncated", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({
        items: [lesson({ id: "a1", status: "accepted" })],
        total: 2,
        limit: 1,
        offset: 0,
      }),
      rejected: ok({
        items: [lesson({ id: "r1", status: "rejected" })],
        total: 2,
        limit: 1,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.acceptedCoverage).toBe("truncated");
    expect(result.rejectedCoverage).toBe("truncated");
    expect(result.status).toBe("partial_truncated");
  });

  it("distinguishes source failure from truncation", () => {
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
    expect(result.status).toBe("partial_failure");
    expect(result.rejectedFailed).toBe(true);
    expect(result.rejectedCoverage).toBeNull();
  });

  it("allows definitive empty only when both sources complete and empty", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      rejected: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.status).toBe("empty");
  });

  it("does not claim empty history when truncated totals remain", () => {
    const result = buildRecentReviewedLessons({
      accepted: ok({ items: [], total: 2, limit: 1, offset: 0 }),
      rejected: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.status).toBe("truncated_empty");
  });
});
