"use client";

import { useCallback, useState } from "react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { PositionCard } from "@/components/PositionCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function PositionsPage() {
  const [busy, setBusy] = useState(false);
  const loader = useCallback(() => api.positions.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Positions</h1>
          <p className="text-sm text-zinc-400">Paper positions only. No real exchange execution.</p>
        </div>
        <KillSwitchButton />
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      <div className="grid gap-4">
        {data?.items.length ? (
          data.items.map((position) => (
            <PositionCard
              key={position.id}
              position={position}
              busy={busy}
              onClosePaper={async (id) => {
                setBusy(true);
                try {
                  const current = data.items.find((item) => item.id === id);
                  await api.positions.closePaper(id, {
                    exit_price: current?.entry_price ?? "1",
                    reason: "Closed from UI",
                  });
                  await reload();
                } finally {
                  setBusy(false);
                }
              }}
            />
          ))
        ) : (
          <EmptyState title="No positions" description="Paper positions appear after approved execution." />
        )}
      </div>
    </div>
  );
}
