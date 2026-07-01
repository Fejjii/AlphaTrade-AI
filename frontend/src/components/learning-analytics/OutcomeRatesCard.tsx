"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OutcomeDistributionItem, RateMetrics } from "@/lib/api/types";

function percent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(0)}%`;
}

const RATE_LABELS: { key: keyof RateMetrics; label: string }[] = [
  { key: "success_rate", label: "Success" },
  { key: "failure_rate", label: "Failure" },
  { key: "invalidated_rate", label: "Invalidated" },
  { key: "missed_entry_rate", label: "Missed entry" },
  { key: "no_trade_rate", label: "No trade" },
  { key: "inconclusive_rate", label: "Inconclusive" },
  { key: "behaved_as_expected_rate", label: "Behaved as expected" },
  { key: "invalidation_hit_rate", label: "Invalidation hit" },
];

export function OutcomeRatesCard({
  rates,
  distribution,
  resultsCount,
}: {
  rates: RateMetrics;
  distribution: OutcomeDistributionItem[];
  resultsCount: number;
}) {
  return (
    <Card data-testid="learning-outcome-rates-card">
      <CardHeader>
        <CardTitle className="text-base">Outcome distribution &amp; rates</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          Derived from {resultsCount} recorded session outcome(s) — read-only, no orders or
          automation.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        <div className="grid gap-2 md:grid-cols-2">
          {RATE_LABELS.map(({ key, label }) => (
            <p key={key} data-testid={`learning-rate-${key}`}>
              {label}: <span className="text-zinc-100">{percent(rates[key])}</span>
            </p>
          ))}
        </div>
        <div>
          <p className="mb-1 font-medium text-zinc-200">By outcome</p>
          <ul className="grid gap-1 md:grid-cols-2">
            {distribution.map((item) => (
              <li key={item.outcome} data-testid={`learning-outcome-${item.outcome}`}>
                {item.outcome}: {item.count} ({percent(item.rate)})
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
