"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ValidationPrioritySummaryResponse } from "@/lib/api/types";

const ACTION_LABELS: Record<string, string> = {
  prioritize: "Prioritize",
  watch: "Watch",
  collect_more_data: "Collect more data",
  avoid_for_now: "Avoid for now",
};

export function PriorityQueueSummary({
  summary,
}: {
  summary: ValidationPrioritySummaryResponse;
}) {
  return (
    <Card data-testid="validation-priority-summary">
      <CardHeader>
        <CardTitle className="text-base">Pending validation queue</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          {summary.total_pending} pending ({summary.run_plans_pending} run plans,{" "}
          {summary.candidates_pending} candidates). Study guidance only.
        </p>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-2 text-sm text-zinc-300 sm:grid-cols-4">
        {summary.by_action.map((row) => (
          <div
            key={row.action_label}
            data-testid={`validation-priority-count-${row.action_label}`}
            className="rounded border border-zinc-800 p-2"
          >
            <p className="text-xl font-semibold text-zinc-100">{row.count}</p>
            <p className="text-xs text-zinc-500">
              {ACTION_LABELS[row.action_label] ?? row.action_label}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
