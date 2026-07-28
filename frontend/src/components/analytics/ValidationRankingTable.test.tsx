import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type {
  SetupRankingResponse,
  StrategyQualitySummaryResponse,
} from "@/lib/api/types";

import { ValidationRankingTable } from "./ValidationRankingTable";

function okRanking(data: SetupRankingResponse): SourceResult<SetupRankingResponse> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function okSq(
  data: StrategyQualitySummaryResponse,
): SourceResult<StrategyQualitySummaryResponse> {
  return { data, available: true, error: null, fallbackUsed: false };
}

const ranking: SetupRankingResponse = {
  organization_id: "org",
  user_id: null,
  date_range: {},
  min_sample: 5,
  dimension: "condition",
  note: "Ranking is observational — not an automation signal.",
  ranked: [
    { setup_key: "breakout", rank: 1, quality_score: 0.72, sample_size: 10 },
    { setup_key: "thin", rank: 2, quality_score: 0.9, sample_size: 2 },
  ],
};

const strategyQuality: StrategyQualitySummaryResponse = {
  organization_id: "org",
  user_id: null,
  date_range: {},
  min_sample: 5,
  note: "Read-only detector context.",
  total_detectors: 4,
  detectors_with_data: 2,
  total_results: 12,
  by_trust_tier: [{ trust_tier: "low", count: 2 }],
  by_verdict: [{ verdict: "watch", count: 2 }],
  ranked: [],
  warnings: [],
};

describe("ValidationRankingTable", () => {
  afterEach(() => cleanup());

  it("shows server ranking fields with sample-size honesty and links", () => {
    render(
      <ValidationRankingTable
        rankingSource={okRanking(ranking)}
        strategyQualitySource={okSq(strategyQuality)}
      />,
    );
    expect(screen.getByTestId("validation-ranking-row-breakout")).toHaveTextContent("breakout");
    expect(screen.getByTestId("validation-ranking-n-breakout")).toHaveTextContent("10");
    expect(screen.getByTestId("validation-ranking-row-thin")).toHaveTextContent(/insufficient data/);
    expect(screen.getByTestId("validation-ranking-n-thin")).toHaveTextContent("2");
    expect(screen.getByTestId("validation-ranking-note")).toHaveTextContent(/not an automation/i);
    expect(screen.getByTestId("validation-ranking-links")).toHaveTextContent("/strategy-quality");
    expect(screen.getByTestId("validation-ranking-links")).toHaveTextContent(
      "/paper-validation/run-sessions",
    );
    expect(screen.getByTestId("validation-sq-counts")).toHaveTextContent("2 of 4");
  });

  it("renders null-like missing scores as em dash, never zero", () => {
    render(
      <ValidationRankingTable
        rankingSource={okRanking({
          ...ranking,
          ranked: [{ setup_key: "x", rank: 1, quality_score: Number.NaN, sample_size: 6 }],
        })}
        strategyQualitySource={null}
        strategyQualityLoading
      />,
    );
    expect(screen.getByTestId("validation-ranking-row-x")).toHaveTextContent("—");
    expect(screen.getByTestId("validation-ranking-row-x").textContent).not.toMatch(/\b0\.00\b/);
  });

  it("keeps ranking error independent from strategy-quality success", () => {
    render(
      <ValidationRankingTable
        rankingSource={{
          data: null,
          available: false,
          error: "ranking down",
          fallbackUsed: false,
        }}
        strategyQualitySource={okSq(strategyQuality)}
      />,
    );
    expect(screen.getByTestId("validation-ranking-table-error")).toHaveTextContent(/ranking down/i);
    expect(screen.getByTestId("validation-sq-counts")).toBeInTheDocument();
  });
});
