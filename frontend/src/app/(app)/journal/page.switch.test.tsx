import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import JournalPage from "./page";

const search = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => search,
}));

vi.mock("@/components/journal/JournalHubScreen", () => ({
  JournalHubScreen: () => <div>Hub record</div>,
}));

vi.mock("@/components/journal/TraderJournalScreen", () => ({
  TraderJournalScreen: () => <div>Trader journal</div>,
}));

afterEach(() => {
  cleanup();
  for (const key of [...search.keys()]) search.delete(key);
});

describe("Journal page switch", () => {
  it("opens the trader journal by default", () => {
    render(<JournalPage />);
    expect(screen.getByText("Trader journal")).toBeInTheDocument();
  });

  it("keeps the record hub for view=record and deep links", () => {
    search.set("view", "record");
    const { rerender } = render(<JournalPage />);
    expect(screen.getByText("Hub record")).toBeInTheDocument();

    search.delete("view");
    search.set("proposal_id", "prop-1");
    rerender(<JournalPage />);
    expect(screen.getByText("Hub record")).toBeInTheDocument();
  });
});
