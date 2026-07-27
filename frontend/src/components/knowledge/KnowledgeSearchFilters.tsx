"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import {
  KNOWLEDGE_SOURCE_FILTERS,
  knowledgeLibrarySearchHref,
  knowledgeSourceFilterHref,
  knowledgeSourceFilterLabel,
  type KnowledgeSourceFilter,
} from "@/components/knowledge/knowledgeContext";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

type KnowledgeSearchFiltersProps = {
  sourceFilter: KnowledgeSourceFilter;
  libraryQuery: string;
  documentId?: string | null;
};

export function KnowledgeSearchFilters({
  sourceFilter,
  libraryQuery,
  documentId,
}: KnowledgeSearchFiltersProps) {
  const router = useRouter();
  const [draftQuery, setDraftQuery] = useState(libraryQuery);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    router.push(
      knowledgeLibrarySearchHref(draftQuery, {
        sourceFilter,
        documentId,
      }),
    );
  };

  return (
    <section
      aria-labelledby="knowledge-search-filters-heading"
      data-testid="knowledge-search-filters"
      className="space-y-4"
    >
      <div>
        <h2
          id="knowledge-search-filters-heading"
          className="text-lg font-semibold text-text-primary"
        >
          Search and filters
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Library search filters the loaded document page only. Use semantic retrieval below to query
          the knowledge base API.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end"
        data-testid="knowledge-library-search-form"
      >
        <div className="min-w-0 flex-1 space-y-2">
          <Label htmlFor="knowledge-library-search">Library search (loaded page)</Label>
          <Input
            id="knowledge-library-search"
            name="q"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            placeholder="Filter loaded titles, types, or URIs"
            data-testid="knowledge-library-search-input"
            autoComplete="off"
          />
        </div>
        <Button type="submit" data-testid="knowledge-library-search-submit">
          Search loaded page
        </Button>
        {libraryQuery.trim() ? (
          <Link
            href={knowledgeLibrarySearchHref("", { sourceFilter, documentId })}
            className="inline-flex h-10 items-center rounded-control border border-border px-4 text-sm text-text-secondary hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            data-testid="knowledge-library-search-clear"
          >
            Clear search
          </Link>
        ) : null}
      </form>

      <div
        className="flex flex-wrap items-center gap-2 text-xs"
        role="group"
        aria-label="Knowledge source filter"
        data-testid="knowledge-source-filter"
      >
        <span className="text-text-muted">Type:</span>
        {KNOWLEDGE_SOURCE_FILTERS.map((filter) => {
          const active = sourceFilter === filter;
          return (
            <Link
              key={filter}
              href={knowledgeSourceFilterHref(filter, {
                documentId,
                query: libraryQuery,
              })}
              data-testid={`knowledge-source-${filter}`}
              aria-current={active ? "true" : undefined}
              className={
                active
                  ? "rounded-control bg-zinc-100 px-3 py-2 font-medium text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  : "rounded-control border border-zinc-700 px-3 py-2 text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              }
            >
              {knowledgeSourceFilterLabel(filter)}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
