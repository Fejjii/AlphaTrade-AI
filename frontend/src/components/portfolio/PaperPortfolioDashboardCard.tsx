"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pnlClassName } from "@/components/portfolio/portfolio-display";
import type { PaperPortfolioResponse } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

function recentDailyPnl(data: PaperPortfolioResponse): string | null {
  if (!data.daily_series.length) return null;
  const latest = data.daily_series[data.daily_series.length - 1];
  return latest.daily_pnl;
}

export function PaperPortfolioDashboardCard({
  portfolio,
}: {
  portfolio: PaperPortfolioResponse | null;
}) {
  const recentPnl = portfolio ? recentDailyPnl(portfolio) : null;

  return (
    <Card data-testid="dashboard-paper-portfolio">
      <CardHeader>
        <CardTitle className="text-base">View paper portfolio</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          Simulated paper performance over time — read-only review before any future real money
          discussion. Not live trading or investment advice.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        {portfolio ? (
          <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
            <div data-testid="dashboard-portfolio-equity">
              <p className="text-zinc-500">Current equity</p>
              <p className="text-lg font-semibold text-zinc-100">
                {formatDecimal(portfolio.account.current_equity)}
              </p>
            </div>
            <div data-testid="dashboard-portfolio-realized-pnl">
              <p className="text-zinc-500">Realized PnL</p>
              <p
                className={`text-lg font-semibold ${pnlClassName(portfolio.account.cumulative_realized_pnl)}`}
              >
                {formatDecimal(portfolio.account.cumulative_realized_pnl)}
              </p>
            </div>
            <div data-testid="dashboard-portfolio-recent-pnl">
              <p className="text-zinc-500">Recent daily PnL</p>
              <p className={`text-lg font-semibold ${pnlClassName(recentPnl)}`}>
                {recentPnl != null ? formatDecimal(recentPnl) : "—"}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-zinc-500" data-testid="dashboard-portfolio-empty">
            Portfolio summary unavailable — open the page to load simulated performance.
          </p>
        )}

        <Link
          href="/portfolio"
          className="inline-block text-xs text-zinc-400 underline"
          data-testid="dashboard-portfolio-link"
        >
          Open paper portfolio
        </Link>
      </CardContent>
    </Card>
  );
}
