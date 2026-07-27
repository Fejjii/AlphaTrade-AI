import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

import { filterLessonsBySource } from "@/components/lessons/lessonDisplay";

export type RecentReviewedStatus =
  | "loading"
  | "unavailable"
  | "partial"
  | "empty"
  | "available"
  | "filtered_empty";

export type RecentReviewedResult = {
  status: RecentReviewedStatus;
  items: LessonCandidate[] | null;
  acceptedAvailable: boolean;
  rejectedAvailable: boolean;
  reasonUnavailable?: string;
};

type BuildRecentInput = {
  accepted: SourceResult<PaginatedLessonCandidates> | undefined;
  rejected: SourceResult<PaginatedLessonCandidates> | undefined;
  loading: boolean;
  sourceFilter: "all" | "coaching";
  limit?: number;
};

function reviewedSortKey(lesson: LessonCandidate): number {
  const reviewed = lesson.reviewed_at && Number.isFinite(Date.parse(lesson.reviewed_at))
    ? Date.parse(lesson.reviewed_at)
    : null;
  const created = lesson.created_at && Number.isFinite(Date.parse(lesson.created_at))
    ? Date.parse(lesson.created_at)
    : null;
  return reviewed ?? created ?? 0;
}

export function buildRecentReviewedLessons(input: BuildRecentInput): RecentReviewedResult {
  const limit = input.limit ?? 12;

  if (input.loading && !input.accepted && !input.rejected) {
    return {
      status: "loading",
      items: null,
      acceptedAvailable: false,
      rejectedAvailable: false,
    };
  }

  const acceptedAvailable = Boolean(input.accepted?.available);
  const rejectedAvailable = Boolean(input.rejected?.available);

  if (!acceptedAvailable && !rejectedAvailable) {
    return {
      status: "unavailable",
      items: null,
      acceptedAvailable: false,
      rejectedAvailable: false,
      reasonUnavailable:
        [input.accepted?.error, input.rejected?.error].filter(Boolean).join("; ") ||
        "Recently reviewed lessons are unavailable. This is not shown as an empty list.",
    };
  }

  const merged: LessonCandidate[] = [];
  if (acceptedAvailable) {
    merged.push(...(input.accepted?.data?.items ?? []));
  }
  if (rejectedAvailable) {
    merged.push(...(input.rejected?.data?.items ?? []));
  }

  const sorted = merged.sort((a, b) => reviewedSortKey(b) - reviewedSortKey(a));
  const filtered = filterLessonsBySource(sorted, input.sourceFilter).slice(0, limit);

  if (merged.length === 0) {
    return {
      status: "empty",
      items: [],
      acceptedAvailable,
      rejectedAvailable,
    };
  }

  if (filtered.length === 0) {
    return {
      status: "filtered_empty",
      items: [],
      acceptedAvailable,
      rejectedAvailable,
    };
  }

  const partial = !acceptedAvailable || !rejectedAvailable;

  return {
    status: partial ? "partial" : "available",
    items: filtered,
    acceptedAvailable,
    rejectedAvailable,
  };
}
