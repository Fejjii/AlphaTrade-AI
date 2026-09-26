import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AGENT_REFLECTION_CONTRACT } from "@/components/journal/trader-journal";
import { TraderJournalView } from "@/components/journal/TraderJournalView";
import { failedSource, okSource } from "@/components/workflows/sourceResult";
import type {
  CanonicalJournalTradeListItem,
  CoachingPrompt,
  JournalEntry,
  LessonCandidate,
} from "@/lib/api/types";

describe("Trader journal", () => {
  afterEach(() => cleanup());

  it("shows trades, reasoning, lessons, coaching prompts, and the reflection gap", () => {
    render(
      <TraderJournalView
        data={{
          trades: okSource({
            items: [
              {
                id: "t1",
                symbol: "BTCUSDT",
                direction: "long",
                result: "win",
                thesis: "Held the higher-timeframe level",
                net_pnl: "15",
                strategy_label: "HTF Pullback",
              } as CanonicalJournalTradeListItem,
            ],
          }),
          entries: okSource({
            items: [
              {
                id: "e1",
                symbol: "ETHUSDT",
                direction: "short",
                result: "loss",
                entry_rationale: "Faded the first push",
                pnl: "-4",
                mistakes: ["Chased"],
                lessons: "Wait for the close",
                strategy_id: "s1",
              } as unknown as JournalEntry,
            ],
          }),
          lessons: okSource({
            items: [{ id: "l1", lesson_text: "Do not chase", mistake_type: "late_entry", status: "accepted" } as LessonCandidate],
          }),
          coaching: okSource({
            items: [{ signature: "p1", prompt_text: "What would have invalidated this?" } as CoachingPrompt],
          }),
        }}
      />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Journal" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Record a trade" })).toHaveAttribute(
      "href",
      "/journal?view=record",
    );
    expect(screen.getByTestId("journal-trades")).toHaveTextContent("Held the higher-timeframe level");
    expect(screen.getByTestId("journal-trades")).toHaveTextContent("HTF Pullback");
    expect(screen.getByTestId("journal-entries")).toHaveTextContent("Faded the first push");
    expect(screen.getByTestId("journal-entries")).toHaveTextContent("Chased");
    expect(screen.getByTestId("journal-entries")).toHaveTextContent("Wait for the close");
    expect(screen.getByTestId("journal-lessons")).toHaveTextContent("Do not chase");
    expect(screen.getByTestId("journal-coaching-prompts")).toHaveTextContent(
      "not stored Agent reflections",
    );
    expect(screen.getByTestId("journal-agent-reflections")).toHaveTextContent(AGENT_REFLECTION_CONTRACT);
  });

  it("does not turn a failed trade source into an empty journal", () => {
    render(
      <TraderJournalView
        data={{
          trades: failedSource("down"),
          entries: failedSource("down"),
          lessons: failedSource("down"),
          coaching: failedSource("down"),
        }}
      />,
    );
    expect(screen.getByTestId("journal-trades")).toHaveTextContent("Trades unavailable");
    expect(screen.queryByText("No canonical trades yet.")).not.toBeInTheDocument();
  });
});
