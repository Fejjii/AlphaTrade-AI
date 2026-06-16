"use client";

import type { PaperValidationRun, PaperValidationSummary } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Props = {
  summary: PaperValidationSummary | null;
  busy: boolean;
  onStart: () => void;
};

export function PaperValidationPanel({ summary, busy, onStart }: Props) {
  const latest: PaperValidationRun | undefined = summary?.runs[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Paper validation metrics</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p className="text-zinc-400">
          Tracks simulated paper trades only — no exchange orders. Real trading disabled.
        </p>
        <Button variant="secondary" disabled={busy} onClick={onStart}>
          {busy ? "Starting…" : "Start / refresh validation"}
        </Button>
        {summary ? (
          <p>
            Paper eligible: {summary.paper_eligible ? "yes" : "no"} · Runs: {summary.total}
          </p>
        ) : null}
        {latest?.metrics ? (
          <ul className="grid gap-1 sm:grid-cols-2">
            <li>Paper trades: {latest.metrics.paper_trades_count}</li>
            <li>Win rate: {(latest.metrics.win_rate * 100).toFixed(1)}%</li>
            <li>Net PnL: {latest.metrics.net_pnl}</li>
            <li>Profit factor: {latest.metrics.profit_factor?.toFixed(2)}</li>
            <li>Recommendation: {latest.recommendation ?? "—"}</li>
          </ul>
        ) : (
          <p className="text-zinc-500">No paper trades linked yet — metrics update as paper positions close.</p>
        )}
      </CardContent>
    </Card>
  );
}
