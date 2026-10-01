import Link from "next/link";

import { DailyReviewCard } from "./DailyReviewCard";

import {
  bucketWinRate,
  closedStrategyRows,
  importantAlerts,
  marketEvidenceSummary,
  openPositionCount,
  openPositionRows,
  portfolioEquity,
  portfolioExpectancy,
  portfolioPnl,
  portfolioWinRate,
  recentTradeRows,
  strategyPerformanceRows,
  watcherTraderLabel,
} from "@/components/dashboard/trader-dashboard";
import { TradingMetric } from "@/components/dashboard/TradingMetric";
import { journalEntryHref } from "@/components/journal/journalContext";
import { EmptyState, UnavailableState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import {
  formatCount,
  formatDateTime,
  formatMonetary,
  formatPrice,
  humanizeToken,
} from "@/lib/format";
import type {
  CanonicalMarketMonitorStatusRead,
  DashboardSummary,
  JournalEntry,
  JournalStatsResponse,
  PaginatedJournalEntries,
  PaginatedPositions,
  PaperAlert,
  PaperPortfolioResponse,
  WatcherMonitoringSnapshot,
} from "@/lib/api/types";

export type TraderDashboardData = {
  portfolio: SourceResult<PaperPortfolioResponse>;
  positions: SourceResult<PaginatedPositions>;
  journal: SourceResult<PaginatedJournalEntries>;
  strategyStats: SourceResult<JournalStatsResponse>;
  summary: SourceResult<DashboardSummary>;
  watcher: SourceResult<WatcherMonitoringSnapshot>;
  market: SourceResult<CanonicalMarketMonitorStatusRead>;
  alerts: SourceResult<{ items: PaperAlert[]; total: number }>;
};

function SectionEmpty({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <EmptyState title={title} description={description} className="py-6" />
  );
}

function TradeLine({ entry }: { entry: JournalEntry }) {
  return (
    <li className="border-b border-border-subtle last:border-b-0">
      <Link
        href={journalEntryHref(entry.id)}
        className="flex min-h-16 items-center justify-between gap-3 rounded-control py-3 hover:bg-surface-2/50"
      >
        <div className="min-w-0">
          <p className="break-words text-sm font-medium text-text-primary">
            {entry.symbol} · {entry.direction}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {humanizeToken(entry.result || "unavailable")} ·{" "}
            {formatDateTime(entry.created_at)}
          </p>
        </div>
        <DataNumber value={formatMonetary(entry.pnl)} className="shrink-0" />
      </Link>
    </li>
  );
}

export function TraderDashboardView({
  data,
  posture,
  onRetry,
  refreshing = false,
}: {
  data: TraderDashboardData;
  posture: SafetyPostureDisplay;
  onRetry?: () => void;
  refreshing?: boolean;
}) {
  const winRate = portfolioWinRate(data.portfolio);
  const expectancy = portfolioExpectancy(data.portfolio);
  const positions = openPositionRows(data.positions);
  const trades = recentTradeRows(data.journal);
  const byStrategy = strategyPerformanceRows(data.strategyStats);
  const closedByStrategy = closedStrategyRows(data.portfolio);
  const alerts = importantAlerts(data.alerts);
  const market = marketEvidenceSummary(data.market);
  const daily = data.summary.available
    ? data.summary.data?.daily_discipline
    : null;
  const watcherLabel = data.watcher.available
    ? watcherTraderLabel(data.watcher.data?.paper_monitoring_status)
    : "Unavailable";
  const unavailable = [
    ["Portfolio", data.portfolio],
    ["Positions", data.positions],
    ["Recent trades", data.journal],
    ["Journal statistics", data.strategyStats],
    ["Daily status", data.summary],
    ["Watcher", data.watcher],
    ["Market evidence", data.market],
    ["Alerts", data.alerts],
  ]
    .filter(([, source]) => !(source as SourceResult<unknown>).available)
    .map(([name]) => name)
    .join(", ");

  return (
    <div className="space-y-5" data-testid="trader-dashboard">
      <PageHeader
        title="Dashboard"
        description="Your paper account, trading day, and next review."
        meta={
          <>
            <PaperModeIndicator active={posture.paperConfirmed} />
            <Badge variant={watcherLabel === "Watching" ? "success" : "muted"}>
              Watcher: {watcherLabel}
            </Badge>
          </>
        }
        actions={
          <>
            <Link
              href="/agent"
              className="inline-flex min-h-11 items-center rounded-control border border-accent-border bg-accent-muted px-4 text-sm font-medium text-accent"
            >
              Open Agent
            </Link>
            <Button variant="outline" onClick={onRetry} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "Refresh"}
            </Button>
          </>
        }
      />
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-control border border-border-subtle px-3 py-2 text-xs text-text-secondary"
        data-testid="dashboard-safety"
      >
        <Badge
          variant={posture.runtimeBadgeVariant}
          data-testid="dashboard-runtime-posture"
        >
          {posture.runtimeBadgeLabel}
        </Badge>
        <span data-testid="dashboard-paper-only">{posture.executionLabel}</span>
        <span data-testid="dashboard-real-trading-status">
          {posture.realTradingLabel}
        </span>
        <span
          className={
            daily?.loss_lock_active || daily?.overtrading_warning_active
              ? "text-warning"
              : "text-text-secondary"
          }
        >
          Today:{" "}
          {daily ? humanizeToken(daily.discipline_status) : "Unavailable"}
          {daily?.loss_lock_active
            ? " · Loss lock active"
            : daily?.overtrading_warning_active
              ? " · Overtrading warning"
              : ""}
        </span>
      </div>
      {posture.conflictMessage ? (
        <p
          role="alert"
          className="text-sm text-danger"
          data-testid="dashboard-safety-conflict"
        >
          {posture.conflictMessage}
        </p>
      ) : null}
      {unavailable ? (
        <div
          role="status"
          className="rounded-control border border-warning-border bg-warning-muted p-3 text-sm text-warning"
        >
          Unavailable: {unavailable}. Available sections remain visible.
        </div>
      ) : null}
      {refreshing ? (
        <p role="status" className="text-sm text-text-secondary">
          Refreshing dashboard; showing the previous snapshot.
        </p>
      ) : null}

      <Card>
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>Paper portfolio</CardTitle>
          <p className="text-xs text-text-secondary">
            {data.portfolio.available && data.portfolio.data?.account.as_of
              ? `As of ${formatDateTime(data.portfolio.data.account.as_of)}`
              : "Account snapshot unavailable"}
          </p>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <TradingMetric
            label="Portfolio value"
            value={portfolioEquity(data.portfolio)}
            note="Paper account equity"
            testId="dashboard-equity"
          />
          <TradingMetric
            label="Realized PnL"
            value={portfolioPnl(data.portfolio)}
            amount={data.portfolio.data?.metrics.net_pnl}
            note="Closed paper trades · net of costs"
            testId="dashboard-pnl"
          />
          <TradingMetric
            label="Open positions"
            value={openPositionCount(data.positions)}
            note="Total open · details below"
            testId="dashboard-open-count"
          />
          <TradingMetric
            label="Win rate"
            value={winRate.value}
            note={winRate.note ?? "Portfolio unavailable"}
            testId="dashboard-win-rate"
          />
          <TradingMetric
            label="Expectancy"
            value={expectancy.value}
            amount={data.portfolio.data?.metrics.expectancy}
            note={expectancy.note}
            testId="dashboard-expectancy"
          />
          <TradingMetric
            label="Today’s realized PnL"
            value={formatMonetary(daily?.realized_pnl_today_paper)}
            amount={daily?.realized_pnl_today_paper}
            note={
              daily
                ? `${daily.date} · ${daily.timezone}`
                : "Daily status unavailable"
            }
            testId="dashboard-daily-pnl"
          />
        </CardContent>
      </Card>

      <DailyReviewCard />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card data-testid="dashboard-daily-status">
          <CardHeader>
            <CardTitle>Daily status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {daily ? (
              <>
                <Badge
                  variant={
                    daily.loss_lock_active
                      ? "danger"
                      : daily.discipline_status === "calm"
                        ? "success"
                        : "warning"
                  }
                >
                  {humanizeToken(daily.discipline_status)}
                </Badge>
                <p className="text-sm leading-relaxed text-text-primary">
                  {daily.recommended_action}
                </p>
                <p className="text-xs text-text-secondary">
                  {formatCount(daily.paper_trades_opened_today)} opened ·{" "}
                  {formatCount(daily.paper_trades_closed_today)} closed ·{" "}
                  {formatCount(daily.remaining_trades_allowed)} remaining
                </p>
                <div className="flex flex-wrap gap-2">
                  {daily.loss_lock_active ? (
                    <Badge variant="danger">Loss lock active</Badge>
                  ) : null}
                  {daily.green_day_protection_active ? (
                    <Badge variant="warning">Green day protection</Badge>
                  ) : null}
                  {daily.overtrading_warning_active ? (
                    <Badge variant="warning">Overtrading warning</Badge>
                  ) : null}
                </div>
                {daily.reasons.length ? (
                  <ul className="space-y-1 text-xs text-text-secondary">
                    {daily.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                ) : null}
                {daily.limitations.length ? (
                  <p className="text-xs text-text-secondary">
                    {daily.limitations.join(" · ")}
                  </p>
                ) : null}
              </>
            ) : (
              <UnavailableState
                message="Daily status unavailable"
                onRetry={onRetry}
                className="py-4"
              />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Monitoring</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div data-testid="dashboard-watcher-status">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-text-secondary">Watcher</p>
                <Badge
                  variant={
                    watcherLabel === "Watching"
                      ? "success"
                      : watcherLabel === "Unavailable" ||
                          watcherLabel === "Stopped"
                        ? "muted"
                        : "warning"
                  }
                >
                  {watcherLabel}
                </Badge>
              </div>
              {data.watcher.available && data.watcher.data?.last_scan_at ? (
                <p className="mt-2 text-xs text-text-secondary">
                  Last scan {formatDateTime(data.watcher.data.last_scan_at)}
                </p>
              ) : null}
              <Link
                href="/watcher"
                className="mt-2 inline-flex min-h-11 items-center text-sm text-accent hover:underline"
              >
                Watcher details
              </Link>
            </div>
            <div
              className="border-t border-border-subtle pt-3"
              data-testid="dashboard-market-evidence"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-text-secondary">Market evidence</p>
                <Badge
                  variant={
                    market.label === "Healthy"
                      ? "success"
                      : market.label === "Unavailable"
                        ? "muted"
                        : "warning"
                  }
                >
                  {market.label}
                </Badge>
              </div>
              {market.symbol ? (
                <p className="mt-2 break-words text-xs text-text-secondary">
                  {market.symbol}
                </p>
              ) : null}
              <Link
                href="/market"
                className="inline-flex min-h-11 items-center text-sm text-accent hover:underline"
              >
                Market monitor
              </Link>
            </div>
          </CardContent>
        </Card>
        <Card
          data-testid="dashboard-alerts"
          className="order-first lg:order-none"
        >
          <CardHeader className="flex-row flex-wrap items-center justify-between">
            <CardTitle>Important alerts</CardTitle>
            <Link
              href="/alerts"
              className="inline-flex min-h-11 items-center text-sm text-accent hover:underline"
            >
              All alerts
            </Link>
          </CardHeader>
          <CardContent>
            {alerts == null ? (
              <UnavailableState
                message="Alerts unavailable"
                onRetry={onRetry}
                className="py-4"
              />
            ) : alerts.length === 0 ? (
              <SectionEmpty
                title="No alerts"
                description="New alerts will appear here for review."
              />
            ) : (
              <ul className="space-y-3">
                {alerts.map((alert) => (
                  <li
                    key={alert.id}
                    className="border-b border-border-subtle pb-3 last:border-b-0 last:pb-0"
                  >
                    <div className="flex flex-wrap gap-2">
                      <Badge
                        variant={
                          alert.severity === "critical" ||
                          alert.severity === "high"
                            ? "danger"
                            : "muted"
                        }
                      >
                        {humanizeToken(alert.severity)}
                      </Badge>
                      {!alert.read_at ? (
                        <span className="text-xs text-text-secondary">
                          Unread
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 break-words text-sm leading-relaxed text-text-primary">
                      {alert.message}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="dashboard-open-positions">
          <CardHeader className="flex-row flex-wrap items-center justify-between">
            <CardTitle>Open positions</CardTitle>
            <Link
              href="/portfolio"
              className="inline-flex min-h-11 items-center text-sm text-accent hover:underline"
            >
              Portfolio
            </Link>
          </CardHeader>
          <CardContent>
            {positions == null ? (
              <UnavailableState
                message="Open positions unavailable"
                onRetry={onRetry}
                className="py-4"
              />
            ) : positions.length === 0 ? (
              <SectionEmpty
                title="No open positions"
                description="Open paper positions will appear here with recorded unrealized PnL."
              />
            ) : (
              <>
                <p className="mb-2 text-right text-xs text-text-secondary">
                  Unrealized PnL
                </p>
                <ul>
                  {positions.map((position) => (
                    <li
                      key={position.id}
                      className="flex items-center justify-between gap-3 border-b border-border-subtle py-3 last:border-b-0"
                    >
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium">
                          {position.symbol} · {position.direction}
                        </p>
                        <p className="mt-1 text-xs text-text-secondary">
                          Entry {formatPrice(position.entry_price)}
                        </p>
                      </div>
                      <DataNumber
                        value={formatMonetary(position.unrealized_pnl)}
                        className="shrink-0"
                      />
                    </li>
                  ))}
                </ul>
                {data.positions.data &&
                data.positions.data.total > positions.length ? (
                  <p className="mt-3 text-xs text-text-secondary">
                    Showing {positions.length} of{" "}
                    {formatCount(data.positions.data.total)} open positions.
                    View the portfolio for more.
                  </p>
                ) : null}
              </>
            )}
          </CardContent>
        </Card>
        <Card data-testid="dashboard-recent-trades">
          <CardHeader className="flex-row flex-wrap items-center justify-between">
            <CardTitle>Recent trades</CardTitle>
            <Link
              href="/journal"
              className="inline-flex min-h-11 items-center text-sm text-accent hover:underline"
            >
              Journal
            </Link>
          </CardHeader>
          <CardContent>
            {trades == null ? (
              <UnavailableState
                message="Recent trades unavailable"
                onRetry={onRetry}
                className="py-4"
              />
            ) : trades.length === 0 ? (
              <SectionEmpty
                title="No journaled trades yet"
                description="Record a trade in the Journal to review its reasoning and outcome."
              />
            ) : (
              <>
                <p className="mb-2 text-xs text-text-secondary">
                  Recent journal entries · recorded PnL
                </p>
                <ul>
                  {trades.map((entry) => (
                    <TradeLine key={entry.id} entry={entry} />
                  ))}
                </ul>
              </>
            )}
          </CardContent>
        </Card>
      </div>
      <Card data-testid="dashboard-strategy-performance">
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>Performance by strategy</CardTitle>
          <Link
            href="/journal/statistics"
            className="inline-flex min-h-11 items-center text-sm text-accent hover:underline"
          >
            Full statistics
          </Link>
        </CardHeader>
        <CardContent className="grid gap-6 lg:grid-cols-2">
          <div className="min-w-0">
            <h4 className="mb-3 text-sm font-medium">Journal results</h4>
            {byStrategy == null ? (
              <UnavailableState
                message="Journal strategy performance unavailable"
                onRetry={onRetry}
                className="py-4"
              />
            ) : byStrategy.length === 0 ? (
              <SectionEmpty
                title="No journaled strategy results yet"
                description="Closed canonical journal trades build strategy statistics."
              />
            ) : (
              <ul>
                {byStrategy.map((bucket) => (
                  <li
                    key={`${bucket.key}-${bucket.label}`}
                    className="border-b border-border-subtle py-3 last:border-b-0"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="min-w-0 break-words text-sm font-medium">
                        {bucket.label}
                      </p>
                      {bucket.metrics.confidence ? (
                        <Badge
                          variant={
                            bucket.metrics.confidence === "insufficient" ||
                            bucket.metrics.confidence === "low"
                              ? "warning"
                              : "muted"
                          }
                        >
                          {humanizeToken(bucket.metrics.confidence)} sample
                        </Badge>
                      ) : null}
                    </div>
                    <dl className="mt-3 grid grid-cols-3 gap-2 text-xs text-text-secondary">
                      <div>
                        <dt>Net PnL</dt>
                        <dd className="mt-1">
                          <DataNumber
                            value={formatMonetary(bucket.metrics.net_pnl_total)}
                          />
                        </dd>
                      </div>
                      <div>
                        <dt>Win rate</dt>
                        <dd className="mt-1">
                          <DataNumber
                            value={bucketWinRate(
                              bucket.metrics.trade_count,
                              bucket.metrics.win_rate,
                            )}
                          />
                        </dd>
                      </div>
                      <div>
                        <dt>Trades</dt>
                        <dd className="mt-1">
                          <DataNumber
                            value={formatCount(bucket.metrics.trade_count)}
                          />
                        </dd>
                      </div>
                    </dl>
                    {bucket.metrics.warnings?.length ? (
                      <ul className="mt-2 space-y-1 text-xs text-warning">
                        {bucket.metrics.warnings.map((warning) => (
                          <li key={warning.code}>{warning.message}</li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="min-w-0">
            <h4 className="mb-3 text-sm font-medium">Closed paper results</h4>
            {closedByStrategy == null ? (
              <UnavailableState
                message="Closed paper strategy performance unavailable"
                onRetry={onRetry}
                className="py-4"
              />
            ) : closedByStrategy.length === 0 ? (
              <SectionEmpty
                title="No closed paper strategy results"
                description="Results appear after paper trades close."
              />
            ) : (
              <ul>
                {closedByStrategy.map((row) => (
                  <li
                    key={row.key}
                    className="flex items-center justify-between gap-3 border-b border-border-subtle py-3 last:border-b-0"
                  >
                    <div className="min-w-0">
                      <p className="break-words text-sm font-medium">
                        {row.key}
                      </p>
                      <p className="mt-1 text-xs text-text-secondary">
                        {formatCount(row.metrics.trade_count)} closed trades
                      </p>
                    </div>
                    <DataNumber
                      value={formatMonetary(row.metrics.net_pnl)}
                      className="shrink-0"
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
