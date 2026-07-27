import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

import { filterLessonsBySource, requiresAttention } from "@/components/lessons/lessonDisplay";

export type AttentionQueueStatus =
  | "loading"
  | "unavailable"
  | "empty"
  | "available"
  | "filtered_empty";

export type AttentionQueueResult = {
  queueStatus: AttentionQueueStatus;
  items: LessonCandidate[] | null;
  reasonUnavailable?: string;
  countDefinitive: boolean;
  sourceAvailable: boolean;
};

type BuildAttentionInput = {
  pending: SourceResult<PaginatedLessonCandidates> | undefined;
  loading: boolean;
  sourceFilter: "all" | "coaching";
};

export function buildLessonsAttentionQueue(input: BuildAttentionInput): AttentionQueueResult {
  if (input.loading && !input.pending) {
    return {
      queueStatus: "loading",
      items: null,
      countDefinitive: false,
      sourceAvailable: false,
    };
  }

  if (!input.pending?.available) {
    return {
      queueStatus: "unavailable",
      items: null,
      reasonUnavailable:
        input.pending?.error ??
        "Pending lessons are unavailable. This is not shown as an empty review queue.",
      countDefinitive: false,
      sourceAvailable: false,
    };
  }

  const pendingItems = (input.pending.data?.items ?? []).filter(requiresAttention);
  const filtered = filterLessonsBySource(pendingItems, input.sourceFilter);

  if (pendingItems.length === 0) {
    return {
      queueStatus: "empty",
      items: [],
      countDefinitive: true,
      sourceAvailable: true,
    };
  }

  if (filtered.length === 0) {
    return {
      queueStatus: "filtered_empty",
      items: [],
      countDefinitive: true,
      sourceAvailable: true,
    };
  }

  return {
    queueStatus: "available",
    items: filtered,
    countDefinitive: true,
    sourceAvailable: true,
  };
}
