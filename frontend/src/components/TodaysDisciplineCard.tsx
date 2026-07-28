"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DailyDisciplineSnapshot, DisciplineScoreSummary } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

/**
 * Snapshot view with honest per-metric availability (FP2-102): fields the
 * current sources could not measure are null and render as unavailable —
 * never as fabricated zeros or "clear" protections. The full backend
 * DailyDisciplineSnapshot remains assignable.
 */
export type DisciplineSnapshotView = Omit<
  DailyDisciplineSnapshot,
  | "trades_today"
  | "paper_trades_opened_today"
  | "paper_trades_closed_today"
  | "journal_entries_today"
  | "loss_lock_active"
  | "green_day_protection_active"
  | "overtrading_warning_active"
  | "discipline_status"
> & {
  trades_today: number | null;
  paper_trades_opened_today: number | null;
  paper_trades_closed_today: number | null;
  journal_entries_today: number | null;
  loss_lock_active: boolean | null;
  green_day_protection_active: boolean | null;
  overtrading_warning_active: boolean | null;
  discipline_status: DailyDisciplineSnapshot["discipline_status"] | null;
};

type Props = {
  snapshot: DisciplineSnapshotView | null;
  disciplineScore?: DisciplineScoreSummary | null;
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "info" | "muted"> = {
  calm: "success",
  caution: "warning",
  locked: "danger",
  review_only: "info",
};

const SCORE_BAND_VARIANT: Record<string, "success" | "warning" | "danger" | "info" | "muted"> = {
  strong: "success",
  good: "success",
  caution: "warning",
  review_needed: "danger",
};

const SOURCE_LABEL: Record<string, string> = {
  configured_daily_state: "Today's configured state",
  user_risk_settings: "Your risk settings",
  system_default: "System defaults",
};

/**
 * Tri-state protection badge: null means the backing source is unavailable
 * and must never look like an all-clear (FP2-102).
 */
function protectionBadge(active: boolean | null, label: string) {
  return (
    <Badge
      variant={active === true ? "warning" : "muted"}
      data-testid={`discipline-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      {label}: {active === true ? "engaged" : active === false ? "clear" : "unknown"}
    </Badge>
  );
}

export function TodaysDisciplineCard({ snapshot, disciplineScore }: Props) {
  const statusVariant = snapshot?.discipline_status
    ? (STATUS_VARIANT[snapshot.discipline_status] ?? "muted")
    : "muted";
  const scoreBand = disciplineScore?.band ?? null;
  const scoreVariant = SCORE_BAND_VARIANT[scoreBand ?? ""] ?? "muted";

  return (
    <Card data-testid="todays-discipline-card">
      <CardHeader>
        <CardTitle className="text-base">Today&apos;s discipline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <div className="flex flex-wrap items-center gap-2">
          {snapshot ? (
            <Badge variant={statusVariant} data-testid="discipline-status-badge">
              {snapshot.discipline_status ?? "status unavailable"}
            </Badge>
          ) : (
            <span className="text-zinc-500">Daily discipline snapshot not available yet.</span>
          )}
          {disciplineScore?.score != null ? (
            <Badge variant={scoreVariant} data-testid="discipline-score-badge">
              Discipline score: {disciplineScore.score}
              {disciplineScore.band ? ` (${disciplineScore.band})` : ""}
            </Badge>
          ) : null}
          <Badge variant="muted" data-testid="trades-today">
            Trades today: {snapshot?.trades_today ?? "—"}
          </Badge>
          {snapshot?.net_pnl_today_paper != null ? (
            <Badge variant="info" data-testid="daily-pnl-today">
              Paper PnL today: {formatDecimal(snapshot.net_pnl_today_paper)}
            </Badge>
          ) : null}
        </div>

        {snapshot ? (
          <div className="flex flex-wrap gap-2 text-xs text-zinc-400" data-testid="discipline-configured-limits">
            <span>Loss limit: {snapshot.daily_loss_limit ?? "—"}</span>
            <span>Target: {snapshot.daily_target ?? "—"}</span>
            <span>Max trades: {snapshot.max_trades_per_day ?? "—"}</span>
            <span data-testid="discipline-settings-source">
              Source: {SOURCE_LABEL[snapshot.risk_settings_source] ?? snapshot.risk_settings_source}
            </span>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {protectionBadge(snapshot?.loss_lock_active ?? null, "Loss protection")}
          {protectionBadge(snapshot?.green_day_protection_active ?? null, "Green-day protection")}
          {protectionBadge(snapshot?.overtrading_warning_active ?? null, "Frequency notice")}
        </div>

        {disciplineScore?.main_contributors.length ? (
          <ul className="space-y-1 text-xs text-zinc-400" data-testid="discipline-score-contributors">
            {disciplineScore.main_contributors.slice(0, 3).map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        ) : null}

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
          <details className="text-xs text-amber-500/80" data-testid="discipline-limitations">
            <summary className="cursor-pointer text-zinc-400">Limitations</summary>
            <ul className="mt-2 space-y-1">
              {snapshot.limitations.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </details>
        ) : null}

        <p className="text-xs text-zinc-500">
          Calm, paper-only guidance. These are supportive signals, not financial advice.
        </p>
      </CardContent>
    </Card>
  );
}
