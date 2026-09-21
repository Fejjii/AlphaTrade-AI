import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CanonicalPaperEvaluationRead } from "@/lib/api/types";

function metric(label: string, value: string | number | null | undefined) {
  return (
    <p>
      {label}: {value == null || value === "" ? "unavailable" : value}
    </p>
  );
}

export function PaperEvaluationSummaryCard({
  evaluation,
}: {
  evaluation: CanonicalPaperEvaluationRead | null;
}) {
  if (!evaluation) {
    return (
      <Card data-testid="paper-evaluation-summary">
        <CardHeader>
          <CardTitle>Paper evaluation</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-text-muted">
          Paper evaluation API unavailable.
        </CardContent>
      </Card>
    );
  }
  const facts = evaluation.summary.facts;
  return (
    <Card data-testid="paper-evaluation-summary">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>Continuous paper evaluation</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              Measurement only. Watcher stays off. Refinements are suggestions, not activations.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge label="Paper only" tone="paper" />
            <StatusBadge label="Watcher not activated" tone="info" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid gap-3 md:grid-cols-2">
          <div data-testid="paper-evaluation-watcher">
            <p className="font-medium">Watcher</p>
            {metric("Scans", facts.watcher.scan_count)}
            {metric("Confirmed setups", facts.watcher.confirmed_setup_count)}
            {metric("Candidates published", facts.watcher.candidates_published)}
            {metric("Stale evidence", facts.watcher.stale_evidence_count)}
          </div>
          <div data-testid="paper-evaluation-conversion">
            <p className="font-medium">Conversion</p>
            {metric("Confirmed", facts.conversion.confirmed_setups)}
            {metric("Candidates", facts.conversion.candidates)}
            {metric("Eligible", facts.conversion.eligible)}
            {metric("Approved / filled / closed", `${facts.conversion.approved} / ${facts.conversion.filled} / ${facts.conversion.closed}`)}
          </div>
          <div data-testid="paper-evaluation-performance">
            <p className="font-medium">Strategy performance</p>
            {metric("Win rate", facts.strategy_overall.win_rate)}
            {metric("Expectancy", facts.strategy_overall.expectancy)}
            {metric("Max drawdown", facts.strategy_overall.max_drawdown)}
            {metric("Avg MFE / MAE", `${facts.strategy_overall.average_mfe ?? "unavailable"} / ${facts.strategy_overall.average_mae ?? "unavailable"}`)}
          </div>
          <div data-testid="paper-evaluation-behaviour">
            <p className="font-medium">Blocked, missed, human vs system</p>
            {metric("Blocked", facts.blocked.blocked_count)}
            {metric("Rejected confirmed", facts.missed_opportunities.rejected_confirmed)}
            {metric("Human approvals", facts.human_vs_system.human_approvals)}
            {metric("False-signal rate", facts.false_signals.false_signal_rate)}
          </div>
        </div>
        <p className="text-caption text-text-muted" data-testid="paper-evaluation-missed-warning">
          {facts.missed_opportunities.warning}
        </p>
        {evaluation.summary.narrative ? (
          <p className="text-caption text-text-muted" data-testid="paper-evaluation-narrative">
            {evaluation.summary.narrative.banner}
          </p>
        ) : (
          <p className="text-caption text-text-muted">Deterministic facts only. LLM narrative is not a fact.</p>
        )}
        <div data-testid="paper-evaluation-refinements">
          <p className="font-medium">Refinement suggestions</p>
          {evaluation.summary.refinements.length ? (
            <ul className="mt-1 space-y-2">
              {evaluation.summary.refinements.map((item) => (
                <li key={item.suggestion_id} className="rounded-md border border-border p-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge label={item.category} tone="info" />
                    <StatusBadge label="Not activated" tone="healthy" />
                  </div>
                  <p className="mt-1">{item.summary}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-text-muted">No refinement suggestions yet.</p>
          )}
        </div>
        <Link href="/decision/strategy" className="text-accent underline">
          Strategy performance
        </Link>
      </CardContent>
    </Card>
  );
}
