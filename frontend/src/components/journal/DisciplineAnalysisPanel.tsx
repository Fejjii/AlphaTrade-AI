"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HumanVsSystemComparison } from "@/lib/api/types";

type Props = {
  comparison: HumanVsSystemComparison | null;
  loading?: boolean;
  error?: string | null;
};

export function DisciplineAnalysisPanel({ comparison, loading, error }: Props) {
  if (loading) {
    return <p className="text-sm text-zinc-400">Loading discipline analysis…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-300">{error}</p>;
  }
  if (!comparison) {
    return null;
  }

  const runner = comparison.missed_runner;
  const stop = comparison.stop_loss_analysis;

  return (
    <Card data-testid="discipline-panel">
      <CardHeader>
        <CardTitle className="text-base">Human vs system discipline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        <p>
          Plan adherence:{" "}
          <span className="font-medium text-zinc-100">{comparison.plan_adherence_score}/100</span>
        </p>
        {comparison.system_would_have_done ? (
          <p className="text-zinc-400">{comparison.system_would_have_done}</p>
        ) : null}
        <div className="grid gap-3 md:grid-cols-2">
          <div data-testid="early-exit-analysis">
            <p className="font-medium text-zinc-200">Early exit analysis</p>
            <p>Flag: {String(runner?.early_exit_flag ?? comparison.early_exit_flag ?? "n/a")}</p>
            {runner?.recommended_lesson ? <p>{runner.recommended_lesson}</p> : null}
            {runner?.missed_profit_estimate ? (
              <p className="text-zinc-400">
                Conservative estimate: {runner.missed_profit_estimate} (not guaranteed)
              </p>
            ) : null}
          </div>
          <div data-testid="stop-loss-analysis">
            <p className="font-medium text-zinc-200">Stop loss discipline</p>
            {stop?.lesson ? <p>{stop.lesson}</p> : null}
            {stop?.avoidable_loss_estimate ? (
              <p className="text-zinc-400">Avoidable loss estimate: {stop.avoidable_loss_estimate}</p>
            ) : null}
          </div>
        </div>
        {comparison.limitations?.length ? (
          <ul className="list-disc pl-4 text-xs text-zinc-500">
            {comparison.limitations.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
