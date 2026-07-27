import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows/sourceResult";
import type { PaginatedRagChunks, PaginatedRagDocuments, RagDocument } from "@/lib/api/types";

import KnowledgePage from "./page";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
};

const search = new URLSearchParams();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => search,
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchBusy: false,
    killSwitchError: null,
    setKillSwitchActive: vi.fn(),
  }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/contexts/ShellFreshnessContext", () => ({
  useShellFreshness: () => ({
    freshness: { state: null },
    setFreshness: vi.fn(),
    clearFreshness: vi.fn(),
  }),
}));

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function documentFixture(overrides: Partial<RagDocument> & { id: string }): RagDocument {
  return {
    title: "Sample knowledge",
    source_type: "trading_playbook",
    version: 1,
    created_at: "2026-07-20T10:00:00.000Z",
    updated_at: "2026-07-20T11:00:00.000Z",
    ...overrides,
  };
}

const playbookDoc = documentFixture({
  id: "doc-playbook",
  title: "Pullback playbook",
  source_type: "trading_playbook",
});
const journalDoc = documentFixture({
  id: "doc-journal",
  title: "Journal sync note",
  source_type: "trade_journal",
  source_uri: "journal://entry-99",
});
const lessonDoc = documentFixture({
  id: "doc-lesson",
  title: "Accepted lesson memory",
  source_type: "review_note",
  source_uri: "lesson://lesson-42",
});
const strategyDoc = documentFixture({
  id: "doc-strategy",
  title: "Strategy template",
  source_type: "strategy_template",
  source_uri: "strategy://strat-7/v1",
});

let asyncState = {
  data: {
    documents: ok<PaginatedRagDocuments>({
      items: [playbookDoc, journalDoc, lessonDoc, strategyDoc],
      total: 4,
      limit: 50,
      offset: 0,
    }),
  } as {
    documents: SourceResult<PaginatedRagDocuments>;
  } | null,
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

const listDocumentsMock = vi.fn();
const listChunksMock = vi.fn();
const searchMock = vi.fn();
const ingestMock = vi.fn();

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      knowledge: {
        ...actual.api.knowledge,
        listDocuments: (...args: unknown[]) => listDocumentsMock(...args),
        listChunks: (...args: unknown[]) => listChunksMock(...args),
        search: (...args: unknown[]) => searchMock(...args),
        ingest: (...args: unknown[]) => ingestMock(...args),
      },
    },
  };
});

function resetAsyncState() {
  asyncState = {
    data: {
      documents: ok({
        items: [playbookDoc, journalDoc, lessonDoc, strategyDoc],
        total: 4,
        limit: 50,
        offset: 0,
      }),
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  };
}

beforeEach(() => {
  resetAsyncState();
  safetyPosture.executionMode = "paper";
  safetyPosture.realTradingEnabled = false;
  search.forEach((_, key) => search.delete(key));
  pushMock.mockReset();
  listDocumentsMock.mockReset();
  listChunksMock.mockReset();
  searchMock.mockReset();
  ingestMock.mockReset();
  listDocumentsMock.mockResolvedValue({
    items: [playbookDoc, journalDoc, lessonDoc, strategyDoc],
    total: 4,
    limit: 50,
    offset: 0,
  });
  listChunksMock.mockResolvedValue({
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
  } satisfies PaginatedRagChunks);
  searchMock.mockResolvedValue({
    query: "test",
    chunks: [],
    citations: [],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("KnowledgePage hub", () => {
  it("renders loading state initially", () => {
    asyncState = { data: null, loading: true, error: null, reload: vi.fn() };
    render(<KnowledgePage />);
    expect(screen.getByText(/loading knowledge hub/i)).toBeInTheDocument();
  });

  it("renders knowledge hub sections and existing route chrome", async () => {
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-hub-page")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-search-filters")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-recent-list")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-categories")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-semantic-search")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-source-availability")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Knowledge" })).toHaveAttribute("aria-current", "page");
  });

  it("shows honest empty state", async () => {
    asyncState.data!.documents = ok({ items: [], total: 0, limit: 50, offset: 0 });
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-recent-empty")).toBeInTheDocument();
  });

  it("does not show empty list when documents source failed", async () => {
    asyncState.data!.documents = failed("documents down");
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-recent-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("knowledge-recent-empty")).not.toBeInTheDocument();
    expect(screen.getByTestId("knowledge-count-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-categories-unavailable")).toBeInTheDocument();
  });

  it("shows partial/source failure messaging without fabricating zeros", async () => {
    asyncState.data!.documents = failed("documents down");
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-sources-all-failed")).toBeInTheDocument();
    expect(screen.queryByTestId("knowledge-count-complete")).not.toBeInTheDocument();
    expect(screen.getByText(/counts are not shown as zero/i)).toBeInTheDocument();
  });

  it("shows truncated coverage without definitive totals", async () => {
    asyncState.data!.documents = ok({
      items: [playbookDoc],
      total: 4,
      limit: 1,
      offset: 0,
    });
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-coverage-truncated")).toHaveTextContent(
      /only 1 of 4 knowledge documents are loaded/i,
    );
    expect(screen.getByTestId("knowledge-count-loaded")).toHaveTextContent(/1 of 4 documents loaded/i);
    expect(screen.queryByTestId("knowledge-count-complete")).not.toBeInTheDocument();
    expect(screen.getByTestId("knowledge-categories-truncated")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-category-presence-manually_stored")).toHaveTextContent(
      /count unavailable/i,
    );
  });

  it("supports loaded-page library search and states coverage limit", async () => {
    search.set("q", "pullback");
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-search-loaded-coverage")).toHaveTextContent(
      /covers only the loaded page/i,
    );
    expect(screen.getByTestId("knowledge-document-card-doc-playbook")).toBeInTheDocument();
    expect(screen.queryByTestId("knowledge-document-card-doc-journal")).not.toBeInTheDocument();
  });

  it("preserves query parameters through source filter links", async () => {
    search.set("q", "risk");
    search.set("document", "doc-playbook");
    search.set("source", "trading_playbook");
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-source-all")).toHaveAttribute(
      "href",
      "/knowledge?q=risk&document=doc-playbook",
    );
    expect(screen.getByTestId("knowledge-source-trade_journal")).toHaveAttribute(
      "href",
      "/knowledge?source=trade_journal&q=risk&document=doc-playbook",
    );
  });

  it("highlights a valid deep-linked document in the list", async () => {
    search.set("document", "doc-playbook");
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-document-card-doc-playbook")).toHaveClass(
      /ring-2/,
    );
    expect(screen.queryByTestId("knowledge-deeplink-only")).not.toBeInTheDocument();
    expect(screen.queryByTestId("knowledge-document-stale")).not.toBeInTheDocument();
  });

  it("keeps a deep-linked document visible when excluded by active filter", async () => {
    search.set("document", "doc-journal");
    search.set("source", "trading_playbook");
    asyncState.data!.documents = ok({
      items: [playbookDoc],
      total: 1,
      limit: 50,
      offset: 0,
    });
    listDocumentsMock.mockResolvedValueOnce({
      items: [playbookDoc, journalDoc, lessonDoc, strategyDoc],
      total: 4,
      limit: 50,
      offset: 0,
    });
    render(<KnowledgePage />);
    const deeplink = await screen.findByTestId("knowledge-deeplink-only");
    expect(within(deeplink).getByTestId("knowledge-document-card-doc-journal")).toBeInTheDocument();
    expect(within(deeplink).getByTestId("knowledge-filter-mismatch-notice")).toBeInTheDocument();
    expect(screen.queryByTestId("knowledge-document-card-doc-journal")).toBe(
      within(deeplink).getByTestId("knowledge-document-card-doc-journal"),
    );
  });

  it("shows stale message for invalid deep link and opens no unrelated record", async () => {
    search.set("document", "missing-doc");
    listDocumentsMock.mockResolvedValue({
      items: [playbookDoc],
      total: 1,
      limit: 50,
      offset: 0,
    });
    listChunksMock.mockResolvedValue({ items: [], total: 0, limit: 1, offset: 0 });
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-document-stale")).toHaveTextContent(/missing-doc/i);
    expect(screen.queryByTestId("knowledge-deeplink-only")).not.toBeInTheDocument();
    expect(screen.getByTestId("knowledge-document-card-doc-playbook")).toBeInTheDocument();
  });

  it("links stored relationships only when URI identifiers exist", async () => {
    render(<KnowledgePage />);
    const journalCard = await screen.findByTestId("knowledge-document-card-doc-journal");
    expect(within(journalCard).getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      "/journal?entry=entry-99",
    );
    const lessonCard = screen.getByTestId("knowledge-document-card-doc-lesson");
    expect(within(lessonCard).getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      "/lessons?candidate=lesson-42",
    );
    const strategyCard = screen.getByTestId("knowledge-document-card-doc-strategy");
    expect(within(strategyCard).getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      "/strategy-lab/strat-7",
    );
  });

  it("shows missing relationship messaging when URI identifiers are absent", async () => {
    asyncState.data!.documents = ok({
      items: [
        documentFixture({
          id: "doc-journal-missing",
          source_type: "trade_journal",
          source_uri: null,
        }),
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    render(<KnowledgePage />);
    const card = await screen.findByTestId("knowledge-document-card-doc-journal-missing");
    expect(
      within(card).getByTestId("knowledge-relationship-unavailable-journal"),
    ).toHaveTextContent(/no journal:\/\//i);
  });

  it("shows confirmed paper posture", async () => {
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-hub-page")).toBeInTheDocument();
    expect(screen.getByTestId("journal-hub-safety")).toHaveTextContent(/paper/i);
    expect(screen.getByTestId("knowledge-limitations")).toHaveTextContent(
      /runtime posture verified as paper-only/i,
    );
  });

  it("shows unverified posture wording when paper is not confirmed", async () => {
    safetyPosture.executionMode = "live";
    safetyPosture.realTradingEnabled = false;
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-limitations")).toHaveTextContent(
      /paper posture is not fully verified/i,
    );
  });

  it("uses mobile card layout structure without horizontal overflow wrappers", async () => {
    render(<KnowledgePage />);
    const page = await screen.findByTestId("knowledge-hub-page");
    expect(page.className).toMatch(/pb-24/);
    const grid = screen.getByTestId("knowledge-document-grid");
    expect(grid.className).toMatch(/grid-cols-1/);
    expect(grid.className).not.toMatch(/overflow-x/);
  });

  it("runs semantic search through the existing API", async () => {
    searchMock.mockResolvedValueOnce({
      query: "discipline",
      chunks: [
        {
          chunk_id: "c1",
          document_id: "doc-playbook",
          title: "Pullback playbook",
          chunk_ordinal: 0,
          source_type: "trading_playbook",
          content: "Wait for confirmation",
          score: 0.91,
        },
      ],
      citations: [],
    });
    render(<KnowledgePage />);
    fireEvent.change(await screen.findByTestId("knowledge-semantic-query-input"), {
      target: { value: "discipline" },
    });
    fireEvent.click(screen.getByTestId("knowledge-semantic-search-submit"));
    await waitFor(() => expect(searchMock).toHaveBeenCalled());
    expect(await screen.findByTestId("knowledge-semantic-results")).toHaveTextContent(
      /wait for confirmation/i,
    );
  });

  it("shows truncated-empty honesty when loaded page has no filter matches", async () => {
    search.set("q", "zzz-no-match");
    asyncState.data!.documents = ok({
      items: [playbookDoc],
      total: 8,
      limit: 1,
      offset: 0,
    });
    render(<KnowledgePage />);
    expect(await screen.findByTestId("knowledge-recent-truncated-empty")).toHaveTextContent(
      /not an all-clear/i,
    );
    expect(screen.queryByTestId("knowledge-recent-empty")).not.toBeInTheDocument();
  });

  it("expands document detail via chunks API", async () => {
    listChunksMock.mockResolvedValueOnce({
      items: [
        {
          id: "chunk-1",
          document_id: "doc-playbook",
          chunk_ordinal: 0,
          content: "Detail chunk body",
          metadata: { source_type: "trading_playbook" },
          created_at: "2026-07-20T10:00:00.000Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    render(<KnowledgePage />);
    fireEvent.click(await screen.findByTestId("knowledge-expand-doc-playbook"));
    expect(await screen.findByTestId("knowledge-detail-doc-playbook")).toHaveTextContent(
      /detail chunk body/i,
    );
  });
});
