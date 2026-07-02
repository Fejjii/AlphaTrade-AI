"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pnlClassName, formatPercent } from "@/components/portfolio/portfolio-display";
import type { PaperPortfolioAccount, PerformanceMetrics } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

export function PaperPortfolioSummaryCards({
  account,
  metrics,
}: {
  account: PaperPortfolioAccount;
  metrics: PerformanceMetrics;
}) {
  const cards = [
    {
      testId: "portfolio-starting-balance",
      label: "Starting balance",
      value: formatDecimal(account.starting_balance),
      className: "text-zinc-100",
    },
    {
      testId: "portfolio-current-equity",
      label: "Current equity",
      value: formatDecimal(account.current_equity),
      className: "text-zinc-100",
    },
    {
      testId: "portfolio-realized-pnl",
      label: "Realized PnL",
      value: formatDecimal(account.cumulative_realized_pnl),
      className: pnlClassName(account.cumulative_realized_pnl),
    },
    {
      testId: "portfolio-unrealized-pnl",
      label: "Unrealized PnL",
      value:
        account.unrealized_pnl != null ? formatDecimal(account.unrealized_pnl) : "Partial / unavailable",
      className: pnlClassName(account.unrealized_pnl),
    },
    {
      testId: "portfolio-win-rate",
      label: "Win rate",
      value: formatPercent(metrics.win_rate),
      className: "text-zinc-100",
    },
    {
      testId: "portfolio-profit-factor",
      label: "Profit factor",
      value: metrics.profit_factor != null ? metrics.profit_factor.toFixed(2) : "—",
      className: "text-zinc-100",
    },
    {
      testId: "portfolio-max-drawdown",
      label: "Max drawdown",
      value: formatDecimal(metrics.max_drawdown),
      className: "text-rose-400",
    },
    {
      testId: "portfolio-trade-count",
      label: "Closed trades",
      value: String(account.closed_trade_count),
      className: "text-zinc-100",
    },
  ];

  return (
    <section
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="paper-portfolio-summary-cards"
    >
      {cards.map((card) => (
        <Card key={card.testId} data-testid={card.testId}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-normal text-zinc-500">{card.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-xl font-semibold ${card.className}`}>{card.value}</p>
          </CardContent>
        </Card>
      ))}
    </section>
  );
}
