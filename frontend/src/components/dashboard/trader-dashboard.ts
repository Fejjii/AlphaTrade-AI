import type { SourceResult } from "@/components/workflows/sourceResult";
import {
  formatCount,
  formatCurrency,
  formatMonetary,
  formatPercent,
  UNAVAILABLE,
} from "@/lib/format";
import type {
  CanonicalMarketMonitorStatusRead,
  CanonicalJournalTradeListItem,
  DashboardSummary,
  OpenPaperTradeItem,
  JournalStatsBucket,
  PaperAlert,
  PaperPortfolioResponse,
  PortfolioGroupBreakdown,
  WatcherMonitoringRuntimeState,
} from "@/lib/api/types";

export function watcherTraderLabel(
  status: WatcherMonitoringRuntimeState | string | null | undefined,
): string {
  switch (status) {
    case "RUNNING":
      return "Watching";
    case "STOPPED":
      return "Stopped";
    case "DEGRADED":
      return "Degraded";
    case "STALE":
      return "Stale";
    case "BLOCKED":
      return "Blocked";
    default:
      return "Unavailable";
  }
}

export function marketEvidenceLabel(
  availability: string | null | undefined,
): string {
  switch (availability) {
    case "fresh":
      return "Healthy";
    case "stale":
      return "Stale";
    case "degraded":
      return "Degraded";
    case "unavailable":
      return "Unavailable";
    case "replay":
      return "Replay";
    default:
      return "Unavailable";
  }
}

export function portfolioEquity(
  portfolio: SourceResult<PaperPortfolioResponse>,
): string {
  if (!portfolio.available || !portfolio.data) return UNAVAILABLE;
  return formatCurrency(portfolio.data.account.current_equity);
}

export function portfolioPnl(
  portfolio: SourceResult<PaperPortfolioResponse>,
): string {
  if (!portfolio.available || !portfolio.data) return UNAVAILABLE;
  return formatMonetary(portfolio.data.metrics.net_pnl);
}

export function portfolioWinRate(
  portfolio: SourceResult<PaperPortfolioResponse>,
): {
  value: string;
  note: string | null;
} {
  if (!portfolio.available || !portfolio.data) {
    return { value: UNAVAILABLE, note: null };
  }
  const metrics = portfolio.data.metrics;
  if (metrics.trade_count <= 0) {
    return { value: UNAVAILABLE, note: "No closed trades yet" };
  }
  return {
    value: formatPercent(metrics.win_rate),
    note: `${formatCount(metrics.trade_count)} closed trades`,
  };
}

export function portfolioExpectancy(
  portfolio: SourceResult<PaperPortfolioResponse>,
): {
  value: string;
  note: string;
} {
  if (!portfolio.available || !portfolio.data) {
    return { value: UNAVAILABLE, note: "Portfolio unavailable" };
  }
  const metrics = portfolio.data.metrics;
  if (metrics.trade_count <= 0) {
    return { value: UNAVAILABLE, note: "No closed trades yet" };
  }
  const value = formatMonetary(metrics.expectancy);
  return {
    value,
    note:
      value === UNAVAILABLE
        ? "Expectancy unavailable"
        : `Per trade · ${formatCount(metrics.trade_count)} closed trades`,
  };
}

export function openPositionCount(
  summary: SourceResult<DashboardSummary>,
): string {
  const open = summary.available ? summary.data?.open_paper_trades_summary : null;
  return open ? formatCount(open.total_count) : UNAVAILABLE;
}

export function openPositionRows(
  summary: SourceResult<DashboardSummary>,
): OpenPaperTradeItem[] | null {
  const open = summary.available ? summary.data?.open_paper_trades_summary : null;
  return open ? open.items.slice(0, 8) : null;
}

export function recentTradeRows(
  journal: SourceResult<{ items: CanonicalJournalTradeListItem[] }>,
): CanonicalJournalTradeListItem[] | null {
  if (!journal.available || !journal.data) return null;
  return journal.data.items.slice(0, 6);
}

export function strategyPerformanceRows(
  stats: SourceResult<{ buckets: JournalStatsBucket[] }>,
): JournalStatsBucket[] | null {
  if (!stats.available || !stats.data) return null;
  return stats.data.buckets.slice(0, 8);
}

export function closedStrategyRows(
  portfolio: SourceResult<PaperPortfolioResponse>,
): PortfolioGroupBreakdown[] | null {
  if (!portfolio.available || !portfolio.data) return null;
  return portfolio.data.breakdowns.by_strategy.slice(0, 8);
}

export function bucketWinRate(
  tradeCount: number,
  winRate: number | null,
): string {
  if (tradeCount <= 0 || winRate == null) return UNAVAILABLE;
  return formatPercent(winRate);
}

export function importantAlerts(
  alerts: SourceResult<{ items: PaperAlert[]; total: number }>,
): PaperAlert[] | null {
  if (!alerts.available || !alerts.data) return null;
  return [...alerts.data.items]
    .sort((left, right) => {
      const leftUnread = left.read_at ? 1 : 0;
      const rightUnread = right.read_at ? 1 : 0;
      if (leftUnread !== rightUnread) return leftUnread - rightUnread;
      const priority: Record<string, number> = {
        critical: 0,
        high: 1,
        warning: 2,
        medium: 2,
        info: 3,
        low: 3,
      };
      const severityDifference =
        (priority[left.severity] ?? 3) - (priority[right.severity] ?? 3);
      if (severityDifference !== 0) return severityDifference;
      return right.created_at.localeCompare(left.created_at);
    })
    .slice(0, 5);
}

export function marketEvidenceSummary(
  market: SourceResult<CanonicalMarketMonitorStatusRead>,
): { label: string; symbol: string | null } {
  if (!market.available || !market.data) {
    return { label: "Unavailable", symbol: null };
  }
  const symbol = market.data.symbol.trim();
  return {
    label: marketEvidenceLabel(market.data.availability),
    symbol: symbol.length > 0 ? symbol : null,
  };
}
