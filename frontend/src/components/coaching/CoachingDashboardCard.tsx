"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CoachingPrompt, CoachingSummaryResponse } from "@/lib/api/types";

const CATEGORY_LABELS: Record<string, string> = {
  missed_entry: "Missed entry",
  should_have_waited: "Should have waited",
  should_have_avoided: "Should have avoided",
  invalidation_hit: "Invalidation hit",
  low_quality_setup: "Low quality",
  overconfidence: "Overconfidence",
  weak_confidence_correlation: "Weak confidence link",
};

export function CoachingDashboardCard({
  summary,
  topPrompts,
}: {
  summary: CoachingSummaryResponse | null;
  topPrompts: CoachingPrompt[];
}) {
  return (
    <Card data-testid="dashboard-coaching">
      <CardHeader>
        <CardTitle className="text-base">Coaching</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          Review repeated behavior patterns before validating more setups. No orders, no automation.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        {summary ? (
          <div
            className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"
            data-testid="dashboard-coaching-distribution"
          >
            {summary.by_severity
              .filter((row) => row.count > 0)
              .slice(0, 4)
              .map((row) => (
                <div
                  key={row.severity}
                  className="rounded border border-zinc-800 px-2 py-1.5"
                  data-testid={`dashboard-coaching-count-${row.severity}`}
                >
                  <p className="text-lg font-semibold text-zinc-100">{row.count}</p>
                  <p className="text-zinc-500">{row.severity}</p>
                </div>
              ))}
          </div>
        ) : null}

        {topPrompts.length ? (
          <ul className="space-y-2" data-testid="dashboard-coaching-top-items">
            {topPrompts.map((prompt) => (
              <li
                key={prompt.signature}
                className="rounded border border-zinc-800 px-3 py-2"
                data-testid={`dashboard-coaching-top-${prompt.signature}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-zinc-100">{prompt.title}</span>
                  <span className="text-xs text-zinc-500">{prompt.severity}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  {CATEGORY_LABELS[prompt.category] ?? prompt.category} · concern {prompt.concern_score}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-zinc-500">No coaching patterns above the sample threshold yet.</p>
        )}

        <div className="flex flex-wrap gap-3 text-xs">
          <Link
            href="/coaching"
            className="text-zinc-400 underline"
            data-testid="dashboard-coaching-view-all"
          >
            Review coaching
          </Link>
          <Link href="/lessons" className="text-zinc-400 underline" data-testid="dashboard-coaching-lessons">
            Open review queue
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
