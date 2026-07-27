"use client";

import { coverageFromPage } from "@/components/knowledge/knowledgeCoverage";
import { Button } from "@/components/ui/button";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { PaginatedRagChunks } from "@/lib/api/types";

type KnowledgeDetailPanelProps = {
  documentId: string;
  chunks: SourceResult<PaginatedRagChunks> | null;
  loading: boolean;
  onRetry?: () => void;
};

export function KnowledgeDetailPanel({
  documentId,
  chunks,
  loading,
  onRetry,
}: KnowledgeDetailPanelProps) {
  if (loading && (!chunks || !chunks.available)) {
    return (
      <div
        className="rounded-control border border-border-subtle bg-surface-0 px-3 py-2 text-sm text-text-muted"
        data-testid={`knowledge-detail-loading-${documentId}`}
      >
        {chunks && !chunks.available
          ? "Retrying document chunks…"
          : "Loading document chunks…"}
      </div>
    );
  }

  if (!chunks) {
    return null;
  }

  if (!chunks.available) {
    return (
      <div
        role="alert"
        className="space-y-2 rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        data-testid={`knowledge-detail-unavailable-${documentId}`}
      >
        <p>Document detail unavailable{chunks.error ? `: ${chunks.error}` : "."}</p>
        {onRetry ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={loading}
            onClick={onRetry}
            data-testid={`knowledge-detail-retry-${documentId}`}
          >
            {loading ? "Retrying…" : "Retry"}
          </Button>
        ) : null}
      </div>
    );
  }

  const page = chunks.data;
  if (!page) {
    return (
      <div
        role="alert"
        className="space-y-2 rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        data-testid={`knowledge-detail-unavailable-${documentId}`}
      >
        <p>Document detail unavailable.</p>
        {onRetry ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={loading}
            onClick={onRetry}
            data-testid={`knowledge-detail-retry-${documentId}`}
          >
            {loading ? "Retrying…" : "Retry"}
          </Button>
        ) : null}
      </div>
    );
  }

  const coverage = coverageFromPage(page.items.length, page.total);

  return (
    <div
      className="min-w-0 space-y-2 rounded-control border border-border-subtle bg-surface-0 px-3 py-3"
      data-testid={`knowledge-detail-${documentId}`}
    >
      <p className="text-sm font-medium text-text-primary">Expanded document view</p>
      {coverage === "truncated" ? (
        <p
          role="status"
          className="text-sm text-warning"
          data-testid={`knowledge-detail-truncated-${documentId}`}
        >
          Showing {page.items.length} of {page.total} chunks. Chunk coverage is truncated.
        </p>
      ) : (
        <p className="text-sm text-text-muted" data-testid={`knowledge-detail-count-${documentId}`}>
          {page.total} {page.total === 1 ? "chunk" : "chunks"}
        </p>
      )}
      {page.items.length === 0 ? (
        <p
          className="text-sm text-text-secondary"
          data-testid={`knowledge-detail-empty-${documentId}`}
        >
          {coverage === "complete"
            ? "No chunks are stored for this document."
            : "No chunks were returned in the loaded page; coverage is truncated so this is not definitive."}
        </p>
      ) : (
        <ol className="space-y-2">
          {page.items.map((chunk) => (
            <li
              key={chunk.id}
              className="min-w-0 rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary"
              data-testid={`knowledge-chunk-${chunk.id}`}
            >
              <p className="break-words font-medium text-text-primary">
                Chunk {chunk.chunk_ordinal}
                {chunk.section_title ? ` · ${chunk.section_title}` : ""}
              </p>
              <p className="mt-1 whitespace-pre-wrap break-words">{chunk.content}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
