import type { SourceResult } from "@/components/workflows/sourceResult";
import type { LessonCandidate, PaginatedLessonCandidates } from "@/lib/api/types";

import { filterLessonsBySource, requiresAttention } from "@/components/lessons/lessonDisplay";
import {
  coverageFromPage,
  pendingCoverageMessage,
  type SourceCoverage,
} from "@/components/lessons/lessonCoverage";

export type AttentionQueueStatus =
  | "loading"
  | "unavailable"
  | "empty"
  | "available"
  | "filtered_empty"
  | "truncated_empty"
  | "truncated_filtered_empty";

export type AttentionQueueResult = {
  queueStatus: AttentionQueueStatus;
  items: LessonCandidate[] | null;
  reasonUnavailable?: string;
  countDefinitive: boolean;
  countAvailable: boolean;
  sourceAvailable: boolean;
  coverage: SourceCoverage | null;
  loadedPendingCount: number;
  totalPendingCount: number;
  filteredLoadedCount: number;
  coverageMessage: string | null;
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
      countAvailable: false,
      sourceAvailable: false,
      coverage: null,
      loadedPendingCount: 0,
      totalPendingCount: 0,
      filteredLoadedCount: 0,
      coverageMessage: null,
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
      countAvailable: false,
      sourceAvailable: false,
      coverage: null,
      loadedPendingCount: 0,
      totalPendingCount: 0,
      filteredLoadedCount: 0,
      coverageMessage: null,
    };
  }

  const page = input.pending.data;
  const loadedPendingCount = page?.items.length ?? 0;
  const totalPendingCount = page?.total ?? 0;
  const coverage = coverageFromPage(loadedPendingCount, totalPendingCount);
  const coverageMessage =
    coverage === "truncated" ? pendingCoverageMessage(loadedPendingCount, totalPendingCount) : null;

  const pendingItems = (page?.items ?? []).filter(requiresAttention);
  const filtered = filterLessonsBySource(pendingItems, input.sourceFilter);
  const filteredLoadedCount = filtered.length;
  const countDefinitive = coverage === "complete";
  const countAvailable = true;

  if (coverage === "complete" && pendingItems.length === 0) {
    return {
      queueStatus: "empty",
      items: [],
      countDefinitive: true,
      countAvailable: true,
      sourceAvailable: true,
      coverage,
      loadedPendingCount,
      totalPendingCount,
      filteredLoadedCount,
      coverageMessage: null,
    };
  }

  if (coverage === "complete" && filtered.length === 0) {
    return {
      queueStatus: "filtered_empty",
      items: [],
      countDefinitive: true,
      countAvailable: true,
      sourceAvailable: true,
      coverage,
      loadedPendingCount,
      totalPendingCount,
      filteredLoadedCount,
      coverageMessage: null,
    };
  }

  if (coverage === "truncated" && filtered.length === 0) {
    return {
      queueStatus:
        input.sourceFilter === "coaching" ? "truncated_filtered_empty" : "truncated_empty",
      items: [],
      countDefinitive: false,
      countAvailable: true,
      sourceAvailable: true,
      coverage,
      loadedPendingCount,
      totalPendingCount,
      filteredLoadedCount,
      coverageMessage,
    };
  }

  return {
    queueStatus: "available",
    items: filtered,
    countDefinitive,
    countAvailable,
    sourceAvailable: true,
    coverage,
    loadedPendingCount,
    totalPendingCount,
    filteredLoadedCount,
    coverageMessage,
  };
}
