import type {
  JournalComparisonCohort,
  JournalComparisonCohortResult,
  JournalComparisonResponse,
  SampleConfidence,
} from "@/lib/api/types";

import { parseDecimal } from "./format";

export type ComparisonMetricId = "win_rate" | "expectancy" | "average_r" | "profit_factor";

export const COMPARISON_METRICS: {
  id: ComparisonMetricId;
  label: string;
  kind: "rate" | "monetary" | "r" | "factor";
}[] = [
  { id: "win_rate", label: "Win rate", kind: "rate" },
  { id: "expectancy", label: "Expectancy", kind: "monetary" },
  { id: "average_r", label: "Average R", kind: "r" },
  { id: "profit_factor", label: "Profit factor", kind: "factor" },
];

export const COHORT_ORDER: JournalComparisonCohort[] = ["human", "paper_system", "backtest"];

export const COHORT_LABELS: Record<JournalComparisonCohort, string> = {
  human: "Human",
  paper_system: "Paper system",
  backtest: "Backtest",
};

export type ComparisonCohortView = {
  cohort: JournalComparisonCohort;
  label: string;
  sampleCount: number;
  confidence: SampleConfidence;
  insufficient: boolean;
  winRate: number | null;
  expectancy: number | null;
  averageR: number | null;
  profitFactor: number | null;
};

export function buildComparisonCohorts(
  response: JournalComparisonResponse | null,
): ComparisonCohortView[] {
  const byCohort = new Map<JournalComparisonCohort, JournalComparisonCohortResult>();
  for (const cohort of response?.cohorts ?? []) byCohort.set(cohort.cohort, cohort);

  return COHORT_ORDER.map((cohort) => {
    const row = byCohort.get(cohort);
    const confidence = row?.metrics.confidence ?? "insufficient";
    return {
      cohort,
      label: COHORT_LABELS[cohort],
      sampleCount: row?.sample_count ?? 0,
      confidence,
      insufficient: confidence === "insufficient" || (row?.sample_count ?? 0) < 5,
      winRate: row?.metrics.win_rate ?? null,
      expectancy: parseDecimal(row?.metrics.expectancy),
      averageR: row?.metrics.average_r ?? null,
      profitFactor: row?.metrics.profit_factor ?? null,
    };
  });
}

export function metricValue(cohort: ComparisonCohortView, metric: ComparisonMetricId): number | null {
  switch (metric) {
    case "win_rate":
      return cohort.winRate == null ? null : cohort.winRate * 100;
    case "expectancy":
      return cohort.expectancy;
    case "average_r":
      return cohort.averageR;
    case "profit_factor":
      return cohort.profitFactor;
  }
}

export function evidenceIsInsufficient(cohorts: ComparisonCohortView[]): boolean {
  const usable = cohorts.filter((cohort) => cohort.sampleCount > 0);
  if (usable.length < 2) return true;
  return usable.some((cohort) => cohort.insufficient);
}
