"use client";

import { useCallback } from "react";

import { ErrorState, LoadingState } from "@/components/states";
import {
  TraderStrategiesView,
  type TraderStrategiesData,
} from "@/components/strategies/TraderStrategiesView";
import { loadSource } from "@/components/workflows";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function StrategiesPage() {
  const loader = useCallback(async (): Promise<TraderStrategiesData> => {
    const [strategies, stats, journal] = await Promise.all([
      loadSource(api.strategies.list({ limit: 50 })),
      loadSource(api.journal.statistics({ group_by: "strategy", limit: 20 })),
      loadSource(api.journal.list({ limit: 50 })),
    ]);
    return { strategies, stats, journal };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);
  if (loading && !data) return <LoadingState label="Loading strategies…" />;
  if (error || !data) {
    return <ErrorState message={error ?? "Strategies unavailable"} onRetry={() => void reload()} />;
  }
  return <TraderStrategiesView data={data} />;
}
