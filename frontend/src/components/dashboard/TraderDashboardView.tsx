import Link from "next/link";

import {
  bucketWinRate,
  closedStrategyRows,
  importantAlerts,
  marketEvidenceSummary,
  openPositionRows,
  portfolioEquity,
  portfolioPnl,
  portfolioWinRate,
  recentTradeRows,
  strategyPerformanceRows,
  watcherTraderLabel,
} from "@/components/dashboard/trader-dashboard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import { formatDateTime, formatMonetary, UNAVAILABLE } from "@/lib/format";
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

type TraderDashboardViewProps = {
  data: TraderDashboardData;
  posture: SafetyPostureDisplay;
};

function Metric({
  label,
  value,
  note,
  testId,
}: {
  label: string;
  value: string;
  note?: string | null;
  testId: string;
}) {
  return (
    <div data-testid={testId} className="min-w-0">
      <p className="text-caption text-text-muted">{label}</p>
      <DataNumber value={value} className="mt-1 block text-xl" />
      {note ? <p className="mt-1 text-caption text-text-muted">{note}</p> : null}
    </div>
  );
}

function SectionNote({ children }: { children: string }) {
  return <p className="text-sm text-text-muted">{children}</p>;
}

function TradeLine({ entry }: { entry: JournalEntry }) {
  return (
    <li className="flex items-baseline justify-between gap-3 border-b border-border-subtle py-2 last:border-b-0">
      <span className="min-w-0 truncate text-sm text-text-primary">
        {entry.symbol} · {entry.direction} · {entry.result || UNAVAILABLE}
      </span>
      <span className="shrink-0 font-data text-sm text-text-secondary">
        {formatMonetary(entry.pnl)}
      </span>
    </li>
  );
}

export function TraderDashboardView({ data, posture }: TraderDashboardViewProps) {
  const winRate = portfolioWinRate(data.portfolio);
  const positions = openPositionRows(data.positions);
  const trades = recentTradeRows(data.journal);
  const byStrategy = strategyPerformanceRows(data.strategyStats);
  const closedByStrategy = closedStrategyRows(data.portfolio);
  const alerts = importantAlerts(data.alerts);
  const market = marketEvidenceSummary(data.market);
  const watcherLabel = data.watcher.available
    ? watcherTraderLabel(data.watcher.data?.paper_monitoring_status)
    : "Unavailable";

  return (
    <div className="space-y-6" data-testid="trader-dashboard">
      <PageHeader
        title="Dashboard"
        description="Paper portfolio, open positions, and what needs attention."
        meta={<PaperModeIndicator active={posture.paperConfirmed} />}
      />

      <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="dashboard-safety">
        <span data-testid="dashboard-paper-only">{posture.executionLabel}</span>
        <span data-testid="dashboard-real-trading-status">{posture.realTradingLabel}</span>
        <Badge variant={posture.runtimeBadgeVariant} data-testid="dashboard-runtime-posture">
          {posture.runtimeBadgeLabel}
        </Badge>
      </div>
      {posture.conflictMessage ? (
        <p className="text-sm text-danger" data-testid="dashboard-safety-conflict">
          {posture.conflictMessage}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Paper portfolio</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Metric label="Portfolio value" value={portfolioEquity(data.portfolio)} testId="dashboard-equity" />
          <Metric label="PnL" value={portfolioPnl(data.portfolio)} testId="dashboard-pnl" />
          <Metric
            label="Win rate"
            value={winRate.value}
            note={winRate.note}
            testId="dashboard-win-rate"
          />
          <Metric
            label="Open positions"
            value={positions ? String(positions.length) : UNAVAILABLE}
            testId="dashboard-open-count"
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="dashboard-open-positions">
          <CardHeader>
            <CardTitle>Open positions</CardTitle>
          </CardHeader>
          <CardContent>
            {positions == null ? (
              <SectionNote>Open positions unavailable</SectionNote>
            ) : positions.length === 0 ? (
              <SectionNote>No open positions</SectionNote>
            ) : (
              <ul>
                {positions.map((position) => (
                  <li
                    key={position.id}
                    className="flex items-baseline justify-between gap-3 border-b border-border-subtle py-2 last:border-b-0"
                  >
                    <span className="min-w-0 truncate text-sm text-text-primary">
                      {position.symbol} · {position.direction}
                    </span>
                    <span className="shrink-0 font-data text-sm">
                      {formatMonetary(position.unrealized_pnl)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card data-testid="dashboard-recent-trades">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent trades</CardTitle>
            <Link href="/journal" className="text-sm text-accent hover:underline">
              Journal
            </Link>
          </CardHeader>
          <CardContent>
            {trades == null ? (
              <SectionNote>Recent trades unavailable</SectionNote>
            ) : trades.length === 0 ? (
              <SectionNote>No journaled trades yet</SectionNote>
            ) : (
              <ul>
                {trades.map((entry) => (
                  <TradeLine key={entry.id} entry={entry} />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card data-testid="dashboard-strategy-performance">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Performance by strategy</CardTitle>
          <Link href="/strategies" className="text-sm text-accent hover:underline">
            Strategies
          </Link>
        </CardHeader>
        <CardContent className="space-y-4">
          {byStrategy == null && closedByStrategy == null ? (
            <SectionNote>Strategy performance unavailable</SectionNote>
          ) : null}
          {byStrategy ? (
            byStrategy.length === 0 ? (
              <SectionNote>No journaled strategy results yet</SectionNote>
            ) : (
              <ul>
                {byStrategy.map((bucket) => (
                  <li
                    key={`${bucket.key}-${bucket.label}`}
                    className="flex items-baseline justify-between gap-3 border-b border-border-subtle py-2 last:border-b-0"
                  >
                    <span className="min-w-0 truncate text-sm text-text-primary">{bucket.label}</span>
                    <span className="shrink-0 text-right font-data text-sm text-text-secondary">
                      {formatMonetary(bucket.metrics.net_pnl_total)} ·{" "}
                      {bucketWinRate(bucket.metrics.trade_count, bucket.metrics.win_rate)}
                    </span>
                  </li>
                ))}
              </ul>
            )
          ) : null}
          {closedByStrategy && closedByStrategy.length > 0 ? (
            <div>
              <p className="mb-1 text-caption text-text-muted">Closed paper results</p>
              <ul>
                {closedByStrategy.map((row) => (
                  <li
                    key={row.key}
                    className="flex items-baseline justify-between gap-3 py-1 text-sm"
                  >
                    <span className="min-w-0 truncate text-text-secondary">{row.key}</span>
                    <span className="shrink-0 font-data">{formatMonetary(row.metrics.net_pnl)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card data-testid="dashboard-watcher-status">
          <CardHeader>
            <CardTitle>Watcher</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-lg text-text-primary">{watcherLabel}</p>
            {data.watcher.available && data.watcher.data?.last_scan_at ? (
              <p className="text-caption text-text-muted">
                Last scan {formatDateTime(data.watcher.data.last_scan_at)}
              </p>
            ) : null}
            <Link href="/watcher" className="text-sm text-accent hover:underline">
              Watcher details
            </Link>
          </CardContent>
        </Card>

        <Card data-testid="dashboard-market-evidence">
          <CardHeader>
            <CardTitle>Market evidence</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-lg text-text-primary">{market.label}</p>
            {market.symbol ? (
              <p className="text-caption text-text-muted">{market.symbol}</p>
            ) : null}
            <Link href="/market" className="text-sm text-accent hover:underline">
              Market monitor
            </Link>
          </CardContent>
        </Card>

        <Card data-testid="dashboard-alerts">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Alerts</CardTitle>
            <Link href="/alerts" className="text-sm text-accent hover:underline">
              All alerts
            </Link>
          </CardHeader>
          <CardContent>
            {alerts == null ? (
              <SectionNote>Alerts unavailable</SectionNote>
            ) : alerts.length === 0 ? (
              <SectionNote>No alerts</SectionNote>
            ) : (
              <ul className="space-y-2">
                {alerts.map((alert) => (
                  <li key={alert.id} className="text-sm text-text-primary">
                    <span className="text-caption uppercase text-text-muted">{alert.severity}</span>
                    <p>{alert.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
