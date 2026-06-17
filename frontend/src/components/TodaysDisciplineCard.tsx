"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DailyDisciplineSnapshot } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

type Props = {
  snapshot: DailyDisciplineSnapshot | null;
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "info" | "muted"> = {
  calm: "success",
  caution: "warning",
  locked: "danger",
  review_only: "info",
};

function protectionBadge(active: boolean, label: string) {
  return (
    <Badge variant={active ? "warning" : "muted"} data-testid={`discipline-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      {label}: {active ? "engaged" : "clear"}
    </Badge>
  );
}

export function TodaysDisciplineCard({ snapshot }: Props) {
  const statusVariant = STATUS_VARIANT[snapshot?.discipline_status ?? "calm"] ?? "muted";

  return (
    <Card data-testid="todays-discipline-card">
      <CardHeader>
        <CardTitle className="text-base">Today&apos;s discipline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <div className="flex flex-wrap items-center gap-2">
          {snapshot ? (
            <Badge variant={statusVariant} data-testid="discipline-status-badge">
              {snapshot.discipline_status}
            </Badge>
          ) : (
            <span className="text-zinc-500">Daily discipline snapshot not available yet.</span>
          )}
          <Badge variant="muted" data-testid="trades-today">
            Trades today: {snapshot?.trades_today ?? "—"}
          </Badge>
          {snapshot?.net_pnl_today_paper != null ? (
            <Badge variant="info" data-testid="daily-pnl-today">
              Paper PnL today: {formatDecimal(snapshot.net_pnl_today_paper)}
            </Badge>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          {protectionBadge(snapshot?.loss_lock_active ?? false, "Loss protection")}
          {protectionBadge(snapshot?.green_day_protection_active ?? false, "Green-day protection")}
          {protectionBadge(snapshot?.overtrading_warning_active ?? false, "Frequency notice")}
        </div>

        {snapshot?.reasons.length ? (
          <ul className="space-y-1 text-xs text-zinc-400" data-testid="discipline-reasons">
            {snapshot.reasons.map((reason) => (
              <li key={reason}>• {reason}</li>
            ))}
          </ul>
        ) : null}

        <p className="text-zinc-400" data-testid="discipline-next-action">
          {snapshot?.recommended_action ??
            "Stay patient and wait for setups that match your plan."}
        </p>

        {snapshot?.limitations.length ? (
          <ul className="space-y-1 text-xs text-amber-500/80" data-testid="discipline-limitations">
            {snapshot.limitations.map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        ) : null}

        <p className="text-xs text-zinc-500">
          Calm, paper-only guidance. These are supportive signals, not financial advice.
        </p>
      </CardContent>
    </Card>
  );
}
