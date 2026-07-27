import { describe, expect, it } from "vitest";

import {
  assessPortfolioHistoryCoverage,
  portfolioSourceCoverage,
} from "@/components/portfolio/portfolioHistoryCoverage";
import { samplePortfolio } from "@/app/(app)/portfolio/sample-portfolio";

describe("portfolioHistoryCoverage", () => {
  it("marks a successful non-paginated portfolio source as complete even with empty equity", () => {
    expect(portfolioSourceCoverage(true)).toBe("complete");
    expect(portfolioSourceCoverage(false)).toBeNull();
  });

  it("treats empty equity and daily series as confirmed empty, not truncated", () => {
    const coverage = assessPortfolioHistoryCoverage({
      ...samplePortfolio,
      equity_curve: [],
      daily_series: [],
      account: { ...samplePortfolio.account, limitations: [] },
    });
    expect(coverage.kind).toBe("empty");
    expect(coverage.message).toMatch(/confirmed empty/i);
    expect(coverage.message).not.toMatch(/truncated/i);
  });

  it("marks history partial only when existing equity points lack valid timestamps", () => {
    const coverage = assessPortfolioHistoryCoverage({
      ...samplePortfolio,
      equity_curve: [
        {
          index: 0,
          timestamp: null,
          equity: "10000",
          cumulative_realized_pnl: "0",
          unrealized_pnl: null,
          event: "start",
        },
      ],
    });
    expect(coverage.kind).toBe("partial_timestamps");
    expect(coverage.missingEquityTimestamps).toBe(1);
  });

  it("surfaces backend limitations without inventing truncated API coverage", () => {
    const coverage = assessPortfolioHistoryCoverage({
      ...samplePortfolio,
      account: {
        ...samplePortfolio.account,
        limitations: ["Methodology excludes funding on open trades"],
      },
    });
    expect(coverage.kind).toBe("limitations");
    expect(coverage.limitations).toContain("Methodology excludes funding on open trades");
  });

  it("reports complete when series and timestamps are valid without limitations", () => {
    const coverage = assessPortfolioHistoryCoverage(samplePortfolio);
    expect(coverage.kind).toBe("complete");
  });
});
