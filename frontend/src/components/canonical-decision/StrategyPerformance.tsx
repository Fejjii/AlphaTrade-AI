import Link from "next/link";

import { PaperEvaluationSummaryCard } from "@/components/canonical-decision/PaperEvaluationSummaryCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  CanonicalLearningStatsRead,
  CanonicalPaperEvaluationRead,
  LearningAnalyticsSummaryResponse,
  SetupAnalyticsResponse,
  StrategyQualitySummaryResponse,
} from "@/lib/api/types";

export function StrategyPerformance({
  quality,
  learning,
  setups,
  canonical,
  evaluation,
}: {
  quality: StrategyQualitySummaryResponse | null;
  learning: LearningAnalyticsSummaryResponse | null;
  setups: SetupAnalyticsResponse | null;
  canonical?: CanonicalLearningStatsRead | null;
  evaluation?: CanonicalPaperEvaluationRead | null;
}) {
  return (
    <div className="space-y-4">
      <PaperEvaluationSummaryCard evaluation={evaluation ?? null} />
      <div className="grid gap-4 xl:grid-cols-4" data-testid="strategy-performance">
      <Card data-testid="canonical-learning-stats">
        <CardHeader>
          <CardTitle>Canonical learning</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {canonical ? (
            <>
              <p>Human approvals: {canonical.snapshot.human_vs_system.human_approvals}</p>
              <p>Paper executions: {canonical.snapshot.human_vs_system.paper_system_executions}</p>
              <p>Executed outcomes: {canonical.snapshot.human_vs_system.executed_outcomes}</p>
              <p className="text-caption text-text-muted">
                LearningQueryService only. LLM narrative is not a fact.
              </p>
            </>
          ) : (
            <p className="text-text-muted">Canonical learning API unavailable.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Strategy quality (compatibility)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {quality ? (
            <>
              <p>
                Detectors with data: {quality.detectors_with_data}/{quality.total_detectors}
              </p>
              <p>Results: {quality.total_results}</p>
              <ul className="space-y-1">
                {quality.ranked.slice(0, 5).map((item) => (
                  <li key={item.condition} className="flex items-center justify-between gap-2">
                    <span>{item.condition}</span>
                    <StatusBadge label={item.verdict} tone="info" />
                  </li>
                ))}
              </ul>
              <Link href="/strategy-quality" className="text-accent underline">
                Full strategy quality
              </Link>
            </>
          ) : (
            <p className="text-text-muted">Strategy quality API unavailable.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Learning analytics (compatibility)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {learning ? (
            <>
              <p>Completed sessions: {learning.completed_sessions}</p>
              <p>Results: {learning.results_count}</p>
              <p>Lessons: {learning.lessons_count}</p>
              <Link href="/learning-analytics" className="text-accent underline">
                Full learning analytics
              </Link>
            </>
          ) : (
            <p className="text-text-muted">Learning analytics API unavailable.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Setup performance (compatibility)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {setups?.setups.length ? (
            <ul className="space-y-2">
              {setups.setups.slice(0, 6).map((setup) => (
                <li key={setup.setup_type}>
                  <p className="font-medium">{setup.setup_type}</p>
                  <p className="text-caption text-text-muted">
                    Paper trades {setup.paper_trade_count} · wins {setup.winning_paper_trades}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-text-muted">No setup statistics yet.</p>
          )}
          <Link href="/analytics" className="text-accent underline">
            Analytics hub
          </Link>
        </CardContent>
      </Card>
      </div>
    </div>
  );
}
