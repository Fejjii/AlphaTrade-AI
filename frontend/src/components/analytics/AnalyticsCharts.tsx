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
