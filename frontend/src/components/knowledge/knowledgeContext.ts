type SearchParamsLike = { get: (key: string) => string | null };

/** API-backed source_type filters exposed on the Knowledge hub. */
export const KNOWLEDGE_SOURCE_FILTERS = [
  "all",
  "review_note",
  "strategy_template",
  "trade_journal",
  "trading_playbook",
  "general_note",
  "risk_policy",
] as const;

export type KnowledgeSourceFilter = (typeof KNOWLEDGE_SOURCE_FILTERS)[number];

export type KnowledgeQueryContext = {
  documentId: string | null;
  sourceFilter: KnowledgeSourceFilter;
  /** Loaded-page library search query (client-side). */
  query: string;
};

function parseSourceFilter(raw: string | null): KnowledgeSourceFilter {
  if (!raw) return "all";
  return (KNOWLEDGE_SOURCE_FILTERS as readonly string[]).includes(raw)
    ? (raw as KnowledgeSourceFilter)
    : "all";
}

/** Parse typed knowledge deep-link, filter, and library-search query parameters. */
export function parseKnowledgeQuery(searchParams: SearchParamsLike): KnowledgeQueryContext {
  const query = searchParams.get("q")?.trim() ?? "";
  return {
    documentId: searchParams.get("document"),
    sourceFilter: parseSourceFilter(searchParams.get("source")),
    query,
  };
}

function buildKnowledgeHref(parts: {
  sourceFilter?: KnowledgeSourceFilter;
  documentId?: string | null;
  query?: string | null;
}): string {
  const params = new URLSearchParams();
  const sourceFilter = parts.sourceFilter ?? "all";
  if (sourceFilter !== "all") {
    params.set("source", sourceFilter);
  }
  if (parts.query?.trim()) {
    params.set("q", parts.query.trim());
  }
  if (parts.documentId) {
    params.set("document", parts.documentId);
  }
  const qs = params.toString();
  return qs ? `/knowledge?${qs}` : "/knowledge";
}

export function knowledgeDocumentHref(
  documentId: string,
  options?: { sourceFilter?: KnowledgeSourceFilter; query?: string | null },
): string {
  return buildKnowledgeHref({
    documentId,
    sourceFilter: options?.sourceFilter,
    query: options?.query,
  });
}

/** Source filter link, preserving deep-link document and library query. */
export function knowledgeSourceFilterHref(
  sourceFilter: KnowledgeSourceFilter,
  options?: { documentId?: string | null; query?: string | null },
): string {
  return buildKnowledgeHref({
    sourceFilter,
    documentId: options?.documentId,
    query: options?.query,
  });
}

/** Library search href, preserving source filter and optional document deep link. */
export function knowledgeLibrarySearchHref(
  query: string,
  options?: { sourceFilter?: KnowledgeSourceFilter; documentId?: string | null },
): string {
  return buildKnowledgeHref({
    sourceFilter: options?.sourceFilter ?? "all",
    documentId: options?.documentId,
    query,
  });
}

export function knowledgeSourceFilterLabel(filter: KnowledgeSourceFilter): string {
  switch (filter) {
    case "all":
      return "All types";
    case "review_note":
      return "Accepted lessons";
    case "strategy_template":
      return "Strategies / rules";
    case "trade_journal":
      return "Journal-derived";
    case "trading_playbook":
      return "Playbooks";
    case "general_note":
      return "General notes";
    case "risk_policy":
      return "Risk policy";
    default:
      return filter;
  }
}
