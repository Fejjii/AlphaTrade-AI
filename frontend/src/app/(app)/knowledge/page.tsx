"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { JournalHubChrome } from "@/components/journal/JournalHubChrome";
import {
  buildDeepLinkExclusionNotices,
  coverageFromPage,
  documentsCoverageMessage,
  filterDocumentsByLibraryQuery,
  KnowledgeCategorySummary,
  KnowledgeDetailPanel,
  KnowledgeDocumentCard,
  KnowledgeRecentList,
  KnowledgeSearchFilters,
  KnowledgeSemanticSearch,
  KnowledgeSourceAvailability,
  KnowledgeStorePanel,
  latestDocumentTimestamp,
  parseKnowledgeQuery,
  type KnowledgeLibraryStatus,
} from "@/components/knowledge";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { PaginatedRagChunks, PaginatedRagDocuments, RagDocument } from "@/lib/api/types";

type KnowledgeHubData = {
  documents: SourceResult<PaginatedRagDocuments>;
};

const DOCUMENT_PAGE_LIMIT = 50;

export default function KnowledgePage() {
  const searchParams = useSearchParams();
  // Depend on serialized params so back/forward and mutated test params recompute context.
  const searchKey = searchParams.toString();
  const context = useMemo(
    () => parseKnowledgeQuery(searchParams),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- searchKey captures URL changes
    [searchKey],
  );
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<KnowledgeHubData> => {
    const source_type =
      context.sourceFilter === "all" ? undefined : context.sourceFilter;
    const documents = await loadSource(
      api.knowledge.listDocuments({
        source_type,
        limit: DOCUMENT_PAGE_LIMIT,
        offset: 0,
      }),
    );
    return { documents };
  }, [context.sourceFilter]);

  const { data, loading, error, reload } = useAsyncData(loader, [context.sourceFilter]);

  const [deepLinkDocument, setDeepLinkDocument] = useState<SourceResult<RagDocument> | null>(
    null,
  );
  const [deepLinkLoading, setDeepLinkLoading] = useState(false);
  const [expandedDocumentId, setExpandedDocumentId] = useState<string | null>(null);
  const [chunkResults, setChunkResults] = useState<
    Record<string, SourceResult<PaginatedRagChunks>>
  >({});
  const [chunkLoadingId, setChunkLoadingId] = useState<string | null>(null);
  const chunkInFlightRef = useRef<string | null>(null);

  useEffect(() => {
    if (!context.documentId) {
      setDeepLinkDocument(null);
      setDeepLinkLoading(false);
      return;
    }

    let cancelled = false;
    setDeepLinkLoading(true);
    void (async () => {
      // No get-by-id API: probe an unfiltered loaded page, then chunks for existence.
      const unfiltered = await loadSource(
        api.knowledge.listDocuments({
          limit: DOCUMENT_PAGE_LIMIT,
          offset: 0,
        }),
      );
      if (cancelled) return;

      if (unfiltered.available && unfiltered.data) {
        const match = unfiltered.data.items.find((item) => item.id === context.documentId);
        if (match) {
          setDeepLinkDocument({
            data: match,
            available: true,
            error: null,
            fallbackUsed: false,
          });
          setDeepLinkLoading(false);
          return;
        }
        if (unfiltered.data.items.length < unfiltered.data.total) {
          setDeepLinkDocument({
            data: null,
            available: false,
            error: `Document ${context.documentId} was not present in the loaded unfiltered page (${unfiltered.data.items.length} of ${unfiltered.data.total}). No unrelated record was opened.`,
            fallbackUsed: false,
          });
          setDeepLinkLoading(false);
          return;
        }
      }

      const chunks = await loadSource(
        api.knowledge.listChunks({
          document_id: context.documentId!,
          limit: 1,
          offset: 0,
        }),
      );
      if (cancelled) return;

      if (chunks.available && chunks.data && chunks.data.total > 0) {
        setDeepLinkDocument({
          data: null,
          available: false,
          error: `Document ${context.documentId} appears to have stored chunks but was not present in the loaded documents page. No unrelated record was opened.`,
          fallbackUsed: false,
        });
      } else if (!chunks.available) {
        setDeepLinkDocument({
          data: null,
          available: false,
          error: `Document ${context.documentId} could not be verified (${chunks.error ?? unfiltered.error ?? "unavailable"}). No unrelated record was opened.`,
          fallbackUsed: false,
        });
      } else {
        setDeepLinkDocument({
          data: null,
          available: false,
          error: `Document ${context.documentId} was not found in loaded knowledge coverage. No unrelated record was opened.`,
          fallbackUsed: false,
        });
      }
      setDeepLinkLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [context.documentId]);

  const fetchChunks = useCallback(async (documentId: string) => {
    if (chunkInFlightRef.current === documentId) return;
    chunkInFlightRef.current = documentId;
    setChunkLoadingId(documentId);
    try {
      const result = await loadSource(
        api.knowledge.listChunks({
          document_id: documentId,
          limit: DOCUMENT_PAGE_LIMIT,
          offset: 0,
        }),
      );
      setChunkResults((prev) => ({ ...prev, [documentId]: result }));
    } finally {
      if (chunkInFlightRef.current === documentId) {
        chunkInFlightRef.current = null;
      }
      setChunkLoadingId((current) => (current === documentId ? null : current));
    }
  }, []);

  useEffect(() => {
    if (!expandedDocumentId) return;
    if (chunkResults[expandedDocumentId]) return;
    void fetchChunks(expandedDocumentId);
  }, [chunkResults, expandedDocumentId, fetchChunks]);

  const handleRetryChunks = (documentId: string) => {
    if (chunkInFlightRef.current === documentId || chunkLoadingId === documentId) return;
    void fetchChunks(documentId);
  };

  const documentsAvailable = Boolean(data?.documents.available);
  const page = documentsAvailable ? data?.documents.data : null;
  const coverage =
    documentsAvailable && page ? coverageFromPage(page.items.length, page.total) : null;

  const matchedFromLoaded = useMemo(() => {
    if (!context.documentId || !page) return null;
    return page.items.find((item) => item.id === context.documentId) ?? null;
  }, [context.documentId, page]);

  const candidateDocument = useMemo(() => {
    if (matchedFromLoaded) return matchedFromLoaded;
    if (
      deepLinkDocument?.available &&
      deepLinkDocument.data &&
      deepLinkDocument.data.id === context.documentId
    ) {
      return deepLinkDocument.data;
    }
    return null;
  }, [context.documentId, deepLinkDocument, matchedFromLoaded]);

  const libraryFiltered = useMemo(() => {
    if (!page) return null;
    return filterDocumentsByLibraryQuery(page.items, context.query);
  }, [context.query, page]);

  const visibleInFilteredList = useMemo(() => {
    if (!context.documentId || !libraryFiltered) return false;
    return libraryFiltered.some((doc) => doc.id === context.documentId);
  }, [context.documentId, libraryFiltered]);

  const highlightedDocumentId = visibleInFilteredList ? context.documentId : null;

  const dedicatedDeepLinkDocument =
    candidateDocument && !visibleInFilteredList ? candidateDocument : null;

  const deepLinkNotices = useMemo(() => {
    if (!dedicatedDeepLinkDocument) return [];
    return buildDeepLinkExclusionNotices({
      document: dedicatedDeepLinkDocument,
      inActiveSourcePage: Boolean(matchedFromLoaded),
      visibleInLibraryResults: visibleInFilteredList,
      sourceFilter: context.sourceFilter,
      libraryQuery: context.query,
    });
  }, [
    context.query,
    context.sourceFilter,
    dedicatedDeepLinkDocument,
    matchedFromLoaded,
    visibleInFilteredList,
  ]);

  const staleDocumentMessage = useMemo(() => {
    if (!context.documentId) return null;
    if (loading || deepLinkLoading) return null;
    if (candidateDocument) return null;
    if (deepLinkDocument && !deepLinkDocument.available) {
      return deepLinkDocument.error;
    }
    return `Document ${context.documentId} was not found in loaded knowledge coverage. No unrelated record was opened.`;
  }, [
    candidateDocument,
    context.documentId,
    deepLinkDocument,
    deepLinkLoading,
    loading,
  ]);

  const libraryStatus: KnowledgeLibraryStatus = useMemo(() => {
    if (loading && !data) return "loading";
    if (!documentsAvailable) return "unavailable";
    if (!libraryFiltered) return "unavailable";
    if (libraryFiltered.length > 0) return "available";
    if (coverage === "truncated") return "truncated_empty";
    return "empty";
  }, [coverage, data, documentsAvailable, libraryFiltered, loading]);

  const sourceStatuses = useMemo(() => {
    if (!data) return [];
    return [
      {
        name: "Knowledge documents",
        available: data.documents.available,
        error: data.documents.error,
        timestamp: latestDocumentTimestamp(data.documents.data?.items ?? []),
        required: true,
      },
    ];
  }, [data]);

  const freshnessSources = sourceStatuses.map((source) => ({
    name: source.name,
    available: source.available,
    required: source.required ?? true,
    timestamp: coverage === "truncated" ? null : source.timestamp,
  }));

  const detailByDocumentId = useMemo(() => {
    const entries: Record<string, ReactNode> = {};
    if (expandedDocumentId) {
      entries[expandedDocumentId] = (
        <KnowledgeDetailPanel
          documentId={expandedDocumentId}
          chunks={chunkResults[expandedDocumentId] ?? null}
          loading={chunkLoadingId === expandedDocumentId}
          onRetry={() => handleRetryChunks(expandedDocumentId)}
        />
      );
    }
    return entries;
  }, [chunkLoadingId, chunkResults, expandedDocumentId]);

  const handleToggleExpand = (documentId: string) => {
    setExpandedDocumentId((current) => (current === documentId ? null : documentId));
  };

  if (loading && !data) {
    return <LoadingState label="Loading Knowledge hub…" />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={() => void reload()} />;
  }

  return (
    <JournalHubChrome
      title="Knowledge"
      description="What trading knowledge have I stored, where did it come from, and how can I find and use it again?"
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="knowledge-hub-page"
      activeHref="/knowledge"
    >
      <div
        className="flex flex-wrap items-center gap-2"
        data-testid="knowledge-fastest-next-action"
      >
        <p className="text-sm text-text-secondary">Fastest next action:</p>
        <a
          href="#knowledge-recent-heading"
          className="inline-flex h-10 items-center rounded-control border border-border bg-surface-1 px-4 text-sm font-medium text-text-primary hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Browse recently added knowledge
        </a>
        {!documentsAvailable ? (
          <Button type="button" size="sm" variant="outline" onClick={() => void reload()}>
            Retry
          </Button>
        ) : null}
      </div>

      <KnowledgeSearchFilters
        sourceFilter={context.sourceFilter}
        libraryQuery={context.query}
        documentId={context.documentId}
      />

      {!documentsAvailable && data ? (
        <ErrorState
          message="Knowledge documents source is unavailable. Counts are not shown as zero."
          onRetry={() => void reload()}
        />
      ) : null}

      {staleDocumentMessage ? (
        <div
          role="alert"
          data-testid="knowledge-document-stale"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          {staleDocumentMessage}
        </div>
      ) : null}

      {dedicatedDeepLinkDocument ? (
        <section
          aria-labelledby="knowledge-deeplink-heading"
          data-testid="knowledge-deeplink-only"
          className="min-w-0 space-y-3"
        >
          <h2 id="knowledge-deeplink-heading" className="text-lg font-semibold text-text-primary">
            Deep-linked knowledge
          </h2>
          <KnowledgeDocumentCard
            document={dedicatedDeepLinkDocument}
            highlighted
            deepLinkNotices={deepLinkNotices}
            expanded={expandedDocumentId === dedicatedDeepLinkDocument.id}
            onToggleExpand={() => handleToggleExpand(dedicatedDeepLinkDocument.id)}
            detailSlot={detailByDocumentId[dedicatedDeepLinkDocument.id]}
          />
        </section>
      ) : null}

      <KnowledgeCategorySummary
        documents={page?.items ?? null}
        available={documentsAvailable}
        coverage={coverage}
        sourceFilter={context.sourceFilter}
        loading={loading && !data}
      />

      <KnowledgeRecentList
        status={libraryStatus}
        documents={libraryFiltered}
        error={data?.documents.error}
        coverage={coverage}
        loadedCount={page ? page.items.length : null}
        totalCount={page ? page.total : null}
        matchCount={libraryFiltered ? libraryFiltered.length : null}
        sourceFilter={context.sourceFilter}
        libraryQuery={context.query}
        searchLimitedToLoadedPage={Boolean(context.query.trim())}
        highlightedDocumentId={highlightedDocumentId}
        expandedDocumentId={expandedDocumentId}
        onToggleExpand={handleToggleExpand}
        detailByDocumentId={detailByDocumentId}
        onRetry={() => void reload()}
        coverageMessage={
          coverage === "truncated" && page
            ? documentsCoverageMessage(page.items.length, page.total)
            : null
        }
      />

      <KnowledgeSemanticSearch initialSourceFilter={context.sourceFilter} />

      <KnowledgeStorePanel onStored={() => void reload()} />

      <KnowledgeSourceAvailability
        sources={sourceStatuses}
        onRetry={() => void reload()}
        limitations={[
          ...(coverage === "truncated" && page
            ? [documentsCoverageMessage(page.items.length, page.total)]
            : []),
          "Library search covers only the loaded documents page, not the full corpus.",
          "Semantic search uses POST /knowledge/search and is separate from library search.",
          "Deep link ?document= is verified within loaded unfiltered coverage; there is no get-by-id API.",
          "Relationship links require stored source_uri schemes (journal://, lesson://, strategy://). IDs are never inferred across types.",
          "Edit, archive, and delete actions are not available through the current knowledge API.",
          "Category labels reflect primary backend producers: review_note←accepted lessons, trade_journal←journal sync, strategy_template←strategy library sync.",
          "Global cross-category counts require sourceFilter=all with complete coverage; active filters never invent zeros for unrequested categories.",
          posture.paperConfirmed
            ? "Runtime posture verified as paper-only for this session."
            : "Paper posture is not fully verified — treat execution labels as conservative guidance only.",
        ]}
      />
    </JournalHubChrome>
  );
}
