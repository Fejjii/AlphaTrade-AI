import { describe, expect, it } from "vitest";

import {
  buildDeepLinkExclusionNotices,
  categoryKindForSourceFilter,
  filterDocumentsByLibraryQuery,
  knowledgeCategory,
  parseStoredSourceUri,
  resolveKnowledgeRelationships,
} from "@/components/knowledge/knowledgeDisplay";
import type { RagDocument } from "@/lib/api/types";

function doc(overrides: Partial<RagDocument> & { id: string }): RagDocument {
  return {
    title: "Sample",
    source_type: "general_note",
    version: 1,
    created_at: "2026-07-20T10:00:00.000Z",
    updated_at: "2026-07-20T10:00:00.000Z",
    ...overrides,
  };
}

describe("knowledgeDisplay", () => {
  it("classifies categories from stored source_type only", () => {
    expect(knowledgeCategory(doc({ id: "1", source_type: "review_note" })).kind).toBe(
      "accepted_lesson",
    );
    expect(knowledgeCategory(doc({ id: "2", source_type: "strategy_template" })).kind).toBe(
      "strategy_or_rule",
    );
    expect(knowledgeCategory(doc({ id: "3", source_type: "trade_journal" })).kind).toBe(
      "journal_derived",
    );
    expect(knowledgeCategory(doc({ id: "4", source_type: "trading_playbook" })).kind).toBe(
      "manually_stored",
    );
  });

  it("parses only explicit stored URI schemes", () => {
    expect(parseStoredSourceUri("journal://entry-1")).toEqual({
      kind: "journal",
      id: "entry-1",
    });
    expect(parseStoredSourceUri("lesson://lesson-1")).toEqual({
      kind: "lesson",
      id: "lesson-1",
    });
    expect(parseStoredSourceUri("strategy://strat-1/v2")).toEqual({
      kind: "strategy",
      id: "strat-1",
    });
    expect(parseStoredSourceUri("https://example.com/journal/1")).toEqual({
      kind: null,
      id: null,
    });
  });

  it("resolves relationship links only when identifiers exist", () => {
    const withLesson = resolveKnowledgeRelationships(
      doc({ id: "d1", source_type: "review_note", source_uri: "lesson://lesson-9" }),
    );
    expect(withLesson).toEqual([
      {
        kind: "lesson",
        label: "Related lesson",
        id: "lesson-9",
        href: "/lessons?candidate=lesson-9",
      },
    ]);

    const missingJournal = resolveKnowledgeRelationships(
      doc({ id: "d2", source_type: "trade_journal", source_uri: null }),
    );
    expect(missingJournal[0]?.href).toBeNull();
    expect(missingJournal[0]?.unavailableReason).toMatch(/journal:\/\//i);
  });

  it("never infers a journal id from a lesson URI", () => {
    const links = resolveKnowledgeRelationships(
      doc({ id: "d3", source_type: "review_note", source_uri: "lesson://lesson-1" }),
    );
    expect(links.some((link) => link.kind === "journal" && link.href)).toBe(false);
  });

  it("filters loaded-page library search by title and uri", () => {
    const items = [
      doc({ id: "a", title: "Pullback playbook", source_uri: "manual://a" }),
      doc({ id: "b", title: "Other", source_uri: "journal://entry-99" }),
    ];
    expect(filterDocumentsByLibraryQuery(items, "pullback").map((item) => item.id)).toEqual([
      "a",
    ]);
    expect(filterDocumentsByLibraryQuery(items, "entry-99").map((item) => item.id)).toEqual([
      "b",
    ]);
  });

  it("maps source filters to category kinds", () => {
    expect(categoryKindForSourceFilter("all")).toBeNull();
    expect(categoryKindForSourceFilter("review_note")).toBe("accepted_lesson");
    expect(categoryKindForSourceFilter("trade_journal")).toBe("journal_derived");
    expect(categoryKindForSourceFilter("strategy_template")).toBe("strategy_or_rule");
  });

  it("describes deep-link exclusions without mislabeling query as source filter", () => {
    const sample = doc({ id: "doc-1", title: "Alpha", source_type: "trade_journal" });
    const queryOnly = buildDeepLinkExclusionNotices({
      document: sample,
      inActiveSourcePage: true,
      visibleInLibraryResults: false,
      sourceFilter: "all",
      libraryQuery: "zzz",
    });
    expect(queryOnly.map((item) => item.kind)).toEqual(["library_query"]);
    expect(queryOnly[0]?.message).toMatch(/library search query/i);
    expect(queryOnly[0]?.message).not.toMatch(/source filter/i);

    const sourceOnly = buildDeepLinkExclusionNotices({
      document: sample,
      inActiveSourcePage: false,
      visibleInLibraryResults: false,
      sourceFilter: "trading_playbook",
      libraryQuery: "",
    });
    expect(sourceOnly.map((item) => item.kind)).toEqual([
      "outside_loaded_page",
      "source_filter",
    ]);

    const both = buildDeepLinkExclusionNotices({
      document: sample,
      inActiveSourcePage: false,
      visibleInLibraryResults: false,
      sourceFilter: "trading_playbook",
      libraryQuery: "zzz",
    });
    expect(both.map((item) => item.kind)).toEqual([
      "outside_loaded_page",
      "source_filter_and_library_query",
    ]);
  });
});
