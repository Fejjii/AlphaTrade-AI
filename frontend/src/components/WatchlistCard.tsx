"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WatchlistItem } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

export function WatchlistCard({
  item,
  onToggle,
  onDelete,
  busy,
}: {
  item: WatchlistItem;
  onToggle?: (id: string, enabled: boolean) => void;
  onDelete?: (id: string) => void;
  busy?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {item.symbol} · {item.exchange}
          </CardTitle>
          <StatusBadge label={item.enabled ? "Enabled" : "Disabled"} tone={item.enabled ? "ok" : "muted"} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p className="text-zinc-400">Timeframes: {item.timeframes.join(", ")}</p>
        <p className="text-zinc-400">Strategies: {item.strategy_ids.join(", ")}</p>
        <p className="text-zinc-500">Added {formatDate(item.created_at)}</p>
        <div className="flex flex-wrap gap-2">
          {onToggle ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={() => onToggle(item.id, !item.enabled)}
            >
              {item.enabled ? "Disable item" : "Enable item"}
            </Button>
          ) : null}
          {onDelete ? (
            <Button variant="destructive" size="sm" disabled={busy} onClick={() => onDelete(item.id)}>
              Delete item
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
