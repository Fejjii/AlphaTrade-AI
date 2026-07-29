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
    const { rerender } = render(<KnowledgeSemanticSearch initialSourceFilter="all" />);
    const select = screen.getByTestId("knowledge-semantic-source-select");
    expect(select).toHaveValue("all");

    fireEvent.change(select, { target: { value: "trade_journal" } });
    expect(select).toHaveValue("trade_journal");

    rerender(<KnowledgeSemanticSearch initialSourceFilter="risk_policy" />);
    expect(screen.getByTestId("knowledge-semantic-source-select")).toHaveValue("risk_policy");
  });
});
