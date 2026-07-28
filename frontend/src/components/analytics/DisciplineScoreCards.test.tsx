import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { DisciplineAnalyticsResponse, DisciplineScoreResult } from "@/lib/api/types";

import { DisciplineScoreCards } from "./DisciplineScoreCards";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

const proposal: DisciplineScoreResult = {
  score: 82,
  grade: "B",
  positive_behaviors: ["followed plan"],
  negative_behaviors: [],
  improvement_suggestions: ["slow down after losses"],
};

const learning: DisciplineAnalyticsResponse = {
  organization_id: "org",
  user_id: null,
  date_range: { start: null, end: null },
  min_sample: 5,
  sample_size: 12,
  insufficient_data: false,
  discipline_score: 71,
  discipline_grade: "C",
  discipline_breakdown: {},
  entry_breakdown: {},
  issue_frequency: {},
  positive_behaviors: [],
  negative_behaviors: [],
  improvement_suggestions: [],
};

describe("DisciplineScoreCards", () => {
  afterEach(() => cleanup());

  it("keeps the two discipline scores separate with distinct source links", () => {
    render(
      <DisciplineScoreCards
        proposalSource={ok(proposal)}
        learningSource={ok(learning)}
      />,
    );

    expect(screen.getByTestId("discipline-proposal-score")).toHaveTextContent("82");
    expect(screen.getByTestId("discipline-learning-score")).toHaveTextContent("71");
    expect(screen.getByTestId("discipline-proposal-source-label")).toHaveTextContent(
      /proposal-flow/i,
    );
    expect(screen.getByTestId("discipline-learning-source-label")).toHaveTextContent(
      /paper-validation session/i,
    );
    expect(screen.getByTestId("discipline-proposal-source-link")).toHaveAttribute("href", "/");
    expect(screen.getByTestId("discipline-learning-source-link")).toHaveAttribute(
      "href",
      "/learning-analytics",
    );
    expect(screen.getByTestId("discipline-learning-source-label")).toHaveTextContent(
      /never averaged or substituted/i,
    );
    expect(screen.getByTestId("discipline-proposal-score").textContent).not.toEqual(
      screen.getByTestId("discipline-learning-score").textContent,
    );
  });

  it("does not collapse when one discipline source fails", () => {
    const retryProposal = vi.fn();
    const retryLearning = vi.fn();
    render(
      <DisciplineScoreCards
        proposalSource={failed("proposal down")}
        learningSource={ok(learning)}
        onRetryProposal={retryProposal}
        onRetryLearning={retryLearning}
      />,
    );

    expect(screen.getByTestId("discipline-proposal-card-error")).toHaveTextContent(
      /proposal down/i,
    );
    expect(screen.getByTestId("discipline-learning-score")).toHaveTextContent("71");
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(retryProposal).toHaveBeenCalled();
  });

  it("shows unavailable score for insufficient learning data instead of substituting", () => {
    render(
      <DisciplineScoreCards
        proposalSource={ok(proposal)}
        learningSource={ok({ ...learning, insufficient_data: true, discipline_score: null })}
      />,
    );
    expect(screen.getByTestId("discipline-learning-score")).toHaveTextContent("—");
    expect(screen.getByTestId("discipline-proposal-score")).toHaveTextContent("82");
  });
});
