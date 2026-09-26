"use client";

import { useCallback } from "react";

import {
  TraderDashboardView,
  type TraderDashboardData,
} from "@/components/dashboard/TraderDashboardView";
import { ErrorState, LoadingState } from "@/components/states";
import { describeSafetyPosture, loadSource } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const { executionMode, realTradingEnabled } = useSafetyPosture();

  const loader = useCallback(async (): Promise<TraderDashboardData> => {
    const [portfolio, positions, journal, strategyStats, summary, watcher, market, alerts] =
      await Promise.all([
        loadSource(api.performance.portfolio()),
        loadSource(api.positions.list({ status: "open", limit: 20 })),
        loadSource(api.journal.list({ limit: 8 })),
        loadSource(api.journal.statistics({ group_by: "strategy", limit: 8 })),
        loadSource(api.dashboard.summary()),
        loadSource(api.marketWatcher.monitoring()),
        loadSource(api.canonical.getMarketStatus()),
        loadSource(api.alerts.list({ limit: 8 })),
      ]);
    return {
      portfolio,
      positions,
      journal,
      strategyStats,
      summary,
      watcher,
      market,
      alerts,
    };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading && !data) {
    return <LoadingState label="Loading dashboard…" />;
  }
  if (error || !data) {
    return <ErrorState message={error ?? "Dashboard unavailable"} onRetry={() => void reload()} />;
  }

  const posture = describeSafetyPosture(
    data.summary.data?.safety.execution_mode ?? executionMode,
    data.summary.data?.safety.real_trading_enabled ?? realTradingEnabled,
  );

  return <TraderDashboardView data={data} posture={posture} />;
}
