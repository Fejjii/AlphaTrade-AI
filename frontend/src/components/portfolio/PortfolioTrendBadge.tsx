"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { trendLabel, trendVariant } from "@/components/portfolio/portfolio-display";
import type { PortfolioTrend } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

export function PortfolioTrendBadge({ trend }: { trend: PortfolioTrend }) {
  return (
    <Card data-testid="paper-portfolio-trend">
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-base">Recent trend</CardTitle>
        <Badge variant={trendVariant(trend.label)} data-testid="portfolio-trend-badge">
          {trendLabel(trend.label)}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-zinc-300">
        <p className="text-xs text-zinc-500">
          {trend.window_days}-day window · descriptive only, not a trading signal.
        </p>
        {trend.recent_net_pnl != null ? (
          <p>
            Recent net PnL:{" "}
            <span className="font-medium text-zinc-100">{formatDecimal(trend.recent_net_pnl)}</span>
          </p>
        ) : null}
        {trend.prior_net_pnl != null ? (
          <p>
            Prior net PnL:{" "}
            <span className="font-medium text-zinc-100">{formatDecimal(trend.prior_net_pnl)}</span>
          </p>
        ) : null}
        {trend.rationale ? <p className="text-xs text-zinc-400">{trend.rationale}</p> : null}
      </CardContent>
    </Card>
  );
}
