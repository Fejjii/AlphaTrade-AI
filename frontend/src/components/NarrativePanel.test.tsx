import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NarrativePanel } from "@/components/NarrativePanel";
import type { NarrativeMetadata, TradingNarrativeDetail } from "@/lib/api/types";

const narrative: TradingNarrativeDetail = {
  summary: "Pullback review for BTC.",
  setup_interpretation: "HTF trend aligned.",
  evidence_explanation: "RSI neutral.",
  risk_explanation: "Risk level medium.",
  invalidation_explanation: "Close below stop.",
  next_decision_point: "Wait for approval.",
  caution_notes: ["Paper only."],
  limitations: ["Mock data."],
  paper_mode_disclaimer: "Paper mode only.",
  citations_used: ["playbook-1"],
};

describe("NarrativePanel", () => {
  afterEach(() => cleanup());

  it("renders narrative content", () => {
    render(<NarrativePanel narrative={narrative} />);
    expect(screen.getByText("Pullback review for BTC.")).toBeInTheDocument();
    expect(screen.getByText("playbook-1")).toBeInTheDocument();
  });

  it("renders LLM polish badge", () => {
    const meta: NarrativeMetadata = {
      source: "llm",
      provider: "mock-llm",
      model: "gpt-4o-mini",
      fallback_used: false,
      validation_passed: true,
    };
    render(<NarrativePanel narrative={narrative} narrativeMeta={meta} />);
    expect(screen.getByText("LLM polish")).toBeInTheDocument();
    expect(screen.getByText("mock-llm · gpt-4o-mini")).toBeInTheDocument();
  });

  it("renders deterministic fallback badge", () => {
    const meta: NarrativeMetadata = {
      source: "deterministic_fallback",
      provider: "mock-llm",
      model: "gpt-4o-mini",
      fallback_used: true,
      validation_passed: false,
    };
    render(<NarrativePanel narrative={narrative} narrativeMeta={meta} />);
    expect(screen.getByText("Deterministic fallback")).toBeInTheDocument();
  });

  it("handles empty optional arrays", () => {
    const minimal: TradingNarrativeDetail = {
      ...narrative,
      caution_notes: [],
      limitations: [],
      citations_used: [],
    };
    render(<NarrativePanel narrative={minimal} />);
    expect(screen.getByText("Paper mode only.")).toBeInTheDocument();
  });
});
