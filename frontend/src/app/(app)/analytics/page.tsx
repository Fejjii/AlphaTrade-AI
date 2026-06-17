"use client";

import { useCallback } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { SETUP_TYPE_OPTIONS } from "@/lib/setup-types";
import { formatDate, formatDecimal } from "@/lib/utils";

function setupLabel(value: string) {
  return SETUP_TYPE_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export default function AnalyticsPage() {
  const loader = useCallback(async () => {
    const [setups, review, discipline, risk] = await Promise.all([
      api.analytics.setups(),
      api.analytics.tradeReview(),
      api.analytics.discipline(),
      api.analytics.riskBehavior(),
    ]);
    return { setups, review, discipline, risk };
  }, []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-zinc-400">
          Deterministic setup performance, trade review, discipline score, and risk behavior (paper
          only).
        </p>
      </div>

      {loading ? <LoadingState label="Loading analytics…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          <section className="space-y-3">
            <h2 className="text-lg font-medium">Setup performance</h2>
            {data.setups.setups.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {data.setups.setups.map((setup) => (
                  <Card key={setup.setup_type}>
                    <CardHeader>
                      <CardTitle className="text-base">{setupLabel(setup.setup_type)}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm text-zinc-300">
                      <p>Proposals: {setup.proposal_count}</p>
                      <p>
                        Paper trades: {setup.paper_trade_count} (W {setup.winning_paper_trades} / L{" "}
                        {setup.losing_paper_trades})
                      </p>
                      {setup.average_paper_pnl ? (
                        <p>Avg paper PnL: {formatDecimal(setup.average_paper_pnl)}</p>
                      ) : null}
                      {setup.average_confidence != null ? (
                        <p>Avg confidence: {(setup.average_confidence * 100).toFixed(0)}%</p>
                      ) : null}
                      {setup.most_common_mistakes.length ? (
                        <p>Mistakes: {setup.most_common_mistakes.join(", ")}</p>
                      ) : null}
                      {setup.last_used_at ? (
                        <p className="text-zinc-500">Last used {formatDate(setup.last_used_at)}</p>
                      ) : null}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No setup activity yet"
                description="Create proposals or paper trades to populate setup statistics."
              />
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Trade review</h2>
            <Card>
              <CardContent className="grid gap-2 pt-6 text-sm text-zinc-300 md:grid-cols-2">
                <p>Journaled trades: {data.review.total_journaled_trades}</p>
                <p>
                  Wins / losses: {data.review.win_count} / {data.review.loss_count}
                </p>
                <p>
                  Most frequent setup:{" "}
                  {data.review.most_frequent_setup_type
                    ? setupLabel(data.review.most_frequent_setup_type)
                    : "—"}
                </p>
                <p>Mistake tag: {data.review.most_frequent_mistake_tag ?? "—"}</p>
                <p>Emotion tag: {data.review.most_frequent_emotion_tag ?? "—"}</p>
                <p>Risk blocks: {data.review.trades_blocked_by_risk_engine}</p>
                <p>After daily loss warning: {data.review.trades_after_daily_loss_warning}</p>
                <p>After green day warning: {data.review.trades_after_green_day_warning}</p>
                <p>Rejected proposals: {data.review.proposals_rejected_by_user}</p>
                <p>Needs more analysis: {data.review.proposals_needing_more_analysis}</p>
              </CardContent>
            </Card>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Discipline score</h2>
            <Card>
              <CardHeader className="flex flex-row items-center gap-3">
                <CardTitle className="text-3xl">{data.discipline.score}</CardTitle>
                <StatusBadge label={`Grade ${data.discipline.grade}`} tone="info" />
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-zinc-300">
                {data.discipline.positive_behaviors.length ? (
                  <div>
                    <p className="font-medium text-emerald-300">Positive behaviors</p>
                    <ul className="list-disc pl-5">
                      {data.discipline.positive_behaviors.map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {data.discipline.negative_behaviors.length ? (
                  <div>
                    <p className="font-medium text-amber-300">Negative behaviors</p>
                    <ul className="list-disc pl-5">
                      {data.discipline.negative_behaviors.map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {data.discipline.improvement_suggestions.length ? (
                  <div>
                    <p className="font-medium text-zinc-200">Improvement suggestions</p>
                    <ul className="list-disc pl-5">
                      {data.discipline.improvement_suggestions.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Risk behavior</h2>
            <Card>
              <CardContent className="grid gap-2 pt-6 text-sm text-zinc-300 md:grid-cols-2">
                <p>Risk blocks: {data.risk.risk_blocks_count}</p>
                <p>Daily loss warnings: {data.risk.daily_loss_warnings}</p>
                <p>Green day warnings: {data.risk.green_day_warnings}</p>
                <p>Trading frequency notices: {data.risk.overtrading_warnings}</p>
                <p>Emotion-driven trade notices: {data.risk.revenge_trading_warnings}</p>
                <p>
                  Journal completion: {(data.risk.journal_completion_rate * 100).toFixed(0)}%
                </p>
                <p>Approvals approved: {data.risk.approval_approved_count}</p>
                <p>Approvals pending: {data.risk.approval_pending_count}</p>
                <p>Paper orders rejected: {data.risk.paper_orders_rejected}</p>
              </CardContent>
            </Card>
          </section>
        </>
      ) : null}
    </div>
  );
}
