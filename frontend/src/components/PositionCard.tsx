"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Position } from "@/lib/api/types";
import { formatDate, formatDecimal } from "@/lib/utils";

export function PositionCard({
  position,
  onClosePaper,
  busy,
}: {
  position: Position;
  onClosePaper?: (id: string) => void;
  busy?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {position.symbol} · {position.direction.toUpperCase()}
          </CardTitle>
          <StatusBadge label={position.status} tone={position.status === "open" ? "ok" : "muted"} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <div className="grid gap-1 sm:grid-cols-2">
          <span>Entry: {formatDecimal(position.entry_price)}</span>
          <span>Size: {formatDecimal(position.size)}</span>
          <span>Unrealized PnL: {formatDecimal(position.unrealized_pnl)}</span>
          <span>Opened: {formatDate(position.opened_at)}</span>
        </div>
        {Object.keys(position.risk_state).length > 0 ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
            <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Risk state</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(position.risk_state).map(([key, value]) => (
                <StatusBadge key={key} label={`${key}: ${value}`} tone="info" />
              ))}
            </div>
          </div>
        ) : null}
        {position.status === "open" && onClosePaper ? (
          <Button variant="warning" disabled={busy} onClick={() => onClosePaper(position.id)}>
            Close paper position
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
