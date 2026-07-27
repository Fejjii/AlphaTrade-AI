"use client";

import type { ReactNode } from "react";

import { KnowledgeDocumentCard } from "@/components/knowledge/KnowledgeDocumentCard";
import type { SourceCoverage } from "@/components/knowledge/knowledgeCoverage";
import type { KnowledgeSourceFilter } from "@/components/knowledge/knowledgeContext";
import { knowledgeSourceFilterLabel } from "@/components/knowledge/knowledgeContext";
import { Button } from "@/components/ui/button";
import type { RagDocument } from "@/lib/api/types";

export type KnowledgeLibraryStatus =
  | "loading"
  | "unavailable"
  | "empty"
  | "truncated_empty"
  | "available";

type KnowledgeRecentListProps = {
  status: KnowledgeLibraryStatus;
  documents: RagDocument[] | null;
  error?: string | null;
  coverage: SourceCoverage | null;
  loadedCount: number | null;
  totalCount: number | null;
  sourceFilter: KnowledgeSourceFilter;
  libraryQuery: string;
  searchLimitedToLoadedPage: boolean;
  highlightedDocumentId?: string | null;
  expandedDocumentId?: string | null;
  onToggleExpand?: (documentId: string) => void;
  detailByDocumentId?: Record<string, ReactNode>;
  onRetry?: () => void;
  coverageMessage?: string | null;
};

export function KnowledgeRecentList({
  status,
  documents,
  error,
  coverage,
  loadedCount,
  totalCount,
  sourceFilter,
  libraryQuery,
  searchLimitedToLoadedPage,
  highlightedDocumentId,
  expandedDocumentId,
  onToggleExpand,
  detailByDocumentId = {},
  onRetry,
  coverageMessage,
}: KnowledgeRecentListProps) {
  const filterLabel = knowledgeSourceFilterLabel(sourceFilter);

  return (
    <section
      aria-labelledby="knowledge-recent-heading"
      data-testid="knowledge-recent-list"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="knowledge-recent-heading" className="text-lg font-semibold text-text-primary">
            Recently added knowledge
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Documents from the knowledge list API, newest first. Edit and archive actions are not
            available.
          </p>
        </div>
        {status === "unavailable" ? (
          <p className="text-sm text-text-muted" data-testid="knowledge-count-unavailable">
            Count unavailable
          </p>
        ) : coverage === "complete" && loadedCount !== null && totalCount !== null ? (
          <p className="text-sm text-text-secondary" data-testid="knowledge-count-complete">
            {totalCount} {totalCount === 1 ? "document" : "documents"}
            {sourceFilter !== "all" ? ` · ${filterLabel}` : ""}
          </p>
        ) : loadedCount !== null && totalCount !== null ? (
          <p className="text-sm text-text-secondary" data-testid="knowledge-count-loaded">
            {loadedCount} of {totalCount} documents loaded
            {sourceFilter !== "all" ? ` · ${filterLabel}` : ""}
          </p>
        ) : (
          <p className="text-sm text-text-muted" data-testid="knowledge-count-unavailable">
            Count unavailable
          </p>
        )}
      </div>

      {searchLimitedToLoadedPage && libraryQuery.trim() ? (
        <div
          role="status"
          data-testid="knowledge-search-loaded-coverage"
          className="rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary"
        >
          Library search for “{libraryQuery.trim()}” covers only the loaded page
          {loadedCount !== null && totalCount !== null
            ? ` (${loadedCount} of ${totalCount} documents)`
            : ""}
          . It is not a full-corpus scan.
        </div>
      ) : null}

      {coverage === "truncated" && coverageMessage ? (
        <div
          role="status"
          data-testid="knowledge-coverage-truncated"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {coverageMessage}
        </div>
      ) : null}

      {status === "loading" ? (
        <p className="text-sm text-text-muted" data-testid="knowledge-recent-loading">
          Loading knowledge documents…
        </p>
      ) : null}

      {status === "unavailable" ? (
        <div
          role="alert"
          data-testid="knowledge-recent-unavailable"
          className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        >
          <p className="font-medium">Knowledge library unavailable</p>
          <p className="mt-1">{error ?? "The documents source failed."}</p>
          {onRetry ? (
            <Button type="button" size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {status === "empty" ? (
        <div
          role="status"
          data-testid="knowledge-recent-empty"
          className="rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary"
        >
          {libraryQuery.trim()
            ? `No knowledge documents matched “${libraryQuery.trim()}” in the loaded page.`
            : sourceFilter === "all"
              ? "No knowledge documents are stored yet."
              : `No ${filterLabel.toLowerCase()} documents are stored.`}
        </div>
      ) : null}

      {status === "truncated_empty" ? (
        <div
          role="status"
          data-testid="knowledge-recent-truncated-empty"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {libraryQuery.trim()
            ? `No matches for “${libraryQuery.trim()}” were found in the loaded page. Coverage is truncated, so this is not an all-clear for the full library.`
            : `No ${sourceFilter === "all" ? "" : `${filterLabel.toLowerCase()} `}documents were found in the loaded page. Coverage is truncated, so empty results are not definitive.`}
        </div>
      ) : null}

      {status === "available" && documents && documents.length > 0 ? (
        <ul
          className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
          data-testid="knowledge-document-grid"
        >
          {documents.map((document) => (
            <li key={document.id} className="min-w-0">
              <KnowledgeDocumentCard
                document={document}
                highlighted={highlightedDocumentId === document.id}
                expanded={expandedDocumentId === document.id}
                onToggleExpand={
                  onToggleExpand ? () => onToggleExpand(document.id) : undefined
                }
                detailSlot={detailByDocumentId[document.id]}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
