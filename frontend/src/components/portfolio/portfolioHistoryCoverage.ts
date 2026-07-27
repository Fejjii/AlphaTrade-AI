import { isValidTimestamp } from "@/components/portfolio/portfolioMetricDisplay";
import type { PaperPortfolioResponse } from "@/lib/api/types";

export type PortfolioHistoryCoverageKind =
  | "complete"
  | "empty"
  | "partial_timestamps"
  | "limitations";

export type PortfolioHistoryCoverage = {
  kind: PortfolioHistoryCoverageKind;
  missingEquityTimestamps: number;
  equityEmpty: boolean;
  dailyEmpty: boolean;
  limitations: string[];
  message: string;
};

/**
 * Portfolio responses are not paginated pages.
 * An empty equity/daily series means confirmed empty history, not truncated API coverage.
 * Partial applies only when existing points have invalid/missing timestamps.
 */
export function assessPortfolioHistoryCoverage(
  portfolio: PaperPortfolioResponse,
): PortfolioHistoryCoverage {
  const equity = portfolio.equity_curve;
  const daily = portfolio.daily_series;
  const limitations = portfolio.account.limitations;
  const missingEquityTimestamps = equity.filter(
    (point) => !isValidTimestamp(point.timestamp),
  ).length;
  const equityEmpty = equity.length === 0;
  const dailyEmpty = daily.length === 0;

  if (missingEquityTimestamps > 0) {
    return {
      kind: "partial_timestamps",
      missingEquityTimestamps,
      equityEmpty,
      dailyEmpty,
      limitations,
      message: `Partial chart history — ${missingEquityTimestamps} equity point(s) lack valid timestamps.`,
    };
  }

  if (equityEmpty && dailyEmpty) {
    return {
      kind: "empty",
      missingEquityTimestamps: 0,
      equityEmpty,
      dailyEmpty,
      limitations,
      message:
        "Confirmed empty history for the selected range — no equity or daily series points were returned.",
    };
  }

  if (limitations.length > 0) {
    return {
      kind: "limitations",
      missingEquityTimestamps: 0,
      equityEmpty,
      dailyEmpty,
      limitations,
      message: "History series loaded with explicit backend limitations.",
    };
  }

  return {
    kind: "complete",
    missingEquityTimestamps: 0,
    equityEmpty,
    dailyEmpty,
    limitations,
    message: "History coverage appears complete for the loaded series.",
  };
}

/** Non-paginated portfolio source coverage: successful load is complete, never truncated for empty curves. */
export function portfolioSourceCoverage(
  available: boolean,
): "complete" | null {
  return available ? "complete" : null;
}
