"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/states";
import { pnlClassName, formatPercent } from "@/components/portfolio/portfolio-display";
import type { PortfolioGroupBreakdown } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

export function PortfolioBreakdownTable({
  title,
  rows,
  testId,
}: {
  title: string;
  rows: PortfolioGroupBreakdown[];
  testId: string;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                  <th className="pb-2 pr-3">Key</th>
                  <th className="pb-2 pr-3">Trades</th>
                  <th className="pb-2 pr-3">Win rate</th>
                  <th className="pb-2 pr-3">Net PnL</th>
                  <th className="pb-2">Profit factor</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key} className="border-b border-zinc-900/80" data-testid={`${testId}-row-${row.key}`}>
                    <td className="py-2 pr-3 font-medium text-zinc-200">{row.key || "—"}</td>
                    <td className="py-2 pr-3 text-zinc-400">{row.metrics.trade_count}</td>
                    <td className="py-2 pr-3 text-zinc-400">{formatPercent(row.metrics.win_rate)}</td>
                    <td className={`py-2 pr-3 ${pnlClassName(row.metrics.net_pnl)}`}>
                      {formatDecimal(row.metrics.net_pnl)}
                    </td>
                    <td className="py-2 text-zinc-400">
                      {row.metrics.profit_factor != null ? row.metrics.profit_factor.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No breakdown data" description="No closed trades match this grouping." />
        )}
      </CardContent>
    </Card>
  );
}
