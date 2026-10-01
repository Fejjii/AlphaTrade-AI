import { parseKnowledgeQuery } from "./knowledgeContext";
import { api } from "@/lib/api";

/** Views of the existing corpus, not new persisted categories. */
export const KNOWLEDGE_WORKSPACE_CATEGORIES = [
  { id: "rules", label: "Trading Rules", sources: ["risk_policy"] },
  { id: "playbook", label: "Playbook", sources: ["trading_playbook"] },
  {
    id: "lessons",
    label: "Lessons",
    sources: ["review_note", "mistakes_database"],
  },
  {
    id: "research",
    label: "Strategy Research",
    sources: ["strategy_template"],
  },
  {
    id: "observations",
    label: "Market Observations",
    sources: ["general_note", "trade_journal"],
  },
] as const;

export function parseWorkspaceQuery(params: URLSearchParams) {
  const legacy = parseKnowledgeQuery(params);
  const category = KNOWLEDGE_WORKSPACE_CATEGORIES.find(
    (item) => item.id === params.get("category"),
  );
  const rawOffset = Number(params.get("offset") ?? 0);
  const offset =
    Number.isSafeInteger(rawOffset) && rawOffset >= 0 ? rawOffset : 0;
  return {
    ...legacy,
    category,
    sources: category
      ? [...category.sources]
      : legacy.sourceFilter === "all"
        ? []
        : [legacy.sourceFilter],
    offset,
  };
}

export function workspaceHref(
  params: URLSearchParams,
  changes: { category?: string; offset?: number },
) {
  const next = new URLSearchParams(params);
  if (changes.category !== undefined) {
    next.delete("source");
    next.delete("offset");
    if (changes.category) next.set("category", changes.category);
    else next.delete("category");
  }
  if (changes.offset !== undefined) {
    if (changes.offset) next.set("offset", String(changes.offset));
    else next.delete("offset");
  }
  return next.size ? `/knowledge?${next}` : "/knowledge";
}

/** There is no document-by-ID endpoint. Resolve exact IDs through canonical pages. */
export async function findKnowledgeDocument(id: string) {
  const limit = 200;
  for (let offset = 0; offset < 4000; offset += limit) {
    const page = await api.knowledge.listDocuments({ limit, offset });
    const match = page.items.find((document) => document.id === id);
    if (match) return match;
    if (offset + page.items.length >= page.total)
      throw new Error("This document is no longer available.");
    if (!page.items.length)
      throw new Error(
        "The document list returned incomplete coverage. Try again.",
      );
  }
  throw new Error(
    "This document was not found in the first 4,000 records. Use document page navigation to locate it.",
  );
}
