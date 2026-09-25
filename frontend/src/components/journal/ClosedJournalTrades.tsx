import type { CanonicalJournalTradeListItem } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function shown(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  return value;
}

export function ClosedJournalTrades({ trades }: { trades: CanonicalJournalTradeListItem[] }) {
  return (
    <Card data-testid="closed-journal-trades">
      <CardHeader>
        <CardTitle className="text-base">Closed paper trades</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {trades.length ? (
          <ul className="space-y-3">
            {trades.map((trade) => (
              <li key={trade.id} className="rounded-md border border-border p-3" data-testid="closed-journal-trade">
                <p>
                  {trade.symbol} · {trade.timeframe} · {trade.direction} · {trade.result}
                </p>
                <p>
                  Entry {shown(trade.entry_price)} · exit {shown(trade.exit_price)} · reason{" "}
                  {shown(trade.exit_reason)}
                </p>
                <p>
                  PnL {shown(trade.net_pnl)} · fees {shown(trade.fees)} · strategy{" "}
                  {shown(trade.strategy_label ?? trade.strategy_version_id)}
                </p>
                {trade.thesis ? <p>Trade reason: {trade.thesis}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-text-muted">No closed canonical journal trades in this list.</p>
        )}
      </CardContent>
    </Card>
  );
}
