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
  it("marks complete pending page as definitive", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({
        items: [lesson({ id: "l1" })],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.coverage).toBe("complete");
    expect(result.countDefinitive).toBe(true);
    expect(result.queueStatus).toBe("available");
  });

  it("marks truncated pending page as non-definitive with coverage message", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({
        items: [lesson({ id: "l1" })],
        total: 5,
        limit: 1,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.coverage).toBe("truncated");
    expect(result.countDefinitive).toBe(false);
    expect(result.countAvailable).toBe(true);
    expect(result.totalPendingCount).toBe(5);
    expect(result.coverageMessage).toMatch(/only 1 of 5 pending lessons/i);
  });

  it("allows definitive empty only when coverage is complete", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({ items: [], total: 0, limit: 50, offset: 0 }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.queueStatus).toBe("empty");
    expect(result.countDefinitive).toBe(true);
  });

  it("does not claim empty when truncated page has zero loaded but nonzero total", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({ items: [], total: 3, limit: 1, offset: 0 }),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.queueStatus).toBe("truncated_empty");
    expect(result.countDefinitive).toBe(false);
  });

  it("uses coaching-specific truncated empty wording", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({
        items: [lesson({ id: "l-journal", source_type: "journal" })],
        total: 4,
        limit: 1,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "coaching",
    });
    expect(result.queueStatus).toBe("truncated_filtered_empty");
  });

  it("does not treat failed pending source as empty", () => {
    const result = buildLessonsAttentionQueue({
      pending: failed("pending down"),
      loading: false,
      sourceFilter: "all",
    });
    expect(result.queueStatus).toBe("unavailable");
    expect(result.countDefinitive).toBe(false);
  });

  it("tracks filteredLoadedCount separately from loadedPendingCount", () => {
    const result = buildLessonsAttentionQueue({
      pending: ok({
        items: [
          lesson({ id: "l-coach", source_type: "coaching" }),
          lesson({ id: "l-journal", source_type: "journal" }),
        ],
        total: 100,
        limit: 50,
        offset: 0,
      }),
      loading: false,
      sourceFilter: "coaching",
    });
    expect(result.loadedPendingCount).toBe(2);
    expect(result.filteredLoadedCount).toBe(1);
    expect(result.totalPendingCount).toBe(100);
  });
});
