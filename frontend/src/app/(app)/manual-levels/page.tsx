"use client";

import { useCallback } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { formatDecimal } from "@/lib/utils";

export default function ManualLevelsPage() {
  const loader = useCallback(() => api.manualLevels.list(), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Manual Levels</h1>
        <p className="text-sm text-zinc-400">
          Chart levels for deterministic pre-trade analysis (paper only).
        </p>
      </div>

      {loading ? <LoadingState label="Loading levels…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data?.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((level) => (
            <Card key={level.id}>
              <CardHeader>
                <CardTitle className="text-base">
                  {level.symbol} · {level.level_type.replace("_", " ")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-zinc-300">
                <p>Exchange: {level.exchange}</p>
                {level.price ? <p>Price: {formatDecimal(level.price)}</p> : null}
                {level.label ? <p>{level.label}</p> : null}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {data && !data.items.length ? (
        <EmptyState
          title="No manual levels"
          description="Add support, resistance, Fibonacci, and other levels via the API or AI Workspace."
        />
      ) : null}
    </div>
  );
}
