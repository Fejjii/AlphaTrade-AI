import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PaginatedRagDocuments, RagDocument } from "@/lib/api/types";
import KnowledgePage from "./page";

const search = new URLSearchParams();
const mocks = vi.hoisted(() => ({
  documents: vi.fn(),
  chunks: vi.fn(),
  search: vi.fn(),
  ingest: vi.fn(),
  candidate: vi.fn(),
  lessons: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));
vi.mock("@/lib/api", () => ({
  api: {
    knowledge: {
      listDocuments: mocks.documents,
      listChunks: mocks.chunks,
      search: mocks.search,
      ingest: mocks.ingest,
    },
    lessons: { getCandidate: mocks.candidate, listCandidates: mocks.lessons },
  },
}));
const doc = (
  id: string,
  source_type = "trading_playbook",
  source_uri: string | null = null,
): RagDocument => ({
  id,
  source_type,
  source_uri,
  title: `Knowledge ${id}`,
  version: 1,
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-01T10:00:00Z",
});
const page = (
  items: RagDocument[],
  total = items.length,
  offset = 0,
): PaginatedRagDocuments => ({ items, total, limit: 50, offset });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  for (const key of [...search.keys()]) search.delete(key);
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.documents.mockResolvedValue(page([doc("playbook")]));
  mocks.chunks.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  mocks.lessons.mockResolvedValue({
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
  });
  mocks.search.mockResolvedValue({ query: "risk", chunks: [], citations: [] });
  mocks.ingest.mockResolvedValue({
    document_id: "saved",
    chunk_count: 1,
    duplicate: false,
  });
});
afterEach(cleanup);

describe("Knowledge trader workspace", () => {
  it("keeps five categories visible while documents load", async () => {
    const pending = deferred<PaginatedRagDocuments>();
    mocks.documents.mockReturnValue(pending.promise);
    render(<KnowledgePage />);
    expect(
      screen.getByText("Loading Knowledge workspace…"),
    ).toBeInTheDocument();
    const nav = screen.getByRole("navigation", {
      name: "Knowledge categories",
    });
    for (const label of [
      "Trading Rules",
      "Playbook",
      "Lessons",
      "Strategy Research",
      "Market Observations",
    ])
      expect(
        within(nav).getByRole("link", { name: label }),
      ).toBeInTheDocument();
    expect(
      screen.queryByTestId("knowledge-store-panel"),
    ).not.toBeInTheDocument();
    await act(async () => pending.resolve(page([])));
  });
  it.each([
    ["rules", ["risk_policy"]],
    ["playbook", ["trading_playbook"]],
    ["lessons", ["review_note", "mistakes_database"]],
    ["research", ["strategy_template"]],
    ["observations", ["general_note", "trade_journal"]],
  ])("loads %s through existing filters", async (category, sources) => {
    search.set("category", category);
    mocks.documents.mockImplementation(({ source_type }) =>
      Promise.resolve(page([doc(source_type, source_type)])),
    );
    render(<KnowledgePage />);
    await screen.findByTestId("knowledge-document-grid");
    expect(
      mocks.documents.mock.calls.map(([params]) => params.source_type),
    ).toEqual(sources);
    expect(
      screen
        .getByRole("navigation", { name: "Knowledge categories" })
        .querySelector('[aria-current="page"]'),
    ).toHaveAttribute("href", `/knowledge?category=${category}`);
  });
  it("preserves query and document links and resets pagination on category change", async () => {
    search.set("q", "Knowledge");
    search.set("document", "playbook");
    search.set("offset", "50");
    render(<KnowledgePage />);
    expect(
      within(
        screen.getByRole("navigation", { name: "Knowledge categories" }),
      ).getByRole("link", { name: "Trading Rules" }),
    ).toHaveAttribute(
      "href",
      "/knowledge?q=Knowledge&document=playbook&category=rules",
    );
    await screen.findByTestId("knowledge-document-grid");
  });
  it("shows provenance and retrieves chunks only on expansion", async () => {
    mocks.documents.mockResolvedValue(
      page([doc("strategy", "strategy_template", "strategy://setup-1/v2")]),
    );
    mocks.chunks.mockResolvedValue({
      items: [
        {
          id: "chunk",
          chunk_ordinal: 0,
          content: "Wait for confirmation",
          section_title: "Entry",
        },
      ],
      total: 1,
    });
    render(<KnowledgePage />);
    await screen.findByTestId("knowledge-document-card-strategy");
    expect(screen.getByTestId("knowledge-source-uri")).toHaveTextContent(
      "strategy://setup-1/v2",
    );
    expect(
      screen.getByRole("link", { name: "Related strategy: open" }),
    ).toHaveAttribute("href", "/strategy-lab/setup-1");
    expect(mocks.chunks).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("knowledge-expand-strategy"));
    await screen.findByText("Wait for confirmation");
    expect(mocks.chunks).toHaveBeenCalledWith({
      document_id: "strategy",
      limit: 50,
      offset: 0,
    });
    fireEvent.click(screen.getByTestId("knowledge-expand-strategy"));
    expect(screen.queryByText("Wait for confirmation")).not.toBeInTheDocument();
  });
  it("retries unavailable chunks and states truncated coverage", async () => {
    mocks.chunks
      .mockRejectedValueOnce(new Error("chunks offline"))
      .mockResolvedValueOnce({
        items: [{ id: "c", chunk_ordinal: 1, content: "Risk rule" }],
        total: 2,
      });
    render(<KnowledgePage />);
    fireEvent.click(await screen.findByTestId("knowledge-expand-playbook"));
    fireEvent.click(
      await screen.findByTestId("knowledge-detail-retry-playbook"),
    );
    expect(
      await screen.findByTestId("knowledge-detail-truncated-playbook"),
    ).toHaveTextContent("Showing 1 of 2 chunks");
  });
  it("shows an honest empty state", async () => {
    mocks.documents.mockResolvedValue(page([]));
    render(<KnowledgePage />);
    expect(await screen.findByText("No knowledge yet")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("retries source failures without inventing empty counts", async () => {
    mocks.documents
      .mockRejectedValueOnce(new Error("documents offline"))
      .mockResolvedValue(page([doc("recovered")]));
    render(<KnowledgePage />);
    await screen.findByText("Knowledge unavailable: documents offline");
    expect(screen.queryByText(/0 stored/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await screen.findByText("Knowledge recovered");
  });
  it("shows partial multi-source results alongside failures", async () => {
    search.set("category", "observations");
    mocks.documents.mockImplementation(({ source_type }) =>
      source_type === "general_note"
        ? Promise.resolve(page([doc("observation", source_type)]))
        : Promise.reject(new Error("journal unavailable")),
    );
    render(<KnowledgePage />);
    await screen.findByText("Knowledge observation");
    expect(
      screen.getByText("trade journal unavailable: journal unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText(/partial coverage/)).toBeInTheDocument();
    expect(screen.queryByText(/1 stored/)).not.toBeInTheDocument();
  });
  it("paginates within the category without claiming an empty corpus", async () => {
    search.set("category", "rules");
    mocks.documents.mockResolvedValue(page([doc("rule", "risk_policy")], 100));
    const { rerender } = render(<KnowledgePage />);
    expect(await screen.findByRole("link", { name: "Next" })).toHaveAttribute(
      "href",
      "/knowledge?category=rules&offset=50",
    );
    mocks.documents.mockResolvedValue(page([], 100, 50));
    search.set("offset", "50");
    rerender(<KnowledgePage />);
    await screen.findByText("No documents on this page");
    expect(screen.getByRole("link", { name: "Previous" })).toHaveAttribute(
      "href",
      "/knowledge?category=rules",
    );
    expect(mocks.documents).toHaveBeenLastCalledWith({
      source_type: "risk_policy",
      limit: 50,
      offset: 50,
    });
  });
  it("ignores older responses after category changes", async () => {
    const old = deferred<PaginatedRagDocuments>();
    mocks.documents
      .mockReturnValueOnce(old.promise)
      .mockResolvedValue(page([doc("new-rules", "risk_policy")]));
    const { rerender } = render(<KnowledgePage />);
    search.set("category", "rules");
    rerender(<KnowledgePage />);
    await screen.findByText("Knowledge new-rules");
    await act(async () => old.resolve(page([doc("stale")])));
    expect(screen.queryByText("Knowledge stale")).not.toBeInTheDocument();
  });
  it("opens exact linked documents beyond the first page", async () => {
    search.set("document", "older");
    search.set("category", "rules");
    mocks.documents.mockImplementation(({ limit, offset }) =>
      limit === 50
        ? Promise.resolve(page([]))
        : offset === 0
          ? Promise.resolve(page([doc("unrelated")], 201))
          : Promise.resolve(page([doc("older")], 201, 200)),
    );
    render(<KnowledgePage />);
    await screen.findByTestId("knowledge-document-card-older");
    expect(
      screen.queryByTestId("knowledge-document-card-unrelated"),
    ).not.toBeInTheDocument();
    expect(mocks.documents).toHaveBeenCalledWith({ limit: 200, offset: 200 });
  });
  it("reports stale links without opening unrelated records", async () => {
    search.set("document", "missing");
    render(<KnowledgePage />);
    await screen.findByText("This document is no longer available.");
    expect(mocks.chunks).not.toHaveBeenCalled();
  });
  it("allows collapsing a deep-linked document", async () => {
    search.set("document", "playbook");
    render(<KnowledgePage />);
    await screen.findByTestId("knowledge-detail-empty-playbook");
    fireEvent.click(screen.getByTestId("knowledge-expand-playbook"));
    expect(
      screen.queryByTestId("knowledge-detail-empty-playbook"),
    ).not.toBeInTheDocument();
  });
  it.each(["risk_policy", "trading_playbook", "general_note"])(
    "saves %s with canonical ingestion and refreshes",
    async (source) => {
      render(<KnowledgePage />);
      await screen.findByText("Knowledge playbook");
      fireEvent.click(screen.getByRole("button", { name: "Add note" }));
      expect(screen.getByRole("button", { name: "Save note" })).toBeDisabled();
      fireEvent.change(screen.getByLabelText("Category"), {
        target: { value: source },
      });
      fireEvent.change(screen.getByLabelText("Title"), {
        target: { value: " My rule " },
      });
      fireEvent.change(screen.getByLabelText("Document text"), {
        target: { value: " Wait for confirmation " },
      });
      fireEvent.click(screen.getByRole("button", { name: "Save note" }));
      await screen.findByTestId("knowledge-ingest-success");
      expect(mocks.ingest).toHaveBeenCalledWith({
        title: "My rule",
        text: "Wait for confirmation",
        source_type: source,
      });
      expect(mocks.documents).toHaveBeenCalledTimes(2);
    },
  );
  it("defaults a new note to the active Trading Rules category", async () => {
    search.set("category", "rules");
    render(<KnowledgePage />);
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(screen.getByLabelText("Category")).toHaveValue("risk_policy");
    await screen.findByTestId("knowledge-document-grid");
  });

  it("keeps existing-source empty states scoped to their source", async () => {
    search.set("source", "risk_policy");
    mocks.documents.mockResolvedValue(page([]));
    render(<KnowledgePage />);
    await screen.findByText("No risk policy yet");
    expect(screen.queryByText("No knowledge yet")).not.toBeInTheDocument();
  });

  it("retains drafts on ingestion errors", async () => {
    mocks.ingest.mockRejectedValue(new Error("save failed"));
    render(<KnowledgePage />);
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Rule" },
    });
    fireEvent.change(screen.getByLabelText("Document text"), {
      target: { value: "Draft rule" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save note" }));
    expect(
      await screen.findByTestId("knowledge-ingest-error"),
    ).toHaveTextContent("save failed");
    expect(screen.getByLabelText("Document text")).toHaveValue("Draft rule");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save note" })).toBeEnabled(),
    );
  });
});
