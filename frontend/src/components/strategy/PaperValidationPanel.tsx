"use client";

import type {
  PaperEligibilityReport,
  PaperValidationRun,
  PaperValidationSummary,
} from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Props = {
  summary: PaperValidationSummary | null;
  eligibility: PaperEligibilityReport | null;
  busy: boolean;
  onStart: () => void;
};

export function PaperValidationPanel({ summary, eligibility, busy, onStart }: Props) {
  const latest: PaperValidationRun | undefined = summary?.runs[0];

  return (
    <Card data-testid="paper-validation-panel">
      <CardHeader>
        <CardTitle className="text-base">Paper validation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p className="text-zinc-400">
          Simulated paper trades only — no exchange orders. Real trading disabled.
        </p>

        {eligibility ? (
          <div className="space-y-2 rounded border border-zinc-800 p-3" data-testid="paper-eligibility-status">
            <p>
              Status: <span className="text-zinc-100">{eligibility.status}</span> · Paper eligible:{" "}
              {eligibility.paper_eligible ? "yes" : "no"}
            </p>
            <p>Recommendation: {eligibility.recommendation}</p>
            {eligibility.eligibility_reasons.length > 0 ? (
              <ul className="list-disc pl-4 text-zinc-400" data-testid="eligibility-reasons">
                {eligibility.eligibility_reasons.slice(0, 4).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : null}
            {eligibility.blockers.length > 0 ? (
              <ul className="list-disc pl-4 text-amber-200" data-testid="paper-eligibility-blockers">
                {eligibility.blockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {eligibility?.latest_backtest ? (
          <div className="rounded border border-zinc-800 p-3" data-testid="latest-backtest-metrics">
            <p className="text-zinc-400">Latest backtest</p>
            <ul className="grid gap-1 sm:grid-cols-2">
              <li>Trades: {eligibility.latest_backtest.trade_count}</li>
              <li>Win rate: {(eligibility.latest_backtest.win_rate * 100).toFixed(1)}%</li>
              <li>Profit factor: {eligibility.latest_backtest.profit_factor.toFixed(2)}</li>
              <li>Max DD: {eligibility.latest_backtest.max_drawdown_pct.toFixed(1)}%</li>
            </ul>
          </div>
        ) : null}

        {eligibility && eligibility.accepted_lessons.length > 0 ? (
          <div data-testid="accepted-lessons-linked">
            <p className="text-zinc-400">
              Accepted lessons affecting strategy: {eligibility.accepted_lessons.length}
            </p>
          </div>
        ) : null}

        {eligibility && eligibility.unresolved_lesson_candidates.length > 0 ? (
          <p className="text-amber-200" data-testid="unresolved-lesson-blocker">
            {eligibility.unresolved_lesson_candidates.length} unresolved lesson candidate(s) —
            review in Lessons before paper promotion.
          </p>
        ) : null}

        <Button variant="secondary" disabled={busy} onClick={onStart}>
          {busy ? "Starting…" : "Start / refresh validation"}
        </Button>

        {summary ? (
          <p>
            Validation runs: {summary.total} · Latest run status: {summary.latest_status ?? "—"}
          </p>
        ) : null}

        {latest?.metrics ? (
          <ul className="grid gap-1 sm:grid-cols-2" data-testid="paper-validation-metrics">
            <li>Paper trades: {latest.metrics.paper_trades_count}</li>
            <li>Win rate: {(latest.metrics.win_rate * 100).toFixed(1)}%</li>
            <li>Net PnL: {latest.metrics.net_pnl}</li>
            <li>Profit factor: {latest.metrics.profit_factor?.toFixed(2)}</li>
            <li>Run recommendation: {latest.recommendation ?? "—"}</li>
          </ul>
        ) : (
          <p className="text-zinc-500">
            No paper trades linked yet — metrics update as paper positions close.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
