import { describe, expect, it } from "vitest";

import { buildLessonsAttentionQueue } from "@/components/lessons/buildLessonsAttention";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

function ok(data: PaginatedLessonCandidates): SourceResult<PaginatedLessonCandidates> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed(error = "down"): SourceResult<PaginatedLessonCandidates> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function lesson(overrides: Partial<LessonCandidate> & { id: string }): LessonCandidate {
  return {
    organization_id: "org",
    user_id: "user",
    source_type: "journal",
    lesson_text: "Test lesson",
    mistake_type: "early_exit",
    severity: "medium",
    status: "pending_review",
    created_at: "2026-07-20T10:00:00.000Z",
    ...overrides,
  };
}

describe("buildLessonsAttentionQueue", () => {
  it("classifies pending_review lessons as attention items", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({
        items: [lesson({ id: "l1" }), lesson({ id: "l2", status: "rejected" })],
        total: 2,
        limit: 50,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.queueStatus).toBe("available");
    expect(result.items).toHaveLength(1);
    expect(result.countDefinitive).toBe(true);
  });

  it("does not treat failed pending source as empty", () => {
    const result = buildLessonsAttentionQueue({
      pending: failed("pending down"),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.queueStatus).toBe("unavailable");
    expect(result.items).toBeNull();
    expect(result.countDefinitive).toBe(false);
  });
});
