"use client";

import dynamic from "next/dynamic";

import { ChartLoadingFallback } from "./ChartLoadingFallback";

export const DailyPnlChart = dynamic(
  () => import("./DailyPnlChart").then((module) => module.DailyPnlChart),
  {
    ssr: false,
    loading: () => <ChartLoadingFallback title="Which days made or lost money?" />,
  },
);

export const CumulativePnlChart = dynamic(
  () => import("./CumulativePnlChart").then((module) => module.CumulativePnlChart),
  {
    ssr: false,
    loading: () => <ChartLoadingFallback title="Is realised P&L compounding or churning?" />,
  },
);

export const SetupWinRateChart = dynamic(
  () => import("./SetupWinRateChart").then((module) => module.SetupWinRateChart),
  {
    ssr: false,
    loading: () => (
      <ChartLoadingFallback title="Which setups win most often — with enough sample to matter?" />
    ),
  },
);

export const SetupExpectancyChart = dynamic(
  () => import("./SetupExpectancyChart").then((module) => module.SetupExpectancyChart),
  {
    ssr: false,
    loading: () => <ChartLoadingFallback title="Expectancy (mean net P&L per trade)" />,
  },
);

export const RuleComplianceChart = dynamic(
  () => import("./RuleComplianceChart").then((module) => module.RuleComplianceChart),
  {
    ssr: false,
    loading: () => (
      <ChartLoadingFallback title="Do I perform better when I follow my rules?" />
    ),
  },
);

export const ComparisonChart = dynamic(
  () => import("./ComparisonChart").then((module) => module.ComparisonChart),
  {
    ssr: false,
    loading: () => <ChartLoadingFallback title="Where does the human beat the system?" />,
  },
);
