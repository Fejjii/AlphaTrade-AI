"use client";

import { useCallback } from "react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { PositionCard } from "@/components/PositionCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function PositionsPage() {
  const loader = useCallback(() => api.positions.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  const closePaperPosition = useCallback(
    async (id: string, exitPrice: string) => {
      // The exit price is exactly what the user entered and confirmed — never a
      // fallback or the entry price. Failures propagate to the card, which keeps
      // the position visible and open; the list reloads only after success.
      await api.positions.closePaper(id, {
        exit_price: exitPrice,
        reason: "Paper close at user-entered exit price",
      });
      await reload();
    },
    [reload],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Positions</h1>
          <p className="text-sm text-zinc-400">Paper positions only. No real exchange execution.</p>
        </div>
        <KillSwitchButton />
      </div>

      {loading ? (
        <LoadingState label="Loading positions…" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void reload()} />
      ) : data ? (
        <div className="grid gap-4">
          {data.items.length ? (
            data.items.map((position) => (
              <PositionCard
                key={position.id}
                position={position}
                onClosePaper={closePaperPosition}
              />
            ))
          ) : (
            <EmptyState
              title="No positions"
              description="Paper positions appear after approved execution."
            />
          )}
        </div>
      ) : null}
    </div>
  );
}
