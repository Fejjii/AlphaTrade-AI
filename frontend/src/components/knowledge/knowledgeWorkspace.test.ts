import { describe, expect, it } from "vitest";
import { parseWorkspaceQuery, workspaceHref } from "./knowledgeWorkspace";

describe("Knowledge workspace URL views", () => {
  it("preserves legacy source and query deep links", () => {
    expect(
      parseWorkspaceQuery(
        new URLSearchParams("source=trade_journal&document=entry-doc&q=Risk"),
      ),
    ).toMatchObject({
      sources: ["trade_journal"],
      documentId: "entry-doc",
      query: "Risk",
      offset: 0,
    });
  });
  it("uses category sources and rejects invalid offsets", () => {
    for (const offset of ["-1", "NaN", "0.5", "9007199254740992"])
      expect(
        parseWorkspaceQuery(
          new URLSearchParams(`category=lessons&offset=${offset}`),
        ),
      ).toMatchObject({
        sources: ["review_note", "mistakes_database"],
        offset: 0,
      });
  });
  it("keeps unknown categories in the all-knowledge view", () => {
    expect(
      parseWorkspaceQuery(new URLSearchParams("category=not-real")),
    ).toMatchObject({ category: undefined, sources: [] });
  });
  it("resets legacy source and offset when selecting a category", () => {
    expect(
      workspaceHref(
        new URLSearchParams(
          "source=risk_policy&offset=50&document=doc%2F1&q=risk",
        ),
        { category: "playbook" },
      ),
    ).toBe("/knowledge?document=doc%2F1&q=risk&category=playbook");
  });
});
