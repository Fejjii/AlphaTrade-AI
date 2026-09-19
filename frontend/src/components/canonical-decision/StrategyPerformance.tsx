import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  LearningAnalyticsSummaryResponse,
  SetupAnalyticsResponse,
  StrategyQualitySummaryResponse,
} from "@/lib/api/types";

export function StrategyPerformance({
  quality,
  learning,
  setups,
}: {
  quality: StrategyQualitySummaryResponse | null;
  learning: LearningAnalyticsSummaryResponse | null;
  setups: SetupAnalyticsResponse | null;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-3" data-testid="strategy-performance">
      <Card>
        <CardHeader>
          <CardTitle>Strategy quality</CardTitle>
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
          <CardTitle>Learning analytics</CardTitle>
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
          <CardTitle>Setup performance</CardTitle>
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
  );
}
