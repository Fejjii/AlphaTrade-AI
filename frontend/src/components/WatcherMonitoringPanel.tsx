"use client";

import { WatcherMonitoringCard } from "@/components/WatcherMonitoringCard";
import { ErrorState, LoadingState } from "@/components/states";
import { useWatcherMonitoring } from "@/hooks/useWatcherMonitoring";

export function WatcherMonitoringPanel({ compact = false }: { compact?: boolean }) {
  const { data, loading, error, reload } = useWatcherMonitoring();

  if (loading) {
    return (
      <div data-testid="watcher-monitoring-loading">
        <LoadingState label="Loading Watcher monitoring…" />
      </div>
    );
  }
  if (error) {
    return (
      <div data-testid="watcher-monitoring-error">
        <ErrorState message={error} onRetry={() => void reload()} />
      </div>
    );
  }
  if (!data) {
    return (
      <p className="text-xs text-text-muted" data-testid="watcher-monitoring-empty">
        Watcher monitoring unavailable.
      </p>
    );
  }
  return (
    <WatcherMonitoringCard
      snapshot={data}
      compact={compact}
      onRefresh={() => void reload()}
    />
  );
}
