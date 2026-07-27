"use client";

import { FormEvent, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { RagSearchResponse } from "@/lib/api/types";

import {
  KNOWLEDGE_SOURCE_FILTERS,
  knowledgeSourceFilterLabel,
  type KnowledgeSourceFilter,
} from "@/components/knowledge/knowledgeContext";

type KnowledgeSemanticSearchProps = {
  initialSourceFilter: KnowledgeSourceFilter;
};

export function KnowledgeSemanticSearch({
  initialSourceFilter,
}: KnowledgeSemanticSearchProps) {
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<KnowledgeSourceFilter>(
    initialSourceFilter === "all" ? "all" : initialSourceFilter,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<RagSearchResponse | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const source_types =
        sourceFilter === "all" ? undefined : [sourceFilter];
      setSearch(
        await api.knowledge.search({
          query: query.trim(),
          top_k: 5,
          source_types,
        }),
      );
    } catch (err) {
      setSearch(null);
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="knowledge-semantic-search-heading"
      data-testid="knowledge-semantic-search"
      className="space-y-3"
    >
      <div>
        <h2
          id="knowledge-semantic-search-heading"
          className="text-lg font-semibold text-text-primary"
        >
          Semantic knowledge search
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Uses the knowledge search API with ranked chunks and citations. This is separate from
          loaded-page library search.
        </p>
      </div>

      <form
        onSubmit={(event) => void onSubmit(event)}
        className="grid gap-3 md:grid-cols-[1fr_auto_auto] md:items-end"
        data-testid="knowledge-semantic-search-form"
      >
        <div className="space-y-2">
          <Label htmlFor="knowledge-semantic-query">Search query</Label>
          <Input
            id="knowledge-semantic-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search stored knowledge"
            data-testid="knowledge-semantic-query-input"
            autoComplete="off"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="knowledge-semantic-source">Source types</Label>
          <Select
            id="knowledge-semantic-source"
            value={sourceFilter}
            onChange={(event) =>
              setSourceFilter(event.target.value as KnowledgeSourceFilter)
            }
            data-testid="knowledge-semantic-source-select"
          >
            {KNOWLEDGE_SOURCE_FILTERS.map((filter) => (
              <option key={filter} value={filter}>
                {knowledgeSourceFilterLabel(filter)}
              </option>
            ))}
          </Select>
        </div>
        <Button
          type="submit"
          disabled={busy || !query.trim()}
          data-testid="knowledge-semantic-search-submit"
        >
          {busy ? "Searching…" : "Search API"}
        </Button>
      </form>

      {error ? (
        <ErrorState message={error} />
      ) : null}

      {search ? (
        <div className="space-y-4" data-testid="knowledge-semantic-results">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-medium text-text-primary">
              Results for “{search.query}”
            </h3>
            {search.degraded ? <StatusBadge label="Degraded" tone="warn" /> : null}
            {search.fallback_used ? <StatusBadge label="Fallback" tone="warn" /> : null}
            {search.vector_backend ? (
              <span className="text-xs text-text-muted">backend: {search.vector_backend}</span>
            ) : null}
          </div>
          {search.degraded || search.fallback_used ? (
            <p
              className="text-sm text-warning"
              data-testid="knowledge-search-degraded-note"
            >
              Search used a degraded or fallback retrieval path
              {search.detail ? ` — ${search.detail}` : ""}. Treat results as lower confidence.
            </p>
          ) : null}
          {search.chunks.length ? (
            search.chunks.map((chunk) => (
              <Card key={chunk.chunk_id}>
                <CardHeader>
                  <CardTitle className="text-sm">
                    {chunk.title ?? chunk.document_id}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-text-secondary">
                  <p>{chunk.content}</p>
                  <p className="text-text-muted">
                    Score: {chunk.score.toFixed(3)} · source: {chunk.source_type}
                  </p>
                </CardContent>
              </Card>
            ))
          ) : (
            <EmptyState title="No chunks matched" />
          )}
          {search.citations.length ? (
            <Card>
              <CardHeader>
                <CardTitle>Citations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-text-muted">
                {search.citations.map((citation) => (
                  <p key={citation.chunk_id}>{citation.snippet ?? citation.title}</p>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
