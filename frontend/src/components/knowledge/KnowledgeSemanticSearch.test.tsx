import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeSemanticSearch } from "@/components/knowledge/KnowledgeSemanticSearch";

vi.mock("@/lib/api", () => ({
  api: {
    knowledge: {
      search: vi.fn(),
    },
  },
}));

describe("KnowledgeSemanticSearch source sync (FP2-210)", () => {
  afterEach(() => cleanup());

  it("updates the source select when the URL-driven prop changes after mount", () => {
    const { rerender } = render(
      <KnowledgeSemanticSearch initialSourceFilter="all" />,
    );
    const select = screen.getByTestId("knowledge-semantic-source-select");
    expect(select).toHaveValue("all");

    fireEvent.change(select, { target: { value: "trade_journal" } });
    expect(select).toHaveValue("trade_journal");

    rerender(<KnowledgeSemanticSearch initialSourceFilter="risk_policy" />);
    expect(screen.getByTestId("knowledge-semantic-source-select")).toHaveValue(
      "risk_policy",
    );
  });
});

describe("Knowledge workspace retrieval", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("searches category sources and links passages to exact canonical documents", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api.knowledge.search).mockResolvedValue({
      query: "risk",
      chunks: [
        {
          document_id: "doc/1",
          chunk_id: "chunk-1",
          title: "Risk plan",
          source_type: "risk_policy",
          chunk_ordinal: 2,
          content: "Size risk first.",
          score: 0.9,
          section_title: "Sizing",
          page_number: 3,
        },
      ],
      citations: [],
      degraded: true,
    });
    render(
      <KnowledgeSemanticSearch
        initialSourceFilter="all"
        workspaceSources={["risk_policy"]}
      />,
    );
    expect(screen.queryByLabelText("Source types")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "risk" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Size risk first.")).toBeInTheDocument();
    expect(api.knowledge.search).toHaveBeenCalledWith({
      query: "risk",
      top_k: 5,
      source_types: ["risk_policy"],
    });
    expect(screen.getByRole("link", { name: "Risk plan" })).toHaveAttribute(
      "href",
      "/knowledge?document=doc%2F1&source=risk_policy",
    );
    expect(
      screen.getByText(/Source: risk policy · passage 2 · Sizing · page 3/),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("knowledge-search-degraded-note"),
    ).toBeInTheDocument();
  });

  it("discards in-flight retrieval when the category changes", async () => {
    const { api } = await import("@/lib/api");
    let resolve!: (
      value: Awaited<ReturnType<typeof api.knowledge.search>>,
    ) => void;
    vi.mocked(api.knowledge.search).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const { rerender } = render(
      <KnowledgeSemanticSearch
        initialSourceFilter="all"
        workspaceSources={["risk_policy"]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "risk" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByText("Searching stored knowledge…")).toBeInTheDocument();
    rerender(
      <KnowledgeSemanticSearch
        initialSourceFilter="all"
        workspaceSources={["trading_playbook"]}
      />,
    );
    const { act } = await import("@testing-library/react");
    await act(async () =>
      resolve({ query: "old risk results", chunks: [], citations: [] }),
    );
    expect(
      screen.queryByTestId("knowledge-semantic-results"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
  });

  it("clears results when a new query is typed and shows retrieval errors", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api.knowledge.search)
      .mockResolvedValueOnce({ query: "risk", chunks: [], citations: [] })
      .mockRejectedValueOnce(new Error("Search unavailable"));
    render(
      <KnowledgeSemanticSearch
        initialSourceFilter="all"
        workspaceSources={[]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "risk" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByText("No chunks matched");
    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "entry" },
    });
    expect(screen.queryByText("No chunks matched")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Search unavailable")).toBeInTheDocument();
  });
});
