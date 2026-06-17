"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DisciplineScoreResult, RiskBehaviorAnalytics } from "@/lib/api/types";

type Props = {
  discipline: DisciplineScoreResult | null;
  risk: RiskBehaviorAnalytics | null;
  tradesToday?: number | null;
};

function protectionBadge(active: boolean, label: string) {
  return (
    <Badge variant={active ? "warning" : "muted"}>
      {label}: {active ? "engaged" : "clear"}
    </Badge>
  );
}

export function TodaysDisciplineCard({ discipline, risk, tradesToday }: Props) {
  const overtrading = (risk?.overtrading_warnings ?? 0) > 0;
  const lossLock = (risk?.daily_loss_warnings ?? 0) > 0;
  const greenDay = (risk?.green_day_warnings ?? 0) > 0;

  const nextAction =
    discipline?.improvement_suggestions?.[0] ??
    (overtrading
      ? "Consider slowing down — frequent entries can reduce discipline."
      : lossLock
        ? "Daily loss protection is engaged. Stepping back can protect capital."
        : "Stay patient and wait for setups that match your plan.");

  return (
    <Card data-testid="todays-discipline-card">
      <CardHeader>
        <CardTitle className="text-base">Today&apos;s discipline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <div className="flex flex-wrap items-center gap-2">
          {discipline ? (
            <Badge variant="info" data-testid="discipline-score-badge">
              Discipline {discipline.score}/100 · {discipline.grade}
            </Badge>
          ) : (
            <span className="text-zinc-500">Discipline score not available yet.</span>
          )}
          <Badge variant="muted" data-testid="trades-today">
            Trades logged: {tradesToday ?? 0}
          </Badge>
        </div>

        <div className="flex flex-wrap gap-2">
          {protectionBadge(lossLock, "Loss protection")}
          {protectionBadge(greenDay, "Green-day protection")}
          {protectionBadge(overtrading, "Frequency notice")}
        </div>

        <p className="text-zinc-400" data-testid="discipline-next-action">
          {nextAction}
        </p>
        <p className="text-xs text-zinc-500">
          Calm, paper-only guidance. These are supportive signals, not financial advice.
        </p>
      </CardContent>
    </Card>
  );
}
