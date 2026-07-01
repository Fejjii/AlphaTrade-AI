"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/states";
import type { BehaviorInsight } from "@/lib/api/types";

function severityTone(severity: string) {
  return severity === "warning" ? "warn" : "info";
}

export function BehaviorInsightsCard({ insights }: { insights: BehaviorInsight[] }) {
  return (
    <Card data-testid="learning-behavior-insights-card">
      <CardHeader>
        <CardTitle className="text-base">Behavior insights</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          Rule-based observations for review only. These never trigger orders, proposals, or
          automation.
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        {insights.length ? (
          <ul className="space-y-3">
            {insights.map((insight) => (
              <li
                key={`${insight.code}-${insight.message}`}
                data-testid={`learning-insight-${insight.code}`}
                className="flex flex-col gap-1 border-b border-zinc-800 pb-2 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <StatusBadge label={insight.severity} tone={severityTone(insight.severity)} />
                  <span className="text-xs text-zinc-500">
                    n={insight.sample_size} · {insight.confidence} confidence
                  </span>
                </div>
                <span className="text-zinc-100">{insight.message}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No insights yet"
            description="Record more validation session outcomes to surface behavior insights."
          />
        )}
      </CardContent>
    </Card>
  );
}
