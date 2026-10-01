"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

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
  workspaceSources?: string[];
  initialQuery?: string;
};

export function KnowledgeSemanticSearch({
  initialSourceFilter,
  workspaceSources,
  initialQuery = "",
}: KnowledgeSemanticSearchProps) {
  const [query, setQuery] = useState(initialQuery);
  const [sourceFilter, setSourceFilter] = useState<KnowledgeSourceFilter>(
    initialSourceFilter === "all" ? "all" : initialSourceFilter,
  );
  // Keep the select in sync when the URL/source prop changes after mount (FP2-210).
  useEffect(() => {
    setSourceFilter(
      initialSourceFilter === "all" ? "all" : initialSourceFilter,
    );
  }, [initialSourceFilter]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<RagSearchResponse | null>(null);
  const generation = useRef(0);
  const workspaceKey = workspaceSources?.join(",");
  useEffect(() => {
    generation.current += 1;
    setSearch(null);
    setError(null);
    setBusy(false);
    setQuery(initialQuery);
    return () => {
      generation.current += 1;
    };
  }, [workspaceKey, sourceFilter, initialQuery]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    const request = ++generation.current;
    setBusy(true);
    setSearch(null);
    setError(null);
    try {
      const source_types =
        workspaceSources ??
        (sourceFilter === "all" ? undefined : [sourceFilter]);
      const result = await api.knowledge.search({
        query: query.trim(),
        top_k: 5,
        source_types,
      });
      if (request === generation.current) setSearch(result);
    } catch (err) {
      if (request !== generation.current) return;
      setSearch(null);
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      if (request === generation.current) setBusy(false);
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
          {workspaceSources ? "Search knowledge" : "Semantic knowledge search"}
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          {workspaceSources
            ? "Search stored content in this category. Results link back to their original documents."
            : "Search ranked passages and their sources across stored knowledge."}
        </p>
      </div>

      <form
        onSubmit={(event) => void onSubmit(event)}
        className={`grid min-w-0 gap-3 md:items-end ${workspaceSources ? "md:grid-cols-[1fr_auto]" : "md:grid-cols-[1fr_auto_auto]"}`}
        data-testid="knowledge-semantic-search-form"
      >
        <div className="space-y-2">
          <Label htmlFor="knowledge-semantic-query">Search query</Label>
          <Input
            id="knowledge-semantic-query"
            value={query}
            onChange={(event) => {
              generation.current += 1;
              setBusy(false);
              setSearch(null);
              setError(null);
              setQuery(event.target.value);
            }}
            placeholder="Search stored knowledge"
            data-testid="knowledge-semantic-query-input"
            autoComplete="off"
          />
        </div>
        {workspaceSources === undefined ? (
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
        ) : null}
        <Button
          type="submit"
          disabled={busy || !query.trim()}
          data-testid="knowledge-semantic-search-submit"
        >
          {busy ? "Searching…" : "Search"}
        </Button>
      </form>

      {busy ? (
        <p role="status" className="text-sm text-text-muted">
          Searching stored knowledge…
        </p>
      ) : null}
      {error ? <ErrorState message={error} /> : null}

      {search ? (
        <div className="space-y-4" data-testid="knowledge-semantic-results">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-medium text-text-primary">
              Results for “{search.query}”
            </h3>
            {search.degraded ? (
              <StatusBadge label="Degraded" tone="warn" />
            ) : null}
            {search.fallback_used ? (
              <StatusBadge label="Fallback" tone="warn" />
            ) : null}
          </div>
          {search.degraded || search.fallback_used ? (
            <p
              className="text-sm text-warning"
              data-testid="knowledge-search-degraded-note"
            >
              Search used a degraded or fallback retrieval path
              {search.detail ? ` — ${search.detail}` : ""}. Treat results as
              lower confidence.
            </p>
          ) : null}
          {search.chunks.length ? (
            search.chunks.map((chunk) => (
              <Card key={chunk.chunk_id} className="min-w-0">
                <CardHeader>
                  <CardTitle className="text-sm">
                    <Link
                      className="inline-flex min-h-11 items-center break-words underline"
                      href={`/knowledge?document=${encodeURIComponent(chunk.document_id)}&source=${encodeURIComponent(chunk.source_type)}`}
                    >
                      {chunk.title ?? chunk.document_id}
                    </Link>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-text-secondary">
                  <p className="whitespace-pre-wrap break-words">
                    {chunk.content}
                  </p>
                  <p className="text-text-muted">
                    Source: {chunk.source_type.replace(/_/g, " ")} · passage{" "}
                    {chunk.chunk_ordinal}
                    {chunk.section_title ? ` · ${chunk.section_title}` : ""}
                    {chunk.page_number != null
                      ? ` · page ${chunk.page_number}`
                      : ""}
                  </p>
                  <p className="break-all text-xs text-text-muted">
                    Document {chunk.document_id} · passage {chunk.chunk_id}
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
                  <p key={citation.chunk_id} className="break-words">
                    <Link
                      href={`/knowledge?document=${encodeURIComponent(citation.document_id)}&source=${encodeURIComponent(citation.source_type)}`}
                      className="underline"
                    >
                      {citation.title ?? citation.document_id}
                    </Link>
                    {citation.snippet ? ` · ${citation.snippet}` : ""}
                  </p>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
