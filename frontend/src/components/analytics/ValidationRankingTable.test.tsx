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

function rankingForDimension(
  dimension: SetupRankingResponse["dimension"],
  ranked: SetupRankingResponse["ranked"],
): SetupRankingResponse {
  return {
    organization_id: "org",
    user_id: null,
    date_range: {},
    min_sample: 5,
    dimension,
    note: "Ranking is observational — not an automation signal.",
    ranked,
  };
}

describe("ValidationRankingTable", () => {
  afterEach(() => cleanup());

  it("uses condition dimension semantics from the ranking response", () => {
    render(
      <ValidationRankingTable
        rankingSource={okRanking(
          rankingForDimension("condition", [
            { setup_key: "breakout", rank: 1, quality_score: 0.72, sample_size: 10 },
            { setup_key: "pullback", rank: 2, quality_score: 0.61, sample_size: 8 },
          ]),
        )}
        strategyQualitySource={okSq(strategyQuality)}
      />,
    );
    expect(screen.getByTestId("validation-ranking-table")).toHaveTextContent(
      "Validation ranking by Condition",
    );
    expect(screen.getByTestId("validation-ranking-identity-header")).toHaveTextContent("Condition");
    expect(screen.getByTestId("validation-ranking-caption")).toHaveTextContent(
      "Learning-analytics setup ranking by condition",
    );
    expect(screen.getByTestId("validation-ranking-table")).toHaveTextContent("ranked groups");
    expect(screen.getByTestId("validation-ranking-gate-breakout")).toHaveTextContent("≥ 5");
    expect(screen.getByTestId("validation-ranking-row-breakout")).not.toHaveTextContent(
      /insufficient/i,
    );
    expect(screen.queryByRole("link", { name: "breakout" })).not.toBeInTheDocument();
  });

  it("uses symbol dimension semantics without calling values detector conditions", () => {
    render(
      <ValidationRankingTable
        rankingSource={okRanking(
          rankingForDimension("symbol", [
            { setup_key: "BTCUSDT", rank: 1, quality_score: 0.55, sample_size: 12 },
          ]),
        )}
        strategyQualitySource={okSq(strategyQuality)}
      />,
    );
    expect(screen.getByTestId("validation-ranking-table")).toHaveTextContent(
      "Validation ranking by Symbol",
    );
    expect(screen.getByTestId("validation-ranking-identity-header")).toHaveTextContent("Symbol");
    expect(screen.getByTestId("validation-ranking-caption")).toHaveTextContent(
      "Learning-analytics setup ranking by symbol",
    );
    expect(screen.getByTestId("validation-ranking-row-BTCUSDT")).toHaveTextContent("BTCUSDT");
    expect(screen.getByTestId("validation-ranking-row-BTCUSDT")).not.toHaveTextContent(
      /condition|detector/i,
    );
  });

  it("shows general context links without row-specific strategy-quality links", () => {
    render(
      <ValidationRankingTable
        rankingSource={okRanking(
          rankingForDimension("condition", [
            { setup_key: "breakout", rank: 1, quality_score: 0.72, sample_size: 10 },
          ]),
        )}
        strategyQualitySource={okSq(strategyQuality)}
      />,
    );
    expect(screen.getByTestId("validation-ranking-links")).toHaveTextContent("/strategy-quality");
    expect(
      screen.getByTestId("validation-ranking-links").querySelector('a[href="/strategy-quality"]'),
    ).toBeTruthy();
    expect(screen.queryByRole("link", { name: "breakout" })).not.toBeInTheDocument();
  });

  it("renders null-like missing scores as em dash, never zero", () => {
    render(
      <ValidationRankingTable
        rankingSource={okRanking(
          rankingForDimension("condition", [
            { setup_key: "x", rank: 1, quality_score: Number.NaN, sample_size: 6 },
          ]),
        )}
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
