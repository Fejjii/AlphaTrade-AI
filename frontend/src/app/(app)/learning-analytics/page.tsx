"use client";

import { useCallback, useState } from "react";

import { BehaviorInsightsCard } from "@/components/learning-analytics/BehaviorInsightsCard";
import { OutcomeRatesCard } from "@/components/learning-analytics/OutcomeRatesCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { SetupDimension } from "@/lib/api/types";

const DIMENSIONS: { value: SetupDimension; label: string }[] = [
  { value: "condition", label: "Condition" },
  { value: "timeframe", label: "Timeframe" },
  { value: "symbol", label: "Symbol" },
  { value: "direction", label: "Direction" },
  { value: "confidence_bucket", label: "Confidence" },
];

function percent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(0)}%`;
}

export default function LearningAnalyticsPage() {
  const [dimension, setDimension] = useState<SetupDimension>("condition");

  const loader = useCallback(async () => {
    const [summary, performance, discipline, confidence, insights, lessons, ranking] =
      await Promise.all([
        api.learningAnalytics.summary(),
        api.learningAnalytics.setupPerformance({ dimension }),
        api.learningAnalytics.discipline(),
        api.learningAnalytics.confidenceOutcome(),
        api.learningAnalytics.behaviorInsights(),
        api.learningAnalytics.lessons(),
        api.learningAnalytics.setupRanking({ dimension }),
      ]);
    return { summary, performance, discipline, confidence, insights, lessons, ranking };
  }, [dimension]);

  const { data, loading, error, reload } = useAsyncData(loader, [dimension]);

  return (
    <div className="space-y-8" data-testid="learning-analytics-page">
      <div>
        <h1 className="text-2xl font-semibold">Learning Analytics</h1>
        <p className="text-sm text-zinc-400">
          Read-only review of paper validation sessions, observations, and outcomes. No orders, no
          proposals, no automation — insights only.
        </p>
      </div>

      {loading && !data ? <LoadingState label="Loading learning analytics…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          <section className="grid gap-3 md:grid-cols-3" data-testid="learning-funnel">
            <Card>
              <CardContent className="grid gap-1 pt-6 text-sm text-zinc-300">
                <p>Total sessions: {data.summary.total_sessions}</p>
                <p>Completed: {data.summary.completed_sessions}</p>
                <p>Cancelled: {data.summary.cancelled_sessions}</p>
                <p>Recorded outcomes: {data.summary.results_count}</p>
                <p>Lessons captured: {data.summary.lessons_count}</p>
                <p>
                  Avg minutes to outcome:{" "}
                  {data.summary.average_minutes_to_outcome ?? "—"}
                </p>
              </CardContent>
            </Card>
            <div className="md:col-span-2">
              <OutcomeRatesCard
                rates={data.summary.rates}
                distribution={data.summary.outcome_distribution}
                resultsCount={data.summary.results_count}
              />
            </div>
          </section>

          <section className="space-y-3" data-testid="learning-setup-performance">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-medium">Setup performance</h2>
              <div className="flex flex-wrap gap-1" role="group" aria-label="Dimension">
                {DIMENSIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    data-testid={`learning-dimension-${option.value}`}
                    onClick={() => setDimension(option.value)}
                    className={
                      dimension === option.value
                        ? "rounded bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-900"
                        : "rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-300"
                    }
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            {data.performance.groups.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {data.performance.groups.map((group) => (
                  <Card
                    key={group.dimension_value}
                    data-testid={`learning-group-${group.dimension_value}`}
                  >
                    <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
                      <CardTitle className="text-base">{group.dimension_value}</CardTitle>
                      {group.insufficient_data ? (
                        <StatusBadge label="Insufficient data" tone="muted" />
                      ) : (
                        <StatusBadge label={`Q ${group.quality_score ?? "—"}`} tone="info" />
                      )}
                    </CardHeader>
                    <CardContent className="space-y-1 text-sm text-zinc-300">
                      <p>Sample size: {group.sample_size}</p>
                      <p>Success: {percent(group.success_rate)}</p>
                      <p>Failure: {percent(group.failure_rate)}</p>
                      <p>Invalidation hit: {percent(group.invalidation_hit_rate)}</p>
                      <p>Behaved as expected: {percent(group.behaved_as_expected_rate)}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No setup performance yet"
                description="Complete validation sessions with recorded outcomes to see performance."
              />
            )}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <Card data-testid="learning-discipline-card">
              <CardHeader className="flex flex-row items-center gap-3">
                <CardTitle className="text-3xl">
                  {data.discipline.discipline_score ?? "—"}
                </CardTitle>
                <StatusBadge
                  label={`Grade ${data.discipline.discipline_grade}`}
                  tone={data.discipline.insufficient_data ? "muted" : "info"}
                />
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-zinc-300">
                {data.discipline.insufficient_data ? (
                  <p className="text-zinc-500">
                    Not enough sessions yet to score discipline (min sample{" "}
                    {data.discipline.min_sample}).
                  </p>
                ) : null}
                {data.discipline.negative_behaviors.length ? (
                  <div>
                    <p className="font-medium text-amber-300">Watch-outs</p>
                    <ul className="list-disc pl-5">
                      {data.discipline.negative_behaviors.map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {data.discipline.improvement_suggestions.length ? (
                  <div>
                    <p className="font-medium text-zinc-200">Suggestions</p>
                    <ul className="list-disc pl-5">
                      {data.discipline.improvement_suggestions.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card data-testid="learning-confidence-card">
              <CardHeader>
                <CardTitle className="text-base">Confidence vs outcome</CardTitle>
                <p className="mt-1 text-xs text-zinc-500">
                  Correlation: {data.confidence.correlation}
                </p>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-zinc-300">
                {data.confidence.buckets.map((bucket) => (
                  <p key={bucket.bucket} data-testid={`learning-confidence-${bucket.bucket}`}>
                    {bucket.bucket}: {percent(bucket.success_rate)} success (n={bucket.sample_size})
                    {bucket.insufficient_data ? " · insufficient" : ""}
                  </p>
                ))}
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <BehaviorInsightsCard insights={data.insights.insights} />

            <Card data-testid="learning-lessons-card">
              <CardHeader>
                <CardTitle className="text-base">Recurring lesson themes</CardTitle>
                <p className="mt-1 text-xs text-zinc-500">
                  {data.lessons.lessons_count} lesson note(s) captured.
                </p>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-zinc-300">
                {data.lessons.themes.length ? (
                  <ul className="space-y-1">
                    {data.lessons.themes.map((theme) => (
                      <li key={theme.theme} data-testid={`learning-theme-${theme.theme}`}>
                        <span className="text-zinc-100">{theme.theme}</span> ({theme.count})
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    title="No lessons yet"
                    description="Add lessons to session outcomes to build recurring themes."
                  />
                )}
              </CardContent>
            </Card>
          </section>

          <section className="space-y-3" data-testid="learning-setup-ranking">
            <h2 className="text-lg font-medium">Setup ranking</h2>
            <p className="text-xs text-zinc-500">{data.ranking.note}</p>
            {data.ranking.ranked.length ? (
              <Card>
                <CardContent className="space-y-1 pt-6 text-sm text-zinc-300">
                  {data.ranking.ranked.map((item) => (
                    <p key={item.setup_key} data-testid={`learning-rank-${item.setup_key}`}>
                      #{item.rank} {item.setup_key} — quality {item.quality_score} (n=
                      {item.sample_size})
                    </p>
                  ))}
                </CardContent>
              </Card>
            ) : (
              <EmptyState
                title="No ranking yet"
                description="Ranking appears once enough sessions meet the minimum sample size."
              />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
