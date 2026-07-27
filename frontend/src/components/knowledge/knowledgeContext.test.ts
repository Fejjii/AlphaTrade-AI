import { describe, expect, it } from "vitest";

import {
  knowledgeDocumentHref,
  knowledgeLibrarySearchHref,
  knowledgeSourceFilterHref,
  parseKnowledgeQuery,
} from "@/components/knowledge/knowledgeContext";

describe("knowledgeContext", () => {
  it("parses document, source, and library query params", () => {
    const params = new URLSearchParams({
      document: "doc-1",
      source: "trade_journal",
      q: "pullback",
    });
    expect(parseKnowledgeQuery(params)).toEqual({
      documentId: "doc-1",
      sourceFilter: "trade_journal",
      query: "pullback",
    });
  });

  it("falls back invalid source filters to all", () => {
    const params = new URLSearchParams({ source: "not-a-type" });
    expect(parseKnowledgeQuery(params).sourceFilter).toBe("all");
  });

  it("preserves document and query across source filter hrefs", () => {
    expect(
      knowledgeSourceFilterHref("review_note", {
        documentId: "doc-1",
        query: "risk",
      }),
    ).toBe("/knowledge?source=review_note&q=risk&document=doc-1");
  });

  it("builds document and library search hrefs without dropping filters", () => {
    expect(
      knowledgeDocumentHref("doc-9", {
        sourceFilter: "strategy_template",
        query: "rule",
      }),
    ).toBe("/knowledge?source=strategy_template&q=rule&document=doc-9");
    expect(
      knowledgeLibrarySearchHref("breakout", {
        sourceFilter: "trading_playbook",
        documentId: "doc-2",
      }),
    ).toBe("/knowledge?source=trading_playbook&q=breakout&document=doc-2");
  });
});
