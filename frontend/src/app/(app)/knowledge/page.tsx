"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { KnowledgeDetailPanel } from "@/components/knowledge/KnowledgeDetailPanel";
import { KnowledgeDocumentCard } from "@/components/knowledge/KnowledgeDocumentCard";
import { KnowledgeStorePanel } from "@/components/knowledge/KnowledgeStorePanel";
import { KnowledgeSemanticSearch } from "@/components/knowledge/KnowledgeSemanticSearch";
import { KnowledgeRelatedContext } from "@/components/knowledge/KnowledgeRelatedContext";
import { filterDocumentsByLibraryQuery } from "@/components/knowledge/knowledgeDisplay";
import { knowledgeSourceFilterLabel } from "@/components/knowledge/knowledgeContext";
import {
  findKnowledgeDocument,
  KNOWLEDGE_WORKSPACE_CATEGORIES,
  parseWorkspaceQuery,
  workspaceHref,
} from "@/components/knowledge/knowledgeWorkspace";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { loadSource } from "@/components/workflows/sourceResult";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { RagDocument } from "@/lib/api/types";

const PAGE_LIMIT = 50;

function DocumentDetail({ document }: { document: RagDocument }) {
  const loader = useCallback(
    () =>
      loadSource(
        api.knowledge.listChunks({
          document_id: document.id,
          limit: PAGE_LIMIT,
          offset: 0,
        }),
      ),
    [document.id],
  );
  const { data, loading, reload } = useAsyncData(loader, [document.id]);
  return (
    <div className="min-w-0 space-y-3">
      <KnowledgeDetailPanel
        documentId={document.id}
        chunks={loading ? null : data}
        loading={loading}
        onRetry={() => void reload()}
      />
      <KnowledgeRelatedContext document={document} />
    </div>
  );
}

function LinkedDocument({ id, retryKey }: { id: string; retryKey: number }) {
  const loader = useCallback(() => findKnowledgeDocument(id), [id]);
  const { data, loading, error, reload } = useAsyncData(loader, [id, retryKey]);
  if (loading) return <LoadingState label="Opening linked knowledge…" />;
  if (error)
    return (
      <div data-testid="knowledge-document-stale">
        <ErrorState
          message={`Document ${id}: ${error}`}
          onRetry={() => void reload()}
        />
      </div>
    );
  if (!data) return null;
  return (
    <section
      aria-label="Linked knowledge"
      className="space-y-2"
      data-testid="knowledge-deeplink-only"
    >
      <p className="text-sm text-text-muted">
        Opened from a direct link, outside the current results.
      </p>
      <KnowledgeDocumentCard
        document={data}
        highlighted
        expanded
        detailSlot={<DocumentDetail key={data.id} document={data} />}
      />
    </section>
  );
}

export default function KnowledgePage() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const params = useMemo(() => new URLSearchParams(searchKey), [searchKey]);
  const context = useMemo(() => parseWorkspaceQuery(params), [params]);
  const sourceKey = context.sources.join(",");
  const [expandedId, setExpandedId] = useState<string | null>(
    context.documentId,
  );
  useEffect(() => {
    setExpandedId(context.documentId);
  }, [context.documentId]);
  const [addingNote, setAddingNote] = useState(false);
  const [storedCount, setStoredCount] = useState(0);

  const loader = useCallback(async () => {
    const sources = sourceKey ? sourceKey.split(",") : [undefined];
    return Promise.all(
      sources.map(async (source) => ({
        source,
        result: await loadSource(
          api.knowledge.listDocuments({
            source_type: source,
            limit: PAGE_LIMIT,
            offset: context.offset,
          }),
        ),
      })),
    );
  }, [sourceKey, context.offset]);
  const { data, loading, error, reload } = useAsyncData(loader, [
    sourceKey,
    context.offset,
  ]);
  // Hide the previous category during reloads; partial reads remain explicit below.
  const pages = loading ? [] : (data ?? []);
  const documents = pages.flatMap(({ result }) =>
    result.available ? (result.data?.items ?? []) : [],
  );
  const uniqueDocuments = [
    ...new Map(documents.map((document) => [document.id, document])).values(),
  ];
  const visible = filterDocumentsByLibraryQuery(uniqueDocuments, context.query);
  const failures = pages.filter(({ result }) => !result.available);
  const available = pages.some(({ result }) => result.available);
  const hasNext = pages.some(
    ({ result }) =>
      result.data &&
      context.offset + result.data.items.length < result.data.total,
  );
  const total = pages.reduce(
    (count, { result }) => count + (result.data?.total ?? 0),
    0,
  );
  const linkedInList = visible.some(
    (document) => document.id === context.documentId,
  );
  const heading =
    context.category?.label ??
    (context.sourceFilter === "all"
      ? "All knowledge"
      : knowledgeSourceFilterLabel(context.sourceFilter));

  function stored() {
    setStoredCount((count) => count + 1);
    void reload();
  }

  return (
    <div
      className="min-w-0 space-y-6 pb-24 md:pb-section [&_input]:text-base [&_textarea]:text-base [&_select]:text-base lg:[&_input]:text-sm lg:[&_textarea]:text-sm lg:[&_select]:text-sm"
      data-testid="knowledge-hub-page"
    >
      <PageHeader
        title="Knowledge"
        description="Your trading rules, playbook and lessons, with the sources behind them."
        actions={
          <Button
            type="button"
            variant="outline"
            aria-expanded={addingNote}
            aria-controls="knowledge-add-note"
            onClick={() => setAddingNote((open) => !open)}
          >
            {addingNote ? "Close note" : "Add note"}
          </Button>
        }
      />
      <nav
        aria-label="Knowledge categories"
        className="flex flex-wrap gap-2"
        data-testid="knowledge-categories"
      >
        {[
          { id: "", label: "All knowledge" },
          ...KNOWLEDGE_WORKSPACE_CATEGORIES,
        ].map((category) => {
          const active =
            category.id === (context.category?.id ?? "") &&
            (Boolean(context.category) || context.sourceFilter === "all");
          return (
            <Link
              key={category.id}
              href={workspaceHref(params, { category: category.id })}
              aria-current={active ? "page" : undefined}
              className={`inline-flex min-h-11 items-center rounded-control border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${active ? "border-info-border bg-surface-2 font-medium text-text-primary" : "border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2"}`}
            >
              {category.label}
            </Link>
          );
        })}
      </nav>
      <KnowledgeSemanticSearch
        initialSourceFilter={context.sourceFilter}
        workspaceSources={context.sources}
        initialQuery={context.query}
      />
      {addingNote ? (
        <div id="knowledge-add-note">
          <KnowledgeStorePanel
            onStored={stored}
            initialSourceType={
              context.category?.id === "rules"
                ? "risk_policy"
                : context.category?.id === "observations"
                  ? "general_note"
                  : "trading_playbook"
            }
          />
        </div>
      ) : null}
      {context.documentId && !loading && !linkedInList ? (
        <LinkedDocument
          key={context.documentId}
          id={context.documentId}
          retryKey={storedCount}
        />
      ) : null}
      <section
        aria-labelledby="knowledge-library-heading"
        className="min-w-0 space-y-3"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2
            id="knowledge-library-heading"
            className="text-lg font-semibold text-text-primary"
          >
            {heading}
          </h2>
          {available ? (
            <p className="text-sm text-text-muted">
              {visible.length} shown
              {!failures.length ? ` · ${total} stored` : " · partial coverage"}
            </p>
          ) : null}
        </div>
        <p className="text-sm text-text-muted">
          {context.category?.id === "observations"
            ? "Stored notes and journal observations."
            : context.category?.id === "lessons"
              ? "Reviewed lesson memory and stored mistake records."
              : "Browse stored documents and open their source context."}
        </p>
        {context.query ? (
          <p role="status" className="text-sm text-text-muted">
            Document titles and source references filtered by “{context.query}”
            on this page. Search above also searches stored content.
          </p>
        ) : null}
        {loading ? <LoadingState label="Loading Knowledge workspace…" /> : null}
        {!loading && error ? (
          <ErrorState message={error} onRetry={() => void reload()} />
        ) : null}
        {failures.map(({ source, result }) => (
          <ErrorState
            key={source ?? "all"}
            message={`${source?.replace(/_/g, " ") ?? "Knowledge"} unavailable: ${result.error ?? "Unable to load documents"}`}
            onRetry={() => void reload()}
          />
        ))}
        {!loading && available && !visible.length ? (
          <EmptyState
            title={
              hasNext || context.offset > 0 || failures.length || context.query
                ? "No documents on this page"
                : context.category || context.sourceFilter !== "all"
                  ? `No ${heading.toLowerCase()} yet`
                  : "No knowledge yet"
            }
            description="Try another category or search stored content. Add a note to capture your own trading knowledge."
          />
        ) : null}
        {!loading && visible.length > 0 ? (
          <ul
            className="grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-2"
            data-testid="knowledge-document-grid"
          >
            {visible.map((document) => {
              const expanded = expandedId === document.id;
              return (
                <li key={document.id} className="min-w-0">
                  <KnowledgeDocumentCard
                    document={document}
                    highlighted={context.documentId === document.id}
                    expanded={expanded}
                    onToggleExpand={() =>
                      setExpandedId((current) =>
                        current === document.id ? null : document.id,
                      )
                    }
                    detailSlot={
                      expanded ? (
                        <DocumentDetail key={document.id} document={document} />
                      ) : null
                    }
                  />
                </li>
              );
            })}
          </ul>
        ) : null}
        {!loading && (hasNext || context.offset > 0) ? (
          <nav
            aria-label="Knowledge document pages"
            className="flex flex-wrap items-center gap-3 text-sm"
          >
            <p className="text-text-muted">
              Showing up to {PAGE_LIMIT} documents per source, from record{" "}
              {context.offset + 1}.
            </p>
            {context.offset > 0 ? (
              <Link
                className="inline-flex min-h-11 items-center underline"
                href={workspaceHref(params, {
                  offset: Math.max(0, context.offset - PAGE_LIMIT),
                })}
              >
                Previous
              </Link>
            ) : null}
            {hasNext ? (
              <Link
                className="inline-flex min-h-11 items-center underline"
                href={workspaceHref(params, {
                  offset: context.offset + PAGE_LIMIT,
                })}
              >
                Next
              </Link>
            ) : null}
          </nav>
        ) : null}
      </section>
      <p className="text-xs text-text-muted">
        Source types organize existing knowledge. Strategy and lesson changes
        are reviewed in their own workspaces.
      </p>
    </div>
  );
}
