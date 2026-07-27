import type { RagDocument } from "@/lib/api/types";

export type KnowledgeCategoryKind =
  | "accepted_lesson"
  | "strategy_or_rule"
  | "journal_derived"
  | "manually_stored"
  | "other";

export type KnowledgeRelationshipLink = {
  kind: "lesson" | "journal" | "strategy";
  label: string;
  href: string | null;
  id: string | null;
  unavailableReason?: string;
};

const JOURNAL_URI = /^journal:\/\/([^/?#]+)$/i;
const LESSON_URI = /^lesson:\/\/([^/?#]+)$/i;
const STRATEGY_URI = /^strategy:\/\/([^/?#]+)\/v\d+$/i;

export function formatSourceType(sourceType: string): string {
  return sourceType.replace(/_/g, " ");
}

export function formatKnowledgeTimestamp(value: string | null | undefined): string | null {
  if (!value || !Number.isFinite(Date.parse(value))) {
    return null;
  }
  return new Date(value).toLocaleString();
}

export function latestDocumentTimestamp(documents: RagDocument[]): string | null {
  let latest: string | null = null;
  let latestMs = Number.NEGATIVE_INFINITY;
  for (const doc of documents) {
    const raw = doc.updated_at || doc.created_at;
    if (!raw || !Number.isFinite(Date.parse(raw))) continue;
    const ms = Date.parse(raw);
    if (ms > latestMs) {
      latestMs = ms;
      latest = raw;
    }
  }
  return latest;
}

/**
 * Classify stored knowledge using existing source_type (and URI only as supporting
 * context for lesson-linked review notes). Never invent categories without API fields.
 */
export function knowledgeCategory(document: RagDocument): {
  kind: KnowledgeCategoryKind;
  label: string;
} {
  const sourceType = document.source_type;
  if (sourceType === "review_note") {
    return { kind: "accepted_lesson", label: "Accepted lesson" };
  }
  if (sourceType === "strategy_template") {
    return { kind: "strategy_or_rule", label: "Strategy / rule" };
  }
  if (sourceType === "trade_journal") {
    return { kind: "journal_derived", label: "Journal-derived" };
  }
  if (sourceType === "trading_playbook" || sourceType === "general_note") {
    return { kind: "manually_stored", label: "Manually stored" };
  }
  return { kind: "other", label: formatSourceType(sourceType) };
}

/** Parse only explicit stored URI schemes — never infer one ID type from another. */
export function parseStoredSourceUri(sourceUri: string | null | undefined): {
  kind: "journal" | "lesson" | "strategy" | null;
  id: string | null;
} {
  if (!sourceUri?.trim()) {
    return { kind: null, id: null };
  }
  const value = sourceUri.trim();
  const journal = JOURNAL_URI.exec(value);
  if (journal?.[1]) {
    return { kind: "journal", id: journal[1] };
  }
  const lesson = LESSON_URI.exec(value);
  if (lesson?.[1]) {
    return { kind: "lesson", id: lesson[1] };
  }
  const strategy = STRATEGY_URI.exec(value);
  if (strategy?.[1]) {
    return { kind: "strategy", id: strategy[1] };
  }
  return { kind: null, id: null };
}

/** Resolve relationship links only when real stored URI identifiers exist. */
export function resolveKnowledgeRelationships(
  document: RagDocument,
): KnowledgeRelationshipLink[] {
  const parsed = parseStoredSourceUri(document.source_uri);
  const links: KnowledgeRelationshipLink[] = [];

  if (parsed.kind === "lesson" && parsed.id) {
    links.push({
      kind: "lesson",
      label: "Related lesson",
      id: parsed.id,
      href: `/lessons?candidate=${encodeURIComponent(parsed.id)}`,
    });
  } else if (document.source_type === "review_note") {
    links.push({
      kind: "lesson",
      label: "Related lesson",
      id: null,
      href: null,
      unavailableReason: "No lesson:// identifier stored in source_uri.",
    });
  }

  if (parsed.kind === "journal" && parsed.id) {
    links.push({
      kind: "journal",
      label: "Related journal entry",
      id: parsed.id,
      href: `/journal?entry=${encodeURIComponent(parsed.id)}`,
    });
  } else if (document.source_type === "trade_journal") {
    links.push({
      kind: "journal",
      label: "Related journal entry",
      id: null,
      href: null,
      unavailableReason: "No journal:// identifier stored in source_uri.",
    });
  }

  if (parsed.kind === "strategy" && parsed.id) {
    links.push({
      kind: "strategy",
      label: "Related strategy",
      id: parsed.id,
      href: `/strategy-lab/${encodeURIComponent(parsed.id)}`,
    });
  } else if (document.source_type === "strategy_template") {
    links.push({
      kind: "strategy",
      label: "Related strategy",
      id: null,
      href: null,
      unavailableReason: "No strategy:// identifier stored in source_uri.",
    });
  }

  return links;
}

/** Client-side library search over the loaded document page only. */
export function filterDocumentsByLibraryQuery(
  documents: RagDocument[],
  query: string,
): RagDocument[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return documents;
  return documents.filter((doc) => {
    const haystack = [doc.title, doc.source_type, doc.source_uri ?? "", doc.id]
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}
