import { relatedValidationHref } from "@/components/journal/journalContext";
import type { LessonCandidate } from "@/lib/api/types";

export type LessonRelationshipLink = {
  kind: "journal" | "strategy" | "validation_session" | "trade_reference";
  label: string;
  href: string | null;
  unavailableReason?: string;
};

export function formatSourceType(sourceType: string): string {
  return sourceType.replace(/_/g, " ");
}

export function formatMistakeType(mistakeType: string): string {
  return mistakeType.replace(/_/g, " ");
}

export function formatLessonTimestamp(value: string | null | undefined): string | null {
  if (!value || !Number.isFinite(Date.parse(value))) {
    return null;
  }
  return new Date(value).toLocaleString();
}

export function requiresAttention(lesson: LessonCandidate): boolean {
  return lesson.status === "pending_review";
}

export function nextActionForLesson(lesson: LessonCandidate): {
  label: string;
  description: string;
} {
  if (lesson.status === "pending_review") {
    return {
      label: "Review required",
      description:
        "Accept to store as reviewed trading memory, or reject to keep as audit-only context. No automatic promotion.",
    };
  }
  if (lesson.status === "accepted") {
    return {
      label: "Accepted memory",
      description: "This lesson is stored as reviewed trading memory. No further review action is required.",
    };
  }
  if (lesson.status === "rejected") {
    return {
      label: "Rejected context",
      description: "This lesson was archived as learning context only and does not affect strategies.",
    };
  }
  if (lesson.status === "archived") {
    return {
      label: "Archived",
      description: "Historical retention without an active review queue action.",
    };
  }
  return {
    label: "Status unavailable",
    description: `Stored status "${lesson.status}" has no configured review action on this hub.`,
  };
}

function firstValidationSessionId(lesson: LessonCandidate): string | null {
  const metadata = lesson.analysis_metadata;
  if (!metadata || typeof metadata !== "object") return null;
  const sessionIds = metadata.source_session_ids;
  if (!Array.isArray(sessionIds) || sessionIds.length === 0) return null;
  const first = sessionIds[0];
  return typeof first === "string" && first.trim() ? first.trim() : null;
}

/** Resolve only relationships backed by stored lesson fields or known metadata keys. */
export function resolveLessonRelationships(lesson: LessonCandidate): LessonRelationshipLink[] {
  const links: LessonRelationshipLink[] = [];

  if (lesson.related_journal_entry_id) {
    links.push({
      kind: "journal",
      label: "Journal entry",
      href: `/journal?entry=${encodeURIComponent(lesson.related_journal_entry_id)}`,
    });
  } else {
    links.push({
      kind: "journal",
      label: "Journal entry",
      href: null,
      unavailableReason: "No related_journal_entry_id stored on this lesson.",
    });
  }

  const validationSessionId = firstValidationSessionId(lesson);
  if (validationSessionId) {
    links.push({
      kind: "validation_session",
      label: "Validation session",
      href: relatedValidationHref(validationSessionId),
    });
  } else if (lesson.source_type === "coaching") {
    links.push({
      kind: "validation_session",
      label: "Validation session",
      href: null,
      unavailableReason: "Coaching metadata did not include source_session_ids.",
    });
  }

  if (lesson.related_strategy_id) {
    links.push({
      kind: "strategy",
      label: "Strategy",
      href: `/strategy-lab/${encodeURIComponent(lesson.related_strategy_id)}`,
    });
  }

  if (lesson.related_trade_id) {
    links.push({
      kind: "trade_reference",
      label: "Related trade reference",
      href: null,
      unavailableReason:
        "related_trade_id is stored for audit only — it is not treated as a journal-entry link on this hub.",
    });
  }

  return links;
}

export function filterLessonsBySource(
  lessons: LessonCandidate[],
  sourceFilter: "all" | "coaching",
): LessonCandidate[] {
  if (sourceFilter === "coaching") {
    return lessons.filter((lesson) => lesson.source_type === "coaching");
  }
  return lessons;
}

export function latestLessonTimestamp(lessons: LessonCandidate[]): string | null {
  let latest: string | null = null;
  for (const lesson of lessons) {
    for (const candidate of [lesson.reviewed_at, lesson.created_at]) {
      if (!candidate || !Number.isFinite(Date.parse(candidate))) continue;
      if (!latest || Date.parse(candidate) > Date.parse(latest)) {
        latest = candidate;
      }
    }
  }
  return latest;
}
