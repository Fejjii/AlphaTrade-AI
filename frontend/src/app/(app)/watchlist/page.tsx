"use client";

import { useCallback, useState } from "react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { WatchlistCard } from "@/components/WatchlistCard";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function WatchlistPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [busy, setBusy] = useState(false);
  const loader = useCallback(() => api.watchlist.list(), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  async function addItem() {
    setBusy(true);
    try {
      await api.watchlist.create({
        symbol,
        exchange: "mock",
        timeframes: ["1h", "4h"],
        strategy_ids: ["htf_trend_pullback"],
        enabled: true,
      });
      await reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Watchlist</h1>
          <p className="text-sm text-zinc-400">Monitor symbols with strategy sets and timeframes.</p>
        </div>
        <KillSwitchButton compact />
      </div>

      <div className="grid gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 md:grid-cols-[1fr_auto]">
        <div className="space-y-2">
          <Label htmlFor="symbol">Add symbol</Label>
          <Input id="symbol" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
        </div>
        <div className="flex items-end">
          <Button disabled={busy} onClick={() => void addItem()}>
            Add to watchlist
          </Button>
        </div>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {!loading && !error && data?.length === 0 ? (
        <EmptyState title="Watchlist is empty" description="Add a symbol to start monitoring." />
      ) : null}
      <div className="grid gap-4">
        {data?.map((item) => (
          <WatchlistCard
            key={item.id}
            item={item}
            busy={busy}
            onToggle={async (id, enabled) => {
              setBusy(true);
              try {
                await api.watchlist.update(id, { enabled });
                await reload();
              } finally {
                setBusy(false);
              }
            }}
            onDelete={async (id) => {
              setBusy(true);
              try {
                await api.watchlist.delete(id);
                await reload();
              } finally {
                setBusy(false);
              }
            }}
          />
        ))}
      </div>
    </div>
  );
}
