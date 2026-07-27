import type { SourceCoverage } from "@/components/knowledge/knowledgeCoverage";
import {
  knowledgeSourceFilterLabel,
  type KnowledgeSourceFilter,
} from "@/components/knowledge/knowledgeContext";
import {
  categoryKindForSourceFilter,
  knowledgeCategory,
  type KnowledgeCategoryKind,
} from "@/components/knowledge/knowledgeDisplay";
import type { RagDocument } from "@/lib/api/types";

const CATEGORY_ORDER: Array<{ kind: KnowledgeCategoryKind; label: string }> = [
  { kind: "accepted_lesson", label: "Accepted lessons" },
  { kind: "strategy_or_rule", label: "Strategies / rules" },
  { kind: "journal_derived", label: "Journal-derived" },
  { kind: "manually_stored", label: "Manually stored" },
  { kind: "other", label: "Other stored types" },
];

type KnowledgeCategorySummaryProps = {
  documents: RagDocument[] | null;
  available: boolean;
  coverage: SourceCoverage | null;
  sourceFilter: KnowledgeSourceFilter;
  loading?: boolean;
};

export function KnowledgeCategorySummary({
  documents,
  available,
  coverage,
  sourceFilter,
  loading = false,
}: KnowledgeCategorySummaryProps) {
  const filteredView = sourceFilter !== "all";
  const activeKind = categoryKindForSourceFilter(sourceFilter);
  const globalCountsDefinitive = !filteredView && coverage === "complete";

  const counts = new Map<KnowledgeCategoryKind, number>();
  for (const kind of CATEGORY_ORDER.map((item) => item.kind)) {
    counts.set(kind, 0);
  }
  for (const doc of documents ?? []) {
    const kind = knowledgeCategory(doc).kind;
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }

  const cards = filteredView
    ? CATEGORY_ORDER.filter((item) => item.kind === activeKind).map((item) => ({
        ...item,
        label: knowledgeSourceFilterLabel(sourceFilter),
      }))
    : CATEGORY_ORDER;

  return (
    <section
      aria-labelledby="knowledge-categories-heading"
      data-testid="knowledge-categories"
      className="space-y-3"
    >
      <div>
        <h2 id="knowledge-categories-heading" className="text-lg font-semibold text-text-primary">
          Knowledge categories
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Distinctions use stored source_type values only. Global cross-category counts require an
          unfiltered complete list.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-text-muted" data-testid="knowledge-categories-loading">
          Loading categories…
        </p>
      ) : null}

      {!loading && !available ? (
        <div
          role="alert"
          data-testid="knowledge-categories-unavailable"
          className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        >
          Category counts unavailable because the documents source failed.
        </div>
      ) : null}

      {!loading && available && filteredView ? (
        <div
          role="status"
          data-testid="knowledge-categories-filter-limited"
          className="rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary"
        >
          Category overview is limited to the active source filter (
          {knowledgeSourceFilterLabel(sourceFilter)}). Unrequested categories are not shown as zero.
        </div>
      ) : null}

      {!loading && available && !filteredView && coverage === "truncated" ? (
        <div
          role="status"
          data-testid="knowledge-categories-truncated"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          Category totals are not shown because the loaded document list is truncated. Loaded-page
          category presence is listed without definitive counts.
        </div>
      ) : null}

      {!loading && available && filteredView && coverage === "truncated" ? (
        <div
          role="status"
          data-testid="knowledge-categories-truncated"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          Active-filter coverage is truncated. Showing loaded-page presence for this filter only,
          without a definitive total.
        </div>
      ) : null}

      {!loading && available ? (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map(({ kind, label }) => {
            const count = counts.get(kind) ?? 0;
            const presentOnLoadedPage = count > 0;
            const showDefinitiveCount = filteredView
              ? coverage === "complete"
              : globalCountsDefinitive;
            return (
              <li
                key={`${kind}-${label}`}
                className="min-w-0 rounded-control border border-border-subtle px-3 py-2 text-sm"
                data-testid={`knowledge-category-${kind}`}
              >
                <p className="break-words font-medium text-text-primary">{label}</p>
                {showDefinitiveCount ? (
                  <p
                    className="mt-1 text-text-secondary"
                    data-testid={`knowledge-category-count-${kind}`}
                  >
                    {count} {count === 1 ? "document" : "documents"}
                  </p>
                ) : (
                  <p
                    className="mt-1 text-text-muted"
                    data-testid={`knowledge-category-presence-${kind}`}
                  >
                    {presentOnLoadedPage
                      ? "Present in loaded page (count unavailable)"
                      : "Not seen in loaded page (count unavailable)"}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
