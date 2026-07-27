import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

import { filterLessonsBySource } from "@/components/lessons/lessonDisplay";
import {
  coverageFromPage,
  reviewedCoverageMessage,
  type SourceCoverage,
} from "@/components/lessons/lessonCoverage";

export type RecentReviewedStatus =
  | "loading"
  | "unavailable"
  | "partial_failure"
  | "partial_truncated"
  | "empty"
  | "available"
  | "filtered_empty"
  | "truncated_empty";

export type RecentReviewedResult = {
  status: RecentReviewedStatus;
  items: LessonCandidate[] | null;
  acceptedAvailable: boolean;
  rejectedAvailable: boolean;
  acceptedFailed: boolean;
  rejectedFailed: boolean;
  acceptedCoverage: SourceCoverage | null;
  rejectedCoverage: SourceCoverage | null;
  coverageMessage: string | null;
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

function pageCoverage(
  source: SourceResult<PaginatedLessonCandidates> | undefined,
): SourceCoverage | null {
  if (!source?.available || !source.data) return null;
  return coverageFromPage(source.data.items.length, source.data.total);
}

export function buildRecentReviewedLessons(input: BuildRecentInput): RecentReviewedResult {
  const limit = input.limit ?? 12;

  if (input.loading && !input.accepted && !input.rejected) {
    return {
      status: "loading",
      items: null,
      acceptedAvailable: false,
      rejectedAvailable: false,
      acceptedFailed: false,
      rejectedFailed: false,
      acceptedCoverage: null,
      rejectedCoverage: null,
      coverageMessage: null,
    };
  }

  const acceptedAvailable = Boolean(input.accepted?.available);
  const rejectedAvailable = Boolean(input.rejected?.available);
  const acceptedFailed = Boolean(input.accepted && !input.accepted.available);
  const rejectedFailed = Boolean(input.rejected && !input.rejected.available);
  const acceptedCoverage = pageCoverage(input.accepted);
  const rejectedCoverage = pageCoverage(input.rejected);

  if (!acceptedAvailable && !rejectedAvailable) {
    return {
      status: "unavailable",
      items: null,
      acceptedAvailable: false,
      rejectedAvailable: false,
      acceptedFailed,
      rejectedFailed,
      acceptedCoverage: null,
      rejectedCoverage: null,
      coverageMessage: null,
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

  const truncationMessages: string[] = [];
  if (acceptedAvailable && acceptedCoverage === "truncated" && input.accepted?.data) {
    truncationMessages.push(
      reviewedCoverageMessage(
        "Accepted",
        input.accepted.data.items.length,
        input.accepted.data.total,
      ),
    );
  }
  if (rejectedAvailable && rejectedCoverage === "truncated" && input.rejected?.data) {
    truncationMessages.push(
      reviewedCoverageMessage(
        "Rejected",
        input.rejected.data.items.length,
        input.rejected.data.total,
      ),
    );
  }
  const coverageMessage = truncationMessages.length > 0 ? truncationMessages.join(" ") : null;

  const acceptedCompleteEmpty =
    acceptedAvailable &&
    acceptedCoverage === "complete" &&
    (input.accepted?.data?.items.length ?? 0) === 0;
  const rejectedCompleteEmpty =
    rejectedAvailable &&
    rejectedCoverage === "complete" &&
    (input.rejected?.data?.items.length ?? 0) === 0;
  const historyDefinitivelyEmpty = acceptedCompleteEmpty && rejectedCompleteEmpty;

  const anyTruncatedWithMore =
    (acceptedAvailable &&
      acceptedCoverage === "truncated" &&
      (input.accepted?.data?.total ?? 0) > 0) ||
    (rejectedAvailable &&
      rejectedCoverage === "truncated" &&
      (input.rejected?.data?.total ?? 0) > 0);

  if (filtered.length === 0) {
    if (historyDefinitivelyEmpty) {
      return {
        status: "empty",
        items: [],
        acceptedAvailable,
        rejectedAvailable,
        acceptedFailed,
        rejectedFailed,
        acceptedCoverage,
        rejectedCoverage,
        coverageMessage,
      };
    }

    if (anyTruncatedWithMore) {
      return {
        status: "truncated_empty",
        items: [],
        acceptedAvailable,
        rejectedAvailable,
        acceptedFailed,
        rejectedFailed,
        acceptedCoverage,
        rejectedCoverage,
        coverageMessage,
      };
    }

    if (input.sourceFilter === "coaching") {
      return {
        status: "filtered_empty",
        items: [],
        acceptedAvailable,
        rejectedAvailable,
        acceptedFailed,
        rejectedFailed,
        acceptedCoverage,
        rejectedCoverage,
        coverageMessage,
      };
    }

    if (acceptedFailed || rejectedFailed) {
      return {
        status: "partial_failure",
        items: [],
        acceptedAvailable,
        rejectedAvailable,
        acceptedFailed,
        rejectedFailed,
        acceptedCoverage,
        rejectedCoverage,
        coverageMessage,
      };
    }
  }

  const hasTruncation = acceptedCoverage === "truncated" || rejectedCoverage === "truncated";
  const hasFailure = acceptedFailed || rejectedFailed;

  let status: RecentReviewedStatus = "available";
  if (hasFailure) {
    status = "partial_failure";
  } else if (hasTruncation) {
    status = "partial_truncated";
  }

  if (filtered.length === 0 && input.sourceFilter === "coaching") {
    status = "filtered_empty";
  }

  return {
    status,
    items: filtered,
    acceptedAvailable,
    rejectedAvailable,
    acceptedFailed,
    rejectedFailed,
    acceptedCoverage,
    rejectedCoverage,
    coverageMessage,
  };
}
